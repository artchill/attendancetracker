from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import (
    LoginManager, login_user, logout_user, login_required, current_user
)
from werkzeug.security import check_password_hash
from datetime import datetime
from functools import wraps
from models import db, User, Attendance

app = Flask(__name__)
app.config['SECRET_KEY'] = 'change-this-secret-key-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///attendance.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def role_required(role):
    """Decorator: enforces a specific role on a route."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('login'))
            if current_user.role != role:
                flash('Access denied.', 'error')
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return wrapped
    return decorator


# ---------- Auth ----------

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for(
            'admin_dashboard' if current_user.role == 'admin'
            else 'employee_dashboard'
        ))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for(
                'admin_dashboard' if user.role == 'admin'
                else 'employee_dashboard'
            ))
        flash('Invalid username or password.', 'error')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ---------- Employee ----------

@app.route('/employee/dashboard')
@role_required('employee')
def employee_dashboard():
    open_session = Attendance.query.filter_by(
        user_id=current_user.id, datetime_out=None
    ).first()
    history = (Attendance.query
               .filter_by(user_id=current_user.id)
               .order_by(Attendance.datetime_in.desc())
               .all())
    return render_template(
        'employee_dashboard.html',
        open_session=open_session,
        history=history,
    )


@app.route('/employee/time-in', methods=['POST'])
@role_required('employee')
def time_in():
    existing = Attendance.query.filter_by(
        user_id=current_user.id, datetime_out=None
    ).first()
    if existing:
        flash('You already have an active session.', 'error')
        return redirect(url_for('employee_dashboard'))

    now = datetime.now()
    record = Attendance(
        user_id=current_user.id,
        datetime_in=now,
        day=now.strftime('%A'),  # auto-fill day name
    )
    db.session.add(record)
    db.session.commit()
    flash(f'Timed in at {now.strftime("%Y-%m-%d %H:%M:%S")}.', 'success')
    return redirect(url_for('employee_dashboard'))


@app.route('/employee/time-out', methods=['POST'])
@role_required('employee')
def time_out():
    task_report = request.form.get('task_report', '').strip()
    if not task_report:
        flash('A task report is required to time out.', 'error')
        return redirect(url_for('employee_dashboard'))

    session_ = Attendance.query.filter_by(
        user_id=current_user.id, datetime_out=None
    ).first()
    if not session_:
        flash('No active session found.', 'error')
        return redirect(url_for('employee_dashboard'))

    now = datetime.now()
    session_.datetime_out = now
    session_.total_hours = round(
        (now - session_.datetime_in).total_seconds() / 3600, 2
    )
    session_.task_report = task_report
    db.session.commit()
    flash(f'Timed out. Total hours: {session_.total_hours}', 'success')
    return redirect(url_for('employee_dashboard'))


# ---------- Admin ----------

@app.route('/admin/dashboard')
@role_required('admin')
def admin_dashboard():
    records = (db.session.query(Attendance, User)
               .join(User, Attendance.user_id == User.id)
               .order_by(Attendance.datetime_in.desc())
               .all())
    return render_template('admin_dashboard.html', records=records)


@app.route('/admin/employees')
@role_required('admin')
def admin_employees():
    employees = User.query.filter_by(role='employee').all()
    return render_template('admin_employees.html', employees=employees)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
