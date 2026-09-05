from app import db
from flask_login import UserMixin
from datetime import datetime
import json
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    password_hash = db.Column(db.String(512), nullable=True)
    role = db.Column(db.String(50), default='student')  # 'student' or 'admin'
    is_active = db.Column(db.Integer, default=1)
    created_at = db.Column(db.String(50), default=lambda: datetime.utcnow().isoformat())
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password) if self.password_hash else False

class Student(db.Model):
    __tablename__ = 'students'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    reg_no = db.Column(db.String(50), nullable=True)
    semester = db.Column(db.Integer, default=1)
    course = db.Column(db.String(100), default='BCA')
    college = db.Column(db.String(255), default='Marian College Kuttikkanam')
    enrolled_subjects = db.Column(db.Text, nullable=True)  # JSON-encoded list of enrolled subjects for active semester
    created_at = db.Column(db.String(50), default=lambda: datetime.utcnow().isoformat())
    
    # Relationships
    marks = db.relationship('Mark', backref='student', lazy=True, cascade='all, delete-orphan')
    insights = db.relationship('MLInsight', backref='student', lazy=True, cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='student', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'reg_no': self.reg_no,
            'semester': self.semester,
            'course': self.course,
            'college': self.college,
            'enrolled_subjects': json.loads(self.enrolled_subjects) if self.enrolled_subjects else [],
        }


class Mark(db.Model):
    __tablename__ = 'marks'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    exam_type = db.Column(db.String(20), nullable=False)  # ISA, LB, LD, CP, SEA1, SEA2
    score = db.Column(db.Float, nullable=False)
    max_score = db.Column(db.Float, default=100.0)
    semester = db.Column(db.Integer, nullable=True)
    entered_at = db.Column(db.String(50), default=lambda: datetime.utcnow().isoformat())

    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'subject': self.subject,
            'exam_type': self.exam_type,
            'score': self.score,
            'max_score': self.max_score,
            'semester': self.semester,
            'entered_at': self.entered_at
        }

class MLInsight(db.Model):
    __tablename__ = 'ml_insights'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    exam_type = db.Column(db.String(20), nullable=False)
    cluster = db.Column(db.String(50))  # Topper, Average, At-Risk
    risk_level = db.Column(db.String(20))  # info, warning, critical
    weak_subjects = db.Column(db.String(500))  # JSON-encoded list
    recommendation = db.Column(db.Text)
    created_at = db.Column(db.String(50), default=lambda: datetime.utcnow().isoformat())

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    exam_type = db.Column(db.String(20))
    message = db.Column(db.Text, nullable=False)
    source = db.Column(db.String(50), default='ml_engine')
    is_read = db.Column(db.Integer, default=0)  # 0 or 1
    sent_at = db.Column(db.String(50), default=lambda: datetime.utcnow().isoformat())

class Subject(db.Model):
    __tablename__ = 'subjects'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)
    program = db.Column(db.String(50), nullable=False, default='BCA')  # e.g. BCA
    semester = db.Column(db.Integer, nullable=False)                   # 1–6
    num_papers = db.Column(db.Integer, default=0)                      # past papers count
    credits = db.Column(db.Integer, default=4)                         # credit allocation
    is_elective = db.Column(db.Boolean, default=False)
    elective_group = db.Column(db.String(100), nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'program': self.program,
            'semester': self.semester,
            'num_papers': self.num_papers,
            'credits': self.credits,
            'is_elective': self.is_elective,
            'elective_group': self.elective_group,
        }


