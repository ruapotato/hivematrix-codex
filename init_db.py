from main import app, db, User

def init_db():
    """Creates the database tables and a default admin user."""
    with app.app_context():
        db.create_all()
        print("Initialized the database.")

        if not User.query.filter_by(username='admin').first():
            admin_user = User(
                username='admin',
                email='admin@nexus.local',
                permission_level='admin'
            )
            admin_user.set_password('admin')
            db.session.add(admin_user)
            db.session.commit()
            print("Created default admin user (admin/admin).")
        else:
            print("Admin user already exists.")

if __name__ == '__main__':
    init_db()
