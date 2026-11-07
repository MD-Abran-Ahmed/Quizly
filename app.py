import os
import uuid
import csv
import io
from datetime import datetime, timezone, timedelta
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Allow OAuth over plain HTTP in local development (never set this in production)
os.environ.setdefault('OAUTHLIB_INSECURE_TRANSPORT', '1')

from flask import (
    Flask, render_template, request, jsonify, redirect,
    url_for, flash, abort, send_from_directory
)
from flask_login import login_required, current_user

from database import (
    db, init_db, User, Document, Quiz, Question,
    QuizAttempt, UserAnswer
)
from auth import auth_bp, init_auth
from pdf_processor import extract_text_from_pdf, allowed_file, PDFProcessingError
from ai_generator import generate_quiz_mcqs, AIGenerationError

def create_app():
    app = Flask(__name__)

    # Configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'quizly-secure-secret-key-default-2025')
    os.makedirs(app.instance_path, exist_ok=True)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URI', 'sqlite:///quizly.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    upload_folder = os.getenv('UPLOAD_FOLDER', os.path.join(app.root_path, 'uploads', 'pdfs'))
    os.makedirs(upload_folder, exist_ok=True)
    app.config['UPLOAD_FOLDER'] = upload_folder
    app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', 25 * 1024 * 1024))  # 25 MB max

    # Initialize extensions
    init_db(app)
    init_auth(app)

    # Register Blueprints
    app.register_blueprint(auth_bp)

    # Context processor for global template variables
    @app.context_processor
    def inject_globals():
        return {
            'app_name': 'Quizly',
            'current_year': datetime.now().year
        }

    @app.after_request
    def apply_cache_control(response):
        """Prevent browser caching of authenticated and dynamic views."""
        if current_user.is_authenticated or request.path.startswith('/api/') or request.path in ['/dashboard', '/upload', '/create', '/documents', '/quizzes', '/analytics']:
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '-1'
        return response

    # --- ERROR HANDLERS ---
    @app.errorhandler(404)
    def page_not_found(e):
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'message': 'Resource not found'}), 404
        return render_template('base.html', error_code=404, error_message="Page Not Found"), 404

    @app.errorhandler(413)
    def file_too_large(e):
        return jsonify({'success': False, 'message': 'File size exceeds 25MB limit.'}), 413

    @app.errorhandler(500)
    def internal_server_error(e):
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'message': 'An internal server error occurred.'}), 500
        return render_template('base.html', error_code=500, error_message="Internal Server Error"), 500

    # =========================================================================
    # PAGE ROUTES (HTML VIEWS)
    # =========================================================================

    @app.route('/')
    def landing_page():
        """Public landing page."""
        if current_user.is_authenticated:
            return redirect(url_for('dashboard_page'))
        return render_template('index.html')

    @app.route('/dashboard')
    @login_required
    def dashboard_page():
        """Student dashboard."""
        return render_template('dashboard.html')

    @app.route('/upload')
    @login_required
    def upload_page():
        """PDF document upload screen."""
        return render_template('upload_pdf.html')

    @app.route('/create')
    @app.route('/quiz/create')
    @login_required
    def create_quiz_page():
        """Manual question creation and CSV bulk upload workspace."""
        return render_template('create_question.html')

    @app.route('/documents')
    @login_required
    def documents_page():
        """My Documents library."""
        return render_template('notes.html')

    @app.route('/quiz/setup/<int:doc_id>')
    @login_required
    def quiz_setup_page(doc_id):
        """Configure and customize quiz parameters before generation."""
        doc = Document.query.filter_by(id=doc_id, user_id=current_user.id).first_or_404()
        return render_template('quiz_setup.html', document=doc)

    @app.route('/quiz/<int:quiz_id>')
    @login_required
    def take_quiz_page(quiz_id):
        """Interactive quiz test taking screen."""
        quiz = Quiz.query.filter_by(id=quiz_id, user_id=current_user.id).first_or_404()
        return render_template('take_quiz.html', quiz=quiz)

    @app.route('/quiz/<int:quiz_id>/result/<int:attempt_id>')
    @login_required
    def quiz_result_page(quiz_id, attempt_id):
        """Quiz submission score and answer breakdown."""
        quiz = Quiz.query.filter_by(id=quiz_id, user_id=current_user.id).first_or_404()
        attempt = QuizAttempt.query.filter_by(id=attempt_id, quiz_id=quiz_id, user_id=current_user.id).first_or_404()
        return render_template('quiz_result.html', quiz=quiz, attempt=attempt)

    @app.route('/quizzes')
    @login_required
    def quizzes_page():
        """My Quizzes list."""
        return render_template('question_bank.html')

    @app.route('/analytics')
    @login_required
    def analytics_page():
        """Student performance analytics."""
        return render_template('dashboard.html', active_tab='performance')

    # =========================================================================
    # REST API ROUTES
    # =========================================================================

    # --- DOCUMENT APIS ---

    @app.route('/api/documents/upload', methods=['POST'])
    @login_required
    def api_upload_document():
        """Upload and extract text from a study notes PDF."""
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'No file was provided in the upload request.'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file was selected.'}), 400

        if not allowed_file(file.filename):
            return jsonify({'success': False, 'message': 'Invalid file format. Only PDF (.pdf) files are supported.'}), 400

        try:
            # Secure filename and generate unique storage name
            orig_filename = secure_filename(file.filename)
            unique_name = f"{uuid.uuid4().hex}_{orig_filename}"
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)

            file.save(save_path)
            file_size = os.path.getsize(save_path)

            # Extract text using PyMuPDF
            extract_result = extract_text_from_pdf(save_path)

            # Save document to database
            doc = Document(
                user_id=current_user.id,
                filename=unique_name,
                original_filename=orig_filename,
                file_size=file_size,
                page_count=extract_result['page_count'],
                extracted_text=extract_result['text']
            )
            db.session.add(doc)
            db.session.commit()

            return jsonify({
                'success': True,
                'message': 'PDF uploaded and parsed successfully!',
                'document': doc.to_dict(),
                'setup_url': url_for('quiz_setup_page', doc_id=doc.id)
            }), 201

        except PDFProcessingError as pe:
            # Clean up uploaded file if processing failed
            if 'save_path' in locals() and os.path.exists(save_path):
                try:
                    os.remove(save_path)
                except Exception:
                    pass
            return jsonify({'success': False, 'message': str(pe)}), 422

        except Exception as e:
            if 'save_path' in locals() and os.path.exists(save_path):
                try:
                    os.remove(save_path)
                except Exception:
                    pass
            return jsonify({'success': False, 'message': f"Unexpected server error during upload: {str(e)}"}), 500

    @app.route('/api/documents', methods=['GET'])
    @login_required
    def api_get_documents():
        """List all documents for the current user."""
        docs = Document.query.filter_by(user_id=current_user.id).order_by(Document.created_at.desc()).all()
        return jsonify({
            'success': True,
            'documents': [d.to_dict() for d in docs]
        })

    @app.route('/api/documents/<int:doc_id>', methods=['DELETE'])
    @login_required
    def api_delete_document(doc_id):
        """Delete an uploaded document and its stored file."""
        doc = Document.query.filter_by(id=doc_id, user_id=current_user.id).first_or_404()

        # Remove file from disk
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], doc.filename)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass

        db.session.delete(doc)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Document deleted successfully.'})

    @app.route('/api/documents/<int:doc_id>/preview', methods=['GET'])
    @login_required
    def api_preview_document(doc_id):
        """Preview snippet of extracted text."""
        doc = Document.query.filter_by(id=doc_id, user_id=current_user.id).first_or_404()
        snippet = doc.extracted_text[:1200] + ('...' if len(doc.extracted_text) > 1200 else '')
        return jsonify({
            'success': True,
            'id': doc.id,
            'filename': doc.original_filename,
            'preview': snippet,
            'char_count': len(doc.extracted_text),
            'page_count': doc.page_count
        })

    # --- QUIZ APIS ---

    @app.route('/api/quiz/generate', methods=['POST'])
    @login_required
    def api_generate_quiz():
        """Generate MCQs from a document using AI engine."""
        data = request.get_json() or {}
        doc_id = data.get('document_id')
        num_questions = int(data.get('num_questions', 10))
        difficulty = data.get('difficulty', 'Mixed')
        custom_title = data.get('title', '').strip()
        include_explanations = bool(data.get('include_explanations', True))

        if not doc_id:
            return jsonify({'success': False, 'message': 'A valid document ID is required.'}), 400

        doc = Document.query.filter_by(id=doc_id, user_id=current_user.id).first_or_404()

        if not doc.extracted_text or len(doc.extracted_text.strip()) < 30:
            return jsonify({'success': False, 'message': 'The selected document does not contain enough text content.'}), 400

        quiz_title = custom_title or f"Quiz: {doc.original_filename.rsplit('.', 1)[0]}"

        try:
            # Generate questions via AI
            gen_result = generate_quiz_mcqs(
                extracted_text=doc.extracted_text,
                num_questions=min(max(num_questions, 3), 30),
                difficulty=difficulty,
                quiz_title=quiz_title,
                include_explanations=include_explanations
            )

            # Create Quiz record
            quiz = Quiz(
                user_id=current_user.id,
                document_id=doc.id,
                title=gen_result.get('quiz_title') or quiz_title,
                difficulty=difficulty,
                num_questions=len(gen_result['questions'])
            )
            db.session.add(quiz)
            db.session.flush()

            # Insert Questions
            for q_data in gen_result['questions']:
                question = Question(
                    quiz_id=quiz.id,
                    order_num=q_data.get('order_num', 1),
                    question_text=q_data['question_text'],
                    option_a=q_data['option_a'],
                    option_b=q_data['option_b'],
                    option_c=q_data['option_c'],
                    option_d=q_data['option_d'],
                    correct_option=q_data['correct_option'],
                    explanation=q_data.get('explanation', '')
                )
                db.session.add(question)

            db.session.commit()

            return jsonify({
                'success': True,
                'message': f"Generated {len(gen_result['questions'])} questions successfully!",
                'quiz_id': quiz.id,
                'quiz_url': url_for('take_quiz_page', quiz_id=quiz.id)
            }), 201

        except AIGenerationError as ae:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(ae)}), 422
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': f"Failed to generate quiz: {str(e)}"}), 500

    @app.route('/api/quiz/demo-csv', methods=['GET'])
    def api_download_demo_csv():
        """Download sample/template CSV format for bulk MCQ upload."""
        downloads_dir = os.path.join(app.root_path, 'static', 'downloads')
        return send_from_directory(
            directory=downloads_dir,
            path='quizly_demo_template.csv',
            as_attachment=True,
            download_name='quizly_demo_template.csv',
            mimetype='text/csv'
        )

    @app.route('/api/quiz/upload-csv', methods=['POST'])
    @login_required
    def api_upload_csv_quiz():
        """Upload and parse a CSV file containing questions and options."""
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'No CSV file was provided.'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file was selected.'}), 400

        if not file.filename.lower().endswith('.csv'):
            return jsonify({'success': False, 'message': 'Invalid file format. Please upload a .csv file.'}), 400

        custom_title = request.form.get('title', '').strip()
        custom_difficulty = request.form.get('difficulty', 'Mixed').strip()

        try:
            raw_bytes = file.read()
            if not raw_bytes:
                return jsonify({'success': False, 'message': 'The uploaded CSV file is empty.'}), 422

            # Decode UTF-8 (handling BOM) or fallback to latin-1
            try:
                content = raw_bytes.decode('utf-8-sig')
            except UnicodeDecodeError:
                content = raw_bytes.decode('latin-1', errors='replace')

            reader = csv.reader(io.StringIO(content))
            rows = [r for r in reader if any(field.strip() for field in r)]
            if not rows or len(rows) < 2:
                return jsonify({
                    'success': False,
                    'message': 'CSV must contain a header row and at least 1 question row. Download our sample demo format to see the layout.'
                }), 422

            headers = [h.strip().lower().replace(' ', '_').replace('-', '_') for h in rows[0]]

            def find_col(aliases):
                for alias in aliases:
                    for i, h in enumerate(headers):
                        if h == alias or h.startswith(alias):
                            return i
                return -1

            q_idx = find_col(['question_text', 'question', 'prompt', 'q'])
            opt_a_idx = find_col(['option_a', 'option1', 'choice_a', 'a'])
            opt_b_idx = find_col(['option_b', 'option2', 'choice_b', 'b'])
            opt_c_idx = find_col(['option_c', 'option3', 'choice_c', 'c'])
            opt_d_idx = find_col(['option_d', 'option4', 'choice_d', 'd'])
            ans_idx = find_col(['correct_option', 'correct_answer', 'correct', 'answer', 'ans'])
            exp_idx = find_col(['explanation', 'explain', 'rationale', 'notes', 'hint'])

            missing = []
            if q_idx == -1: missing.append('question')
            if opt_a_idx == -1: missing.append('option_a')
            if opt_b_idx == -1: missing.append('option_b')
            if opt_c_idx == -1: missing.append('option_c')
            if opt_d_idx == -1: missing.append('option_d')
            if ans_idx == -1: missing.append('correct_option')

            if missing:
                return jsonify({
                    'success': False,
                    'message': f"CSV is missing required columns: {', '.join(missing)}. Please use our demo template format."
                }), 422

            parsed_questions = []
            for row_num, row in enumerate(rows[1:], start=2):
                if not any(cell.strip() for cell in row):
                    continue

                def get_val(idx):
                    return row[idx].strip() if idx < len(row) else ''

                q_text = get_val(q_idx)
                opt_a = get_val(opt_a_idx)
                opt_b = get_val(opt_b_idx)
                opt_c = get_val(opt_c_idx)
                opt_d = get_val(opt_d_idx)
                ans_raw = get_val(ans_idx).strip()
                exp = get_val(exp_idx) if exp_idx != -1 else ''

                if not q_text:
                    return jsonify({'success': False, 'message': f'Row {row_num}: Question text cannot be empty.'}), 422
                if not (opt_a and opt_b and opt_c and opt_d):
                    return jsonify({'success': False, 'message': f'Row {row_num}: All 4 options (A, B, C, D) are required.'}), 422

                # Normalize correct_option
                correct_letter = None
                ans_upper = ans_raw.upper()
                if ans_upper in ['A', 'B', 'C', 'D']:
                    correct_letter = ans_upper
                elif ans_upper in ['1', '2', '3', '4']:
                    correct_letter = {'1': 'A', '2': 'B', '3': 'C', '4': 'D'}[ans_upper]
                else:
                    if ans_raw.lower() == opt_a.lower(): correct_letter = 'A'
                    elif ans_raw.lower() == opt_b.lower(): correct_letter = 'B'
                    elif ans_raw.lower() == opt_c.lower(): correct_letter = 'C'
                    elif ans_raw.lower() == opt_d.lower(): correct_letter = 'D'

                if not correct_letter:
                    return jsonify({
                        'success': False,
                        'message': f"Row {row_num}: Invalid correct option '{ans_raw}'. Must be A, B, C, D or match one of the choices."
                    }), 422

                parsed_questions.append({
                    'order_num': len(parsed_questions) + 1,
                    'question_text': q_text,
                    'option_a': opt_a,
                    'option_b': opt_b,
                    'option_c': opt_c,
                    'option_d': opt_d,
                    'correct_option': correct_letter,
                    'explanation': exp
                })

            if not parsed_questions:
                return jsonify({'success': False, 'message': 'No valid questions found in CSV.'}), 422

            quiz_title = custom_title or f"CSV Quiz: {file.filename.rsplit('.', 1)[0]}"
            quiz = Quiz(
                user_id=current_user.id,
                document_id=None,
                title=quiz_title,
                difficulty=custom_difficulty or 'Mixed',
                num_questions=len(parsed_questions)
            )
            db.session.add(quiz)
            db.session.flush()

            for q_data in parsed_questions:
                question = Question(
                    quiz_id=quiz.id,
                    order_num=q_data['order_num'],
                    question_text=q_data['question_text'],
                    option_a=q_data['option_a'],
                    option_b=q_data['option_b'],
                    option_c=q_data['option_c'],
                    option_d=q_data['option_d'],
                    correct_option=q_data['correct_option'],
                    explanation=q_data['explanation']
                )
                db.session.add(question)

            db.session.commit()

            return jsonify({
                'success': True,
                'message': f"Successfully imported {len(parsed_questions)} questions from CSV!",
                'quiz_id': quiz.id,
                'quiz_url': url_for('take_quiz_page', quiz_id=quiz.id)
            }), 201

        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': f"Error parsing CSV file: {str(e)}"}), 500

    @app.route('/api/quiz/create-manual', methods=['POST'])
    @login_required
    def api_create_manual_quiz():
        """Create a quiz directly by authoring questions manually."""
        data = request.get_json(silent=True) or {}
        title = data.get('title', '').strip()
        difficulty = data.get('difficulty', 'Mixed').strip()
        questions_input = data.get('questions', [])

        if not title:
            return jsonify({'success': False, 'message': 'Please enter a quiz title.'}), 400

        if not questions_input or not isinstance(questions_input, list):
            return jsonify({'success': False, 'message': 'At least 1 question is required.'}), 400

        validated_questions = []
        for i, q in enumerate(questions_input, start=1):
            q_text = (q.get('question_text') or '').strip()
            opt_a = (q.get('option_a') or '').strip()
            opt_b = (q.get('option_b') or '').strip()
            opt_c = (q.get('option_c') or '').strip()
            opt_d = (q.get('option_d') or '').strip()
            correct_opt = (q.get('correct_option') or '').strip().upper()
            exp = (q.get('explanation') or '').strip()

            if not q_text:
                return jsonify({'success': False, 'message': f'Question #{i}: Question text is required.'}), 400
            if not (opt_a and opt_b and opt_c and opt_d):
                return jsonify({'success': False, 'message': f'Question #{i}: All 4 options (A, B, C, D) are required.'}), 400
            if correct_opt not in ['A', 'B', 'C', 'D']:
                return jsonify({'success': False, 'message': f'Question #{i}: Please select which option is correct (A, B, C, or D).'}), 400

            validated_questions.append({
                'order_num': i,
                'question_text': q_text,
                'option_a': opt_a,
                'option_b': opt_b,
                'option_c': opt_c,
                'option_d': opt_d,
                'correct_option': correct_opt,
                'explanation': exp
            })

        try:
            quiz = Quiz(
                user_id=current_user.id,
                document_id=None,
                title=title,
                difficulty=difficulty or 'Mixed',
                num_questions=len(validated_questions)
            )
            db.session.add(quiz)
            db.session.flush()

            for q_data in validated_questions:
                question = Question(
                    quiz_id=quiz.id,
                    order_num=q_data['order_num'],
                    question_text=q_data['question_text'],
                    option_a=q_data['option_a'],
                    option_b=q_data['option_b'],
                    option_c=q_data['option_c'],
                    option_d=q_data['option_d'],
                    correct_option=q_data['correct_option'],
                    explanation=q_data['explanation']
                )
                db.session.add(question)

            db.session.commit()

            return jsonify({
                'success': True,
                'message': f"Quiz '{title}' created successfully with {len(validated_questions)} questions!",
                'quiz_id': quiz.id,
                'quiz_url': url_for('take_quiz_page', quiz_id=quiz.id)
            }), 201

        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': f"Failed to save custom quiz: {str(e)}"}), 500

    @app.route('/api/quiz/<int:quiz_id>', methods=['GET'])
    @login_required
    def api_get_quiz(quiz_id):
        """
        Retrieve quiz data for testing.
        CRITICAL SECURITY REQUIREMENT:
        Does NOT include 'correct_option' or 'explanation' to prevent cheating.
        """
        quiz = Quiz.query.filter_by(id=quiz_id, user_id=current_user.id).first_or_404()
        return jsonify({
            'success': True,
            'quiz': quiz.to_dict(user_id=current_user.id, include_questions=True, include_correct=False)
        })

    @app.route('/api/quiz/<int:quiz_id>/submit', methods=['POST'])
    @login_required
    def api_submit_quiz(quiz_id):
        """
        Submit quiz answers, compute score securely on server, and store attempt.
        """
        quiz = Quiz.query.filter_by(id=quiz_id, user_id=current_user.id).first_or_404()
        data = request.get_json() or {}
        submitted_answers = data.get('answers', {})  # Dict {question_id_str: 'A'}
        time_taken_seconds = int(data.get('time_taken', 0))

        questions = {q.id: q for q in quiz.questions}
        total_questions = len(questions)

        if total_questions == 0:
            return jsonify({'success': False, 'message': 'Quiz contains no questions.'}), 400

        correct_count = 0
        user_answer_records = []

        for q_id, question in questions.items():
            user_choice = submitted_answers.get(str(q_id), '').strip().upper()
            is_correct = (user_choice == question.correct_option.strip().upper())
            if is_correct:
                correct_count += 1

            user_answer_records.append({
                'question_id': q_id,
                'selected_option': user_choice if user_choice in ['A', 'B', 'C', 'D'] else None,
                'is_correct': is_correct
            })

        percentage = (correct_count / total_questions) * 100.0

        # Save Attempt
        attempt = QuizAttempt(
            quiz_id=quiz.id,
            user_id=current_user.id,
            score=correct_count,
            total_questions=total_questions,
            percentage=percentage,
            time_taken_seconds=time_taken_seconds
        )
        db.session.add(attempt)
        db.session.flush()

        for ua in user_answer_records:
            ans_row = UserAnswer(
                attempt_id=attempt.id,
                question_id=ua['question_id'],
                selected_option=ua['selected_option'],
                is_correct=ua['is_correct']
            )
            db.session.add(ans_row)

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Quiz submitted and evaluated successfully!',
            'attempt_id': attempt.id,
            'score': correct_count,
            'total_questions': total_questions,
            'percentage': round(percentage, 1),
            'result_url': url_for('quiz_result_page', quiz_id=quiz.id, attempt_id=attempt.id)
        })

    @app.route('/api/quiz/<int:quiz_id>/results/<int:attempt_id>', methods=['GET'])
    @login_required
    def api_get_quiz_results(quiz_id, attempt_id):
        """
        Retrieve complete quiz results, including full explanations and breakdown.
        """
        quiz = Quiz.query.filter_by(id=quiz_id, user_id=current_user.id).first_or_404()
        attempt = QuizAttempt.query.filter_by(id=attempt_id, quiz_id=quiz_id, user_id=current_user.id).first_or_404()

        answers_map = {ua.question_id: ua for ua in attempt.user_answers}

        breakdown = []
        for q in quiz.questions:
            ua = answers_map.get(q.id)
            breakdown.append({
                'question_id': q.id,
                'order_num': q.order_num,
                'question_text': q.question_text,
                'options': {
                    'A': q.option_a,
                    'B': q.option_b,
                    'C': q.option_c,
                    'D': q.option_d,
                },
                'selected_option': ua.selected_option if ua else None,
                'correct_option': q.correct_option,
                'is_correct': ua.is_correct if ua else False,
                'explanation': q.explanation
            })

        return jsonify({
            'success': True,
            'quiz_title': quiz.title,
            'difficulty': quiz.difficulty,
            'source_document': quiz.document.original_filename if quiz.document else 'Custom Notes',
            'attempt': attempt.to_dict(),
            'breakdown': breakdown
        })

    @app.route('/api/quizzes', methods=['GET'])
    @login_required
    def api_list_quizzes():
        """Retrieve list of quizzes for user."""
        quizzes = Quiz.query.filter_by(user_id=current_user.id).order_by(Quiz.created_at.desc()).all()
        return jsonify({
            'success': True,
            'quizzes': [q.to_dict(user_id=current_user.id) for q in quizzes]
        })

    @app.route('/api/quizzes/<int:quiz_id>', methods=['DELETE'])
    @login_required
    def api_delete_quiz(quiz_id):
        """Delete a quiz."""
        quiz = Quiz.query.filter_by(id=quiz_id, user_id=current_user.id).first_or_404()
        db.session.delete(quiz)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Quiz deleted successfully.'})

    # --- DASHBOARD & ANALYTICS APIS ---

    @app.route('/api/dashboard/stats', methods=['GET'])
    @login_required
    def api_dashboard_stats():
        """Dashboard overview statistics & recent activity."""
        user_id = current_user.id

        total_docs = Document.query.filter_by(user_id=user_id).count()
        total_quizzes = Quiz.query.filter_by(user_id=user_id).count()
        attempts = QuizAttempt.query.filter_by(user_id=user_id).all()

        questions_attempted = sum(a.total_questions for a in attempts)
        avg_score = round(sum(a.percentage for a in attempts) / len(attempts), 1) if attempts else 0.0

        # Recent activities (docs and attempts combined)
        recent_docs = Document.query.filter_by(user_id=user_id).order_by(Document.created_at.desc()).limit(4).all()
        recent_quizzes = Quiz.query.filter_by(user_id=user_id).order_by(Quiz.created_at.desc()).limit(4).all()
        recent_attempts = QuizAttempt.query.filter_by(user_id=user_id).order_by(QuizAttempt.completed_at.desc()).limit(5).all()

        return jsonify({
            'success': True,
            'stats': {
                'total_documents': total_docs,
                'quizzes_generated': total_quizzes,
                'questions_attempted': questions_attempted,
                'average_score': avg_score
            },
            'recent_documents': [d.to_dict() for d in recent_docs],
            'recent_quizzes': [q.to_dict(user_id=user_id) for q in recent_quizzes],
            'recent_attempts': [a.to_dict() for a in recent_attempts]
        })

    @app.route('/api/analytics', methods=['GET'])
    @login_required
    def api_analytics():
        """Student performance analytics."""
        user_id = current_user.id
        attempts = QuizAttempt.query.filter_by(user_id=user_id).order_by(QuizAttempt.completed_at.asc()).all()

        total_quizzes_completed = len(attempts)
        highest_score = round(max((a.percentage for a in attempts), default=0.0), 1)
        avg_score = round(sum(a.percentage for a in attempts) / total_quizzes_completed, 1) if attempts else 0.0
        total_questions = sum(a.total_questions for a in attempts)
        total_correct = sum(a.score for a in attempts)
        total_incorrect = total_questions - total_correct

        # Weekly trend (last 7 days)
        today = datetime.now(timezone.utc).date()
        daily_activity = { (today - timedelta(days=i)).strftime('%a'): 0 for i in range(6, -1, -1) }

        for a in attempts:
            if a.completed_at:
                a_date = a.completed_at.date()
                day_diff = (today - a_date).days
                if 0 <= day_diff < 7:
                    day_name = a_date.strftime('%a')
                    daily_activity[day_name] = daily_activity.get(day_name, 0) + 1

        return jsonify({
            'success': True,
            'total_quizzes_completed': total_quizzes_completed,
            'average_score': avg_score,
            'highest_score': highest_score,
            'total_questions_attempted': total_questions,
            'total_correct': total_correct,
            'total_incorrect': total_incorrect,
            'weekly_activity': daily_activity,
            'history': [a.to_dict() for a in attempts[-10:]]
        })

    return app


app = create_app()

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'True').lower() in ['true', '1', 'yes']
    print(f"\n=============================================")
    print(f" Quizly AI-Powered Platform Starting")
    print(f" Web UI: http://127.0.0.1:{port}")
    print(f"=============================================\n")
    app.run(host='127.0.0.1', port=port, debug=debug)
