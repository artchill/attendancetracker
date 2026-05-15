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
    role = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    attendances = db.relationship(
        'Attendance',
        foreign_keys='Attendance.user_id',
        backref='user',
        lazy=True,
    )
    leave_days = db.relationship(
        'LeaveDay',
        foreign_keys='LeaveDay.user_id',
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

    edited_by = db.relationship('User', foreign_keys=[edited_by_id])


class LeaveDay(db.Model):
    """Records VL (Vacation Leave) or SL (Sick Leave) for a given user+date."""
    __tablename__ = 'leave_days'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    leave_type = db.Column(db.String(10), nullable=False)  # 'VL' or 'SL'
    note = db.Column(db.Text, nullable=True)
    marked_at = db.Column(db.DateTime, default=datetime.utcnow)
    marked_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    marked_by = db.relationship('User', foreign_keys=[marked_by_id])

    __table_args__ = (
        db.UniqueConstraint('user_id', 'date', name='unique_user_date_leave'),
    )