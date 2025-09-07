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

        # Add new section for service account credentials used by sync scripts
        if not config.has_section('nexus_auth'):
            config.add_section('nexus_auth')
            # Use the default admin credentials for the scripts to get a token
            config.set('nexus_auth', 'username', 'admin')
            config.set('nexus_auth', 'password', 'admin')
            print("Added [nexus_auth] section to config for scripts.")

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

        # --- Configure Plans and Features ---
        # Use generic placeholders. The user should customize these in nexus.conf
        DEFAULT_PLAN_NAMES = ["Generic Plan"]
        DEFAULT_FEATURES = {
            "Generic Feature": ["Option A", "Option B", "Not Included"]
        }

        if not config.has_section('plans'):
            print("Creating default 'plans' section in config.")
            config.add_section('plans')
            config.set('plans', 'plan_names', ','.join(DEFAULT_PLAN_NAMES))

        if not config.has_section('features'):
            print("Creating default 'features' section in config.")
            config.add_section('features')
            for feature, options in DEFAULT_FEATURES.items():
                config.set('features', feature.lower().replace(' ', '_'), ','.join(options))

        plan_names_str = config.get('plans', 'plan_names', fallback=','.join(DEFAULT_PLAN_NAMES))
        plan_names = [p.strip() for p in plan_names_str.split(',')]

        # Read feature keys from the config to ensure we use what's defined there
        feature_keys = []
        if config.has_section('features'):
            feature_keys = [key for key, value in config.items('features')]

        for plan_name in plan_names:
            section_name = f"plan_{plan_name.replace(' ', '_')}"
            if not config.has_section(section_name):
                print(f"Creating section for plan: {plan_name}")
                config.add_section(section_name)
                for key in feature_keys:
                    config.set(section_name, key, "Not Included")

        with open(config_path, 'w') as configfile:
            config.write(configfile)

        print("`nexus.conf` has been created/updated with the admin API key and plan structure.")


if __name__ == '__main__':
    init_db()
