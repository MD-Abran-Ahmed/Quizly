import os
import sys
import io
import json

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import fitz
from app import create_app
from database import db, User, Document, Quiz, Question, QuizAttempt, UserAnswer

@pytest.fixture
def app():
    os.environ['DATABASE_URI'] = 'sqlite:///:memory:'
    os.environ['SECRET_KEY'] = 'test-secret-key'
    app = create_app()
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False
    })

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def auth_client(client, app):
    # Register and login a test user
    with app.app_context():
        user = User(name="Test Student", email="student@test.com")
        user.set_password("securepassword123")
        db.session.add(user)
        db.session.commit()

    # Login
    res = client.post('/api/auth/login', json={
        'email': 'student@test.com',
        'password': 'securepassword123'
    })
    assert res.status_code == 200
    return client

def create_sample_pdf_bytes():
    """Create an in-memory PDF using PyMuPDF with rich text content."""
    doc = fitz.open()
    page = doc.new_page()
    text = (
        "Cellular Biology Overview\n\n"
        "Mitochondria are membrane-bound cell organelles that generate most of the chemical energy "
        "needed to power the biochemical reactions of eukaryotic cells. Chemical energy produced by the "
        "mitochondria is stored in a small molecule called adenosine triphosphate or ATP.\n\n"
        "The nucleus is an organelle found in eukaryotic cells that contains the genetic material or DNA.\n\n"
        "Ribosomes are macromolecular machines found within all cells that perform biological protein synthesis.\n\n"
        "Question: What molecule stores chemical energy produced by the mitochondria?\n"
        "Answer: Adenosine triphosphate (ATP)\n"
    )
    page.insert_text((50, 72), text, fontsize=11)
    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes

def test_landing_page(client):
    res = client.get('/')
    assert res.status_code == 200
    assert b"Quizly" in res.data
    assert b"Your Notes. Your Knowledge. Your Quiz." in res.data

def test_unauthenticated_protection(client):
    # Protected views should redirect to login
    for path in ['/dashboard', '/upload', '/documents', '/quizzes', '/analytics']:
        res = client.get(path)
        assert res.status_code == 302
        assert '/login' in res.location

def test_user_registration_and_login(client):
    # Register
    reg_res = client.post('/api/auth/register', json={
        'name': 'Ada Lovelace',
        'email': 'ada@quizly.ai',
        'password': 'analyticalengine'
    })
    assert reg_res.status_code == 200
    reg_data = json.loads(reg_res.data)
    assert reg_data['success'] is True

    # Check authenticated endpoint
    me_res = client.get('/api/auth/me')
    assert me_res.status_code == 200
    me_data = json.loads(me_res.data)
    assert me_data['authenticated'] is True
    assert me_data['user']['name'] == 'Ada Lovelace'

def test_invalid_file_upload(auth_client):
    # Non-pdf file
    res = auth_client.post('/api/documents/upload', data={
        'file': (io.BytesIO(b"Just plain text file"), 'test.txt')
    }, content_type='multipart/form-data')
    assert res.status_code == 400
    data = json.loads(res.data)
    assert "Only PDF" in data['message']

    # Empty file
    res = auth_client.post('/api/documents/upload', data={
        'file': (io.BytesIO(b""), 'empty.pdf')
    }, content_type='multipart/form-data')
    assert res.status_code == 422
    data = json.loads(res.data)
    assert "empty" in data['message'].lower()

def test_pdf_upload_and_extraction(auth_client, app):
    pdf_bytes = create_sample_pdf_bytes()
    data = {
        'file': (io.BytesIO(pdf_bytes), 'biology_notes.pdf')
    }
    res = auth_client.post('/api/documents/upload', data=data, content_type='multipart/form-data')
    assert res.status_code == 201
    res_data = json.loads(res.data)
    assert res_data['success'] is True
    assert 'document' in res_data
    assert res_data['document']['original_filename'] == 'biology_notes.pdf'
    assert res_data['document']['page_count'] == 1

def test_quiz_generation_and_taking_flow(auth_client, app):
    # 1. Upload PDF
    pdf_bytes = create_sample_pdf_bytes()
    upload_res = auth_client.post('/api/documents/upload', data={
        'file': (io.BytesIO(pdf_bytes), 'biology_notes.pdf')
    }, content_type='multipart/form-data')
    doc_id = json.loads(upload_res.data)['document']['id']

    # 2. Generate Quiz
    gen_res = auth_client.post('/api/quiz/generate', json={
        'document_id': doc_id,
        'num_questions': 5,
        'difficulty': 'Medium',
        'title': 'Cell Biology Test',
        'include_explanations': True
    })
    assert gen_res.status_code == 201
    gen_data = json.loads(gen_res.data)
    assert gen_data['success'] is True
    quiz_id = gen_data['quiz_id']

    # 3. Fetch Quiz (ensure correct answers are NOT leaked to client before submit)
    quiz_res = auth_client.get(f'/api/quiz/{quiz_id}')
    assert quiz_res.status_code == 200
    quiz_data = json.loads(quiz_res.data)['quiz']
    assert len(quiz_data['questions']) > 0
    first_q = quiz_data['questions'][0]
    assert 'correct_option' not in first_q
    assert 'explanation' not in first_q
    assert 'options' in first_q
    assert 'A' in first_q['options']

    # 4. Submit Answers
    answers = {}
    for q in quiz_data['questions']:
        answers[str(q['id'])] = 'A'

    submit_res = auth_client.post(f'/api/quiz/{quiz_id}/submit', json={
        'answers': answers,
        'time_taken': 45
    })
    assert submit_res.status_code == 200
    submit_data = json.loads(submit_res.data)
    assert submit_data['success'] is True
    assert 'attempt_id' in submit_data
    assert submit_data['total_questions'] == len(quiz_data['questions'])

    # 5. Review Results
    attempt_id = submit_data['attempt_id']
    results_res = auth_client.get(f'/api/quiz/{quiz_id}/results/{attempt_id}')
    assert results_res.status_code == 200
    results_data = json.loads(results_res.data)
    assert results_data['success'] is True
    assert len(results_data['breakdown']) == len(quiz_data['questions'])
    assert 'correct_option' in results_data['breakdown'][0]
    assert 'explanation' in results_data['breakdown'][0]

    # 6. Dashboard stats & analytics check
    stats_res = auth_client.get('/api/dashboard/stats')
    assert stats_res.status_code == 200
    stats_data = json.loads(stats_res.data)['stats']
    assert stats_data['total_documents'] == 1
    assert stats_data['quizzes_generated'] == 1
    assert stats_data['questions_attempted'] == len(quiz_data['questions'])

    analytics_res = auth_client.get('/api/analytics')
    assert analytics_res.status_code == 200
    analytics_data = json.loads(analytics_res.data)
    assert analytics_data['total_quizzes_completed'] == 1
    assert 'weekly_activity' in analytics_data

    # 7. Document deletion test
    del_doc = auth_client.delete(f'/api/documents/{doc_id}')
    assert del_doc.status_code == 200
    del_data = json.loads(del_doc.data)
    assert del_data['success'] is True


def test_logout_clears_session(auth_client):
    # Verify user is currently logged in
    me_res = auth_client.get('/api/auth/me')
    assert me_res.status_code == 200
    assert json.loads(me_res.data)['authenticated'] is True

    # Call logout
    logout_res = auth_client.get('/logout')
    assert logout_res.status_code == 302
    assert '/login' in logout_res.location

    # Verify user is now logged out
    me_after = auth_client.get('/api/auth/me')
    assert me_after.status_code == 200
    assert json.loads(me_after.data)['authenticated'] is False


def test_demo_csv_download(client):
    res = client.get('/api/quiz/demo-csv')
    assert res.status_code == 200
    assert b"question,option_a,option_b,option_c,option_d,correct_option,explanation" in res.data


def test_csv_upload_quiz(auth_client):
    csv_content = (
        'question,option_a,option_b,option_c,option_d,correct_option,explanation\n'
        '"What is 2+2?","3","4","5","6","B","Basic arithmetic: 2+2=4"\n'
        '"Which gas do plants absorb?","Oxygen","Carbon Dioxide","Nitrogen","Helium","B","Photosynthesis consumes CO2"\n'
    )
    res = auth_client.post('/api/quiz/upload-csv', data={
        'file': (io.BytesIO(csv_content.encode('utf-8')), 'test_questions.csv'),
        'title': 'Math and Science Test',
        'difficulty': 'Easy'
    }, content_type='multipart/form-data')

    assert res.status_code == 201
    data = json.loads(res.data)
    assert data['success'] is True
    assert 'quiz_id' in data

    # Verify quiz was created and can be retrieved
    quiz_id = data['quiz_id']
    get_res = auth_client.get(f'/api/quiz/{quiz_id}')
    assert get_res.status_code == 200
    q_data = json.loads(get_res.data)['quiz']
    assert len(q_data['questions']) == 2
    assert q_data['title'] == 'Math and Science Test'


def test_manual_quiz_creation(auth_client):
    payload = {
        'title': 'Manual Physics Quiz',
        'difficulty': 'Hard',
        'questions': [
            {
                'question_text': 'What is the speed of light in vacuum?',
                'option_a': '300,000 km/s',
                'option_b': '150,000 km/s',
                'option_c': '500,000 km/s',
                'option_d': '1,000,000 km/s',
                'correct_option': 'A',
                'explanation': 'Speed of light c is approximately 299,792 km/s.'
            }
        ]
    }
    res = auth_client.post('/api/quiz/create-manual', json=payload)
    assert res.status_code == 201
    data = json.loads(res.data)
    assert data['success'] is True
    assert 'quiz_id' in data

    quiz_id = data['quiz_id']
    get_res = auth_client.get(f'/api/quiz/{quiz_id}')
    assert get_res.status_code == 200
    q_data = json.loads(get_res.data)['quiz']
    assert len(q_data['questions']) == 1
    assert q_data['title'] == 'Manual Physics Quiz'
