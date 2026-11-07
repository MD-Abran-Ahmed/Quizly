import os
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    password_hash = db.Column(db.String(255), nullable=True)
    google_id = db.Column(db.String(255), unique=True, nullable=True)
    avatar_url = db.Column(db.String(512), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    documents = db.relationship('Document', backref='user', lazy=True, cascade='all, delete-orphan')
    quizzes = db.relationship('Quiz', backref='user', lazy=True, cascade='all, delete-orphan')
    attempts = db.relationship('QuizAttempt', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'avatar_url': self.avatar_url or f"https://api.dicebear.com/7.x/initials/svg?seed={self.name}&backgroundColor=d6bc83&textColor=111110",
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Document(db.Model):
    __tablename__ = 'documents'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)  # in bytes
    page_count = db.Column(db.Integer, default=1)
    extracted_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    quizzes = db.relationship('Quiz', backref='document', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'original_filename': self.original_filename,
            'file_size': self.file_size,
            'file_size_formatted': self.format_size(),
            'page_count': self.page_count,
            'char_count': len(self.extracted_text) if self.extracted_text else 0,
            'created_at': self.created_at.strftime('%b %d, %Y %H:%M') if self.created_at else None,
            'quizzes_count': len(self.quizzes)
        }

    def format_size(self):
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"


class Quiz(db.Model):
    __tablename__ = 'quizzes'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id', ondelete='SET NULL'), nullable=True)
    title = db.Column(db.String(255), nullable=False)
    difficulty = db.Column(db.String(50), default='Mixed')
    num_questions = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    questions = db.relationship('Question', backref='quiz', lazy=True, cascade='all, delete-orphan', order_by='Question.order_num')
    attempts = db.relationship('QuizAttempt', backref='quiz', lazy=True, cascade='all, delete-orphan')

    def get_best_score(self, user_id=None):
        user_attempts = [a for a in self.attempts if (user_id is None or a.user_id == user_id)]
        if not user_attempts:
            return None
        return round(max(a.percentage for a in user_attempts), 1)

    def get_last_attempt(self, user_id=None):
        user_attempts = [a for a in self.attempts if (user_id is None or a.user_id == user_id)]
        if not user_attempts:
            return None
        return max(user_attempts, key=lambda a: a.completed_at)

    def to_dict(self, user_id=None, include_questions=False, include_correct=False):
        last_attempt = self.get_last_attempt(user_id)
        data = {
            'id': self.id,
            'title': self.title,
            'difficulty': self.difficulty,
            'num_questions': self.num_questions,
            'source_document': self.document.original_filename if self.document else 'Custom Notes',
            'document_id': self.document_id,
            'created_at': self.created_at.strftime('%b %d, %Y') if self.created_at else None,
            'total_attempts': len(self.attempts),
            'best_score': self.get_best_score(user_id),
            'last_attempt_date': last_attempt.completed_at.strftime('%b %d, %Y') if last_attempt else None,
            'last_score': round(last_attempt.percentage, 1) if last_attempt else None
        }
        if include_questions:
            data['questions'] = [q.to_dict(include_correct=include_correct) for q in self.questions]
        return data


class Question(db.Model):
    __tablename__ = 'questions'

    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id', ondelete='CASCADE'), nullable=False, index=True)
    order_num = db.Column(db.Integer, default=1)
    question_text = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.Text, nullable=False)
    option_b = db.Column(db.Text, nullable=False)
    option_c = db.Column(db.Text, nullable=False)
    option_d = db.Column(db.Text, nullable=False)
    correct_option = db.Column(db.String(5), nullable=False)  # 'A', 'B', 'C', 'D'
    explanation = db.Column(db.Text, nullable=True)

    def to_dict(self, include_correct=False):
        data = {
            'id': self.id,
            'order_num': self.order_num,
            'question_text': self.question_text,
            'options': {
                'A': self.option_a,
                'B': self.option_b,
                'C': self.option_c,
                'D': self.option_d
            }
        }
        if include_correct:
            data['correct_option'] = self.correct_option
            data['explanation'] = self.explanation
        return data


class QuizAttempt(db.Model):
    __tablename__ = 'quiz_attempts'

    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    score = db.Column(db.Integer, nullable=False)
    total_questions = db.Column(db.Integer, nullable=False)
    percentage = db.Column(db.Float, nullable=False)
    time_taken_seconds = db.Column(db.Integer, default=0)
    completed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user_answers = db.relationship('UserAnswer', backref='attempt', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'quiz_id': self.quiz_id,
            'quiz_title': self.quiz.title if self.quiz else 'Quiz',
            'score': self.score,
            'total_questions': self.total_questions,
            'percentage': round(self.percentage, 1),
            'time_taken_seconds': self.time_taken_seconds,
            'completed_at': self.completed_at.strftime('%b %d, %Y %H:%M') if self.completed_at else None
        }


class UserAnswer(db.Model):
    __tablename__ = 'user_answers'

    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('quiz_attempts.id', ondelete='CASCADE'), nullable=False, index=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False)
    selected_option = db.Column(db.String(5), nullable=True)  # 'A', 'B', 'C', 'D' or None
    is_correct = db.Column(db.Boolean, default=False)

    question = db.relationship('Question')

    def to_dict(self):
        return {
            'question_id': self.question_id,
            'question_text': self.question.question_text if self.question else '',
            'options': {
                'A': self.question.option_a,
                'B': self.question.option_b,
                'C': self.question.option_c,
                'D': self.question.option_d,
            } if self.question else {},
            'selected_option': self.selected_option,
            'correct_option': self.question.correct_option if self.question else '',
            'is_correct': self.is_correct,
            'explanation': self.question.explanation if self.question else ''
        }


def init_db(app):
    db.init_app(app)
    with app.app_context():
        os.makedirs(app.instance_path, exist_ok=True)
        db.create_all()
