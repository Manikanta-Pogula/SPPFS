# app/models.py
from datetime import datetime
from . import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'admin' or 'faculty'
    uploaded_files = db.relationship('UploadedFile', backref='uploader', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Subject(db.Model):
    __tablename__ = 'subjects'
    sub_code = db.Column(db.String(50), primary_key=True)   # e.g., CS-402
    sub_name = db.Column(db.String(255), nullable=False)
    branch = db.Column(db.String(50), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    semester = db.Column(db.Integer, nullable=False)
    marks = db.relationship('Mark', backref='subject', lazy=True)

class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    pin = db.Column(db.String(64), unique=True, nullable=False)  # e.g., 23189-CS-001
    name = db.Column(db.String(255), nullable=False)
    branch = db.Column(db.String(50), nullable=False)
    exam_year = db.Column(db.Integer, nullable=False)
    # relationships
    marks = db.relationship('Mark', backref='student', lazy=True)

class Mark(db.Model):
    __tablename__ = 'marks'
    id = db.Column(db.Integer, primary_key=True)

    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    sub_code = db.Column(db.String(50), db.ForeignKey('subjects.sub_code'), nullable=False)

    # component marks (these can be null initially and updated later)
    mid1 = db.Column(db.Float, nullable=True)     # out of 20
    mid2 = db.Column(db.Float, nullable=True)     # out of 20
    internal = db.Column(db.Float, nullable=True) # out of 20
    end_sem = db.Column(db.Float, nullable=True)  # out of 40

    attendance = db.Column(db.Float, nullable=True)  # percentage 0-100

    total = db.Column(db.Float, nullable=True)      # computed or provided
    semester = db.Column(db.Integer, nullable=False) # 1..6
    year = db.Column(db.Integer, nullable=False)

    # derived values
    subject_score = db.Column(db.Float, nullable=True)  # 0-100 normalized score for this subject
    risk = db.Column(db.String(10), nullable=True)      # 'low' / 'medium' / 'high'

    # optional provenance
    updated_on = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('student_id', 'sub_code', 'semester', name='uix_student_subject_sem'),
    )

class UploadedFile(db.Model):
    __tablename__ = 'uploaded_files'
    id = db.Column(db.Integer, primary_key=True)
    file_name = db.Column(db.String(255), nullable=False)         # user-provided name
    original_file_name = db.Column(db.String(255), nullable=False)
    exam_type = db.Column(db.String(20), nullable=False)         # 'mid1','mid2','semester'
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    uploaded_on = db.Column(db.DateTime, default=datetime.utcnow)
    note = db.Column(db.String(255), nullable=True)
    
    def __repr__(self):
        return f"<UploadedFile {self.id} {self.file_name}>"
    
class Institution(db.Model):
    __tablename__ = "institution"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f"<Institution {self.name}>"
