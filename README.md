# Attendance Tracker System

A role-based attendance tracking web application built with Flask. Supports two user roles (Admin and Employee) with secure authentication, automatic time tracking, and mandatory task reporting.

## Features

### Employee
- Secure login with hashed passwords
- One-click **Time In** / **Time Out**
- Auto-captured datetime, day of week, and total working hours
- Mandatory task report on time-out
- Personal attendance history view

### Admin
- View attendance records for all employees
- View list of all registered employees with their details
- Role-based access control on every route

## Tech Stack

- **Backend:** Python 3.9+, Flask 3, Flask-Login, Flask-SQLAlchemy
- **Database:** SQLite (zero-config, file-based)
- **Frontend:** Jinja2 templates + Tailwind CSS (CDN)
- **Security:** Werkzeug password hashing

## Project Structure

```
attendance_tracker/
├── app.py                  # Flask app, routes, role guards
├── models.py               # SQLAlchemy models
├── seed.py                 # Database seeder
├── requirements.txt
├── .gitignore
├── README.md
└── templates/
    ├── base.html
    ├── login.html
    ├── employee_dashboard.html
    ├── admin_dashboard.html
    └── admin_employees.html
```

## Getting Started

### Prerequisites
- Python 3.9 or higher
- pip

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/attendance-tracker.git
   cd attendance-tracker
   ```

2. **Create a virtual environment**
   ```bash
   # macOS / Linux
   python3 -m venv venv
   source venv/bin/activate

   # Windows (PowerShell)
   python -m venv venv
   venv\Scripts\Activate.ps1
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Seed the database**
   ```bash
   python seed.py
   ```

5. **Run the app**
   ```bash
   python app.py
   ```

6. **Open your browser** to [http://localhost:5000](http://localhost:5000)

## Default Credentials

| Role     | Username | Password      |
|----------|----------|---------------|
| Admin    | admin    | admin123      |
| Employee | jdoe     | employee123   |
| Employee | asmith   | employee123   |

> ⚠️ Change these credentials before deploying to production.

## Screenshots

_Add screenshots of your login, employee dashboard, and admin dashboard here._

## Roadmap

- [ ] Admin form to create new employees
- [ ] CSV export of attendance records
- [ ] Date-range filtering on admin views
- [ ] Email notifications on long sessions
- [ ] Dockerfile for containerized deployment

## License

MIT — see [LICENSE](LICENSE) for details.

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you'd like to change.
