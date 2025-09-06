import os
import configparser
from main import app
from models import User
from extensions import db

def init_db():
    """Creates the database tables, a default admin user, and configures the API key."""
    with app.app_context():
        db.create_all()
        print("Initialized the database.")

        admin_user = User.query.filter_by(username='admin').first()

        if not admin_user:
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

        # Ensure the admin user has an API key
        if not admin_user.api_key:
             admin_user.regenerate_api_key()
             db.session.commit()

        admin_api_key = admin_user.api_key
        print(f"\nAdmin API Key: {admin_api_key}\n")

        # Automatically create/update nexus.conf in the instance folder
        instance_path = app.instance_path
        config_path = os.path.join(instance_path, 'nexus.conf')

        config = configparser.ConfigParser()

        if os.path.exists(config_path):
            config.read(config_path)
            print(f"Updating configuration file at: {config_path}")
        else:
            print(f"Creating new configuration file at: {config_path}")

        if not config.has_section('nexus'):
            config.add_section('nexus')
        
        config.set('nexus', 'api_key', admin_api_key)

        # Add placeholder sections if they don't exist to guide the user
        if not config.has_section('freshservice'):
            config.add_section('freshservice')
            config.set('freshservice', 'api_key', 'YOUR_FRESHSERVICE_API_KEY')
            config.set('freshservice', 'domain', 'your-domain.freshservice.com')

        if not config.has_section('datto'):
            config.add_section('datto')
            config.set('datto', 'api_endpoint', 'https://zinfandel-api.centrastage.net')
            config.set('datto', 'public_key', 'YOUR_DATTO_PUBLIC_KEY')
            config.set('datto', 'secret_key', 'YOUR_DATTO_SECRET_KEY')

        with open(config_path, 'w') as configfile:
            config.write(configfile)
        
        print("`nexus.conf` has been created/updated with the admin API key.")


if __name__ == '__main__':
    init_db()
