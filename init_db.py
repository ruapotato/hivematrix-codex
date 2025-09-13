import os
import configparser
import sys
from getpass import getpass
from main import create_app
from models import User
from extensions import db
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

def get_db_credentials(config):
    """Prompts the user for PostgreSQL connection details."""
    print("--- PostgreSQL Database Configuration ---")
    print("Please provide the connection details for your PostgreSQL database.")
    
    db_details = {
        'host': 'localhost',
        'port': '5432',
        'user': 'nexus_user',
        'dbname': 'nexus_db'
    }
    
    # Pre-fill with existing config values if they exist
    if config.has_section('database_credentials'):
        for key, default_val in db_details.items():
            db_details[key] = config.get('database_credentials', f'db_{key}', fallback=default_val)

    host = input(f"Host [default: {db_details['host']}]: ") or db_details['host']
    port = input(f"Port [default: {db_details['port']}]: ") or db_details['port']
    dbname = input(f"Database Name [default: {db_details['dbname']}]: ") or db_details['dbname']
    user = input(f"User [default: {db_details['user']}]: ") or db_details['user']
    password = getpass("Password: ")

    return {
        'host': host,
        'port': port,
        'dbname': dbname,
        'user': user,
        'password': password
    }

def test_db_connection(creds):
    """Tests the database connection with the provided credentials."""
    conn_string = f"postgresql://{creds['user']}:{creds['password']}@{creds['host']}:{creds['port']}/{creds['dbname']}"
    try:
        engine = create_engine(conn_string)
        with engine.connect() as connection:
            print("\nDatabase connection successful!")
            return conn_string, True
    except OperationalError as e:
        print(f"\nConnection failed: {e}", file=sys.stderr)
        return conn_string, False

def init_db():
    """Interactively configures and initializes the database."""
    # Create a temporary app to get the instance path
    temp_app = create_app()
    instance_path = temp_app.instance_path
    config_path = os.path.join(instance_path, 'nexus.conf')
    config = configparser.ConfigParser()

    if os.path.exists(config_path):
        config.read(config_path)

    # Loop until a successful database connection is made
    while True:
        creds = get_db_credentials(config)
        conn_string, success = test_db_connection(creds)
        if success:
            if not config.has_section('database'):
                config.add_section('database')
            config.set('database', 'connection_string', conn_string)
            
            # Save credentials for future prompts, but not the password
            if not config.has_section('database_credentials'):
                config.add_section('database_credentials')
            config.set('database_credentials', 'db_host', creds['host'])
            config.set('database_credentials', 'db_port', creds['port'])
            config.set('database_credentials', 'db_name', creds['dbname'])
            config.set('database_credentials', 'db_user', creds['user'])

            with open(config_path, 'w') as configfile:
                config.write(configfile)
            break
        else:
            retry = input("Would you like to try again? (y/n): ").lower()
            if retry != 'y':
                sys.exit("Database configuration aborted.")

    # Now, create the full app with the verified config
    app = create_app()
    with app.app_context():
        print("Initializing the database schema...")
        db.create_all()
        print("Database schema initialized.")

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

        # Update the rest of the configuration file
        if not config.has_section('nexus'):
            config.add_section('nexus')
        config.set('nexus', 'api_key', admin_api_key)

        if not config.has_section('nexus_auth'):
            config.add_section('nexus_auth')
            config.set('nexus_auth', 'username', 'admin')
            config.set('nexus_auth', 'password', 'admin')

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

        print("`nexus.conf` has been successfully configured.")


if __name__ == '__main__':
    init_db()
