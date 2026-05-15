from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import (
    LoginManager, login_user, logout_user, login_required, current_user
)
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, date, timedelta
from calendar import monthrange, month_name
from functools import wraps
from models import db, User, Attendance, LeaveDay

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


def build_month_calendar(user_id, year, month):
    """
    Return a list of dicts, one per day of the given month, with:
      date, day_name, status, attendance (or None), leave (or None), is_future
    Status is one of: 'present', 'absent', 'vl', 'sl', 'no_work', 'future'
    """
    days_in_month = monthrange(year, month)[1]
    today = date.today()

    # Pre-fetch all attendances and leaves for this user/month in 2 queries
    start = date(year, month, 1)
    end = date(year, month, days_in_month)

    attendances = Attendance.query.filter(
        Attendance.user_id == user_id,
        Attendance.datetime_in >= datetime.combine(start, datetime.min.time()),
        Attendance.datetime_in <= datetime.combine(end, datetime.max.time()),
    ).all()
    att_by_date = {}
    for a in attendances:
        att_by_date.setdefault(a.datetime_in.date(), []).append(a)

    leaves = LeaveDay.query.filter(
        LeaveDay.user_id == user_id,
        LeaveDay.date >= start,
        LeaveDay.date <= end,
    ).all()
    leave_by_date = {l.date: l for l in leaves}

    calendar = []
    for day_num in range(1, days_in_month + 1):
        d = date(year, month, day_num)
        is_weekend = d.weekday() >= 5  # 5=Sat, 6=Sun
        is_future = d > today

        day_attendances = att_by_date.get(d, [])
        leave = leave_by_date.get(d)

        if day_attendances:
            status = 'present'
        elif leave:
            status = leave.leave_type.lower()  # 'vl' or 'sl'
        elif is_future:
            status = 'future'
        elif is_weekend:
            status = 'no_work'
        else:
            status = 'absent'

        calendar.append({
            'date': d,
            'day_name': d.strftime('%A'),
            'status': status,
            'attendances': day_attendances,
            'leave': leave,
            'is_future': is_future,
            'is_weekend': is_weekend,
        })

    return calendar


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
    today = date.today()
    year = int(request.args.get('year', today.year))
    month = int(request.args.get('month', today.month))

    open_session = Attendance.query.filter_by(
        user_id=current_user.id, datetime_out=None
    ).first()

    calendar = build_month_calendar(current_user.id, year, month)

    return render_template(
        'employee_dashboard.html',
        open_session=open_session,
        calendar=calendar,
        year=year,
        month=month,
        month_name=month_name[month],
        available_years=range(today.year - 2, today.year + 2),
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
    flash(f'Timed in at {now.strftime("%I:%M %p")}.', 'success')
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


# ---------- Leave marking (shared) ----------

@app.route('/leave/mark', methods=['POST'])
@login_required
def mark_leave():
    """Mark a day as VL or SL. Employees can mark for themselves; admins for anyone."""
    target_user_id = int(request.form.get('user_id', current_user.id))
    date_str = request.form.get('date', '').strip()
    leave_type = request.form.get('leave_type', '').strip().upper()
    note = request.form.get('note', '').strip()
    redirect_to = request.form.get('redirect_to', 'employee_dashboard')
    redirect_kwargs = {}
    if redirect_to == 'admin_employee_tracker':
        redirect_kwargs['employee_id'] = target_user_id
        redirect_kwargs['year'] = request.form.get('year')
        redirect_kwargs['month'] = request.form.get('month')

    # Authorization
    if current_user.role != 'admin' and target_user_id != current_user.id:
        flash('You can only mark leave for yourself.', 'error')
        return redirect(url_for(redirect_to, **redirect_kwargs))

    if leave_type not in ('VL', 'SL'):
        flash('Leave type must be VL or SL.', 'error')
        return redirect(url_for(redirect_to, **redirect_kwargs))

    try:
        leave_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date.', 'error')
        return redirect(url_for(redirect_to, **redirect_kwargs))

    # Don't allow leave on a day there's already an attendance
    has_att = Attendance.query.filter(
        Attendance.user_id == target_user_id,
        Attendance.datetime_in >= datetime.combine(leave_date, datetime.min.time()),
        Attendance.datetime_in <= datetime.combine(leave_date, datetime.max.time()),
    ).first()
    if has_att:
        flash('Cannot mark leave — attendance already recorded for that day.', 'error')
        return redirect(url_for(redirect_to, **redirect_kwargs))

    existing = LeaveDay.query.filter_by(
        user_id=target_user_id, date=leave_date
    ).first()
    if existing:
        existing.leave_type = leave_type
        existing.note = note or None
        existing.marked_by_id = current_user.id
        existing.marked_at = datetime.now()
        flash(f'Updated {leave_date} to {leave_type}.', 'success')
    else:
        new_leave = LeaveDay(
            user_id=target_user_id,
            date=leave_date,
            leave_type=leave_type,
            note=note or None,
            marked_by_id=current_user.id,
        )
        db.session.add(new_leave)
        flash(f'Marked {leave_date} as {leave_type}.', 'success')

    db.session.commit()
    return redirect(url_for(redirect_to, **redirect_kwargs))


@app.route('/leave/<int:leave_id>/delete', methods=['POST'])
@login_required
def delete_leave(leave_id):
    leave = LeaveDay.query.get_or_404(leave_id)
    if current_user.role != 'admin' and leave.user_id != current_user.id:
        flash('Not allowed.', 'error')
        return redirect(url_for('employee_dashboard'))

    redirect_to = request.form.get('redirect_to', 'employee_dashboard')
    redirect_kwargs = {}
    if redirect_to == 'admin_employee_tracker':
        redirect_kwargs['employee_id'] = leave.user_id
        redirect_kwargs['year'] = request.form.get('year')
        redirect_kwargs['month'] = request.form.get('month')

    db.session.delete(leave)
    db.session.commit()
    flash('Leave entry removed.', 'success')
    return redirect(url_for(redirect_to, **redirect_kwargs))


# ---------- Admin ----------

@app.route('/admin/dashboard')
@role_required('admin')
def admin_dashboard():
    """Redirect to first employee's tracker, or show empty state if none."""
    first_employee = User.query.filter_by(role='employee').order_by(User.fname).first()
    if first_employee:
        return redirect(url_for('admin_employee_tracker',
                                employee_id=first_employee.id))
    return render_template('admin_dashboard_empty.html')


@app.route('/admin/employees/<int:employee_id>/tracker')
@role_required('admin')
def admin_employee_tracker(employee_id):
    employee = User.query.get_or_404(employee_id)
    today = date.today()
    year = int(request.args.get('year', today.year))
    month = int(request.args.get('month', today.month))

    calendar = build_month_calendar(employee_id, year, month)
    all_employees = User.query.filter_by(role='employee').order_by(User.fname).all()

    return render_template(
        'admin_employee_tracker.html',
        employee=employee,
        all_employees=all_employees,
        calendar=calendar,
        year=year,
        month=month,
        month_name=month_name[month],
        available_years=range(today.year - 2, today.year + 2),
    )


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
        return redirect(url_for('admin_employee_tracker',
                                employee_id=record.user_id))

    return render_template('admin_edit_attendance.html', record=record)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5001)