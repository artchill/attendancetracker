from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    fname = db.Column(db.String(80), nullable=False)
    lname = db.Column(db.String(80), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'admin' or 'employee'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Tell SQLAlchemy explicitly: "attendances" uses Attendance.user_id
    attendances = db.relationship(
        'Attendance',
        foreign_keys='Attendance.user_id',
        backref='user',
        lazy=True,
    )


class Attendance(db.Model):
    __tablename__ = 'attendances'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    datetime_in = db.Column(db.DateTime, nullable=False)
    datetime_out = db.Column(db.DateTime, nullable=True)
    day = db.Column(db.String(20), nullable=False)
    total_hours = db.Column(db.Float, nullable=True)
    task_report = db.Column(db.Text, nullable=True)
    edited_at = db.Column(db.DateTime, nullable=True)
    edited_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # The admin who last edited this record (separate FK)
    edited_by = db.relationship('User', foreign_keys=[edited_by_id])