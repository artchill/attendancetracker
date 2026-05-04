from app import app
from models import db, User
from werkzeug.security import generate_password_hash


def seed():
    with app.app_context():
        db.create_all()

        if User.query.first():
            print('Database already has users — skipping seed.')
            return

        users = [
            User(
                username='admin',
                password_hash=generate_password_hash('admin123', method='pbkdf2:sha256'),
                fname='System',
                lname='Administrator',
                role='admin',
            ),
            User(
                username='jdoe',
                password_hash=generate_password_hash('employee123', method='pbkdf2:sha256'),
                fname='John',
                lname='Doe',
                role='employee',
            ),
            User(
                username='asmith',
                password_hash=generate_password_hash('employee123', method='pbkdf2:sha256'),
                fname='Alice',
                lname='Smith',
                role='employee',
            ),
        ]
        db.session.add_all(users)
        db.session.commit()

        print('Seeded successfully.')
        print('  Admin    -> username: admin   password: admin123')
        print('  Employee -> username: jdoe    password: employee123')
        print('  Employee -> username: asmith  password: employee123')


if __name__ == '__main__':
    seed()
