from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import (
    LoginManager, login_user, logout_user, login_required, current_user
)
from werkzeug.security import check_password_hash, generate_password_hash
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
        day=now.strftime('%A'),
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


@app.route('/admin/employees/new', methods=['GET', 'POST'])
@role_required('admin')
def admin_new_employee():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        fname = request.form.get('fname', '').strip()
        lname = request.form.get('lname', '').strip()
        role = request.form.get('role', '').strip()

        errors = []
        if not username or not password or not fname or not lname or not role:
            errors.append('All fields are required.')
        if role not in ('employee', 'admin'):
            errors.append('Invalid role selected.')
        if len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        if password != confirm_password:
            errors.append('Passwords do not match.')
        if User.query.filter_by(username=username).first():
            errors.append(f'Username "{username}" is already taken.')

        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template(
                'admin_new_employee.html',
                form_data={'username': username, 'fname': fname,
                           'lname': lname, 'role': role}
            )

        new_user = User(
            username=username,
            password_hash=generate_password_hash(password, method='pbkdf2:sha256'),
            fname=fname,
            lname=lname,
            role=role,
        )
        db.session.add(new_user)
        db.session.commit()
        flash(f'User "{username}" created successfully.', 'success')
        return redirect(url_for('admin_employees'))

    return render_template('admin_new_employee.html', form_data={})


@app.route('/admin/attendance/<int:record_id>/edit', methods=['GET', 'POST'])
@role_required('admin')
def admin_edit_attendance(record_id):
    record = Attendance.query.get_or_404(record_id)

    if request.method == 'POST':
        date_str = request.form.get('date', '').strip()
        time_in_str = request.form.get('time_in', '').strip()
        time_out_str = request.form.get('time_out', '').strip()
        task_report = request.form.get('task_report', '').strip()

        errors = []

        if not date_str or not time_in_str:
            errors.append('Date and Time In are required.')

        new_datetime_in = None
        new_datetime_out = None

        if not errors:
            try:
                new_datetime_in = datetime.strptime(
                    f'{date_str} {time_in_str}', '%Y-%m-%d %H:%M'
                )
            except ValueError:
                errors.append('Invalid Date or Time In format.')

        if time_out_str and not errors:
            try:
                new_datetime_out = datetime.strptime(
                    f'{date_str} {time_out_str}', '%Y-%m-%d %H:%M'
                )
                if new_datetime_out <= new_datetime_in:
                    errors.append('Time Out must be after Time In.')
            except ValueError:
                errors.append('Invalid Time Out format.')

        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('admin_edit_attendance.html', record=record)

        record.datetime_in = new_datetime_in
        record.day = new_datetime_in.strftime('%A')

        if new_datetime_out:
            record.datetime_out = new_datetime_out
            record.total_hours = round(
                (new_datetime_out - new_datetime_in).total_seconds() / 3600, 2
            )
        else:
            record.datetime_out = None
            record.total_hours = None

        record.task_report = task_report or None
        record.edited_at = datetime.now()
        record.edited_by_id = current_user.id

        db.session.commit()
        flash('Attendance record updated successfully.', 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('admin_edit_attendance.html', record=record)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5001)