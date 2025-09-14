import os
import configparser
import sys
from getpass import getpass
from main import create_app
from models import User
from extensions import db
from sqlalchemy import create_engine, inspect as sqlalchemy_inspect
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
    temp_app = create_app()
    instance_path = temp_app.instance_path
    config_path = os.path.join(instance_path, 'nexus.conf')
    config = configparser.ConfigParser()

    if os.path.exists(config_path):
        config.read(config_path)

    while True:
        creds = get_db_credentials(config)
        conn_string, success = test_db_connection(creds)
        if success:
            if not config.has_section('database'):
                config.add_section('database')
            config.set('database', 'connection_string', conn_string)
            
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

    app = create_app()
    with app.app_context():
        engine = db.engine
        inspector = sqlalchemy_inspect(engine)
        model_table_names = set(db.metadata.tables.keys())
        existing_table_names = set(inspector.get_table_names())
        
        tables_exist = model_table_names.intersection(existing_table_names)
        
        should_create_schema = True
        if tables_exist:
            print("\n[!] Existing HiveMatrix Nexus tables found in the database.")
            print(f"    Found tables: {', '.join(sorted(list(tables_exist)))}")
            reset = input("    Do you want to drop all tables and re-initialize? (THIS WILL DELETE ALL DATA) (y/n): ").lower()
            if reset == 'y':
                print("    -> Dropping all tables...")
                db.drop_all()
                print("    -> Re-initializing schema...")
                db.create_all()
                print("    Database schema re-initialized.")
            else:
                should_create_schema = False
                print("    -> Skipping schema modification. Preserving existing data.")
        
        if should_create_schema and not tables_exist:
            print("Initializing the database schema...")
            db.create_all()
            print("Database schema initialized.")

        # --- Create Admin User ---
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

        # --- Create Service Account ---
        service_account = User.query.filter_by(username='service_account').first()
        if not service_account:
            service_account = User(
                username='service_account',
                email='service@nexus.local',
                permission_level='admin'
            )
            service_account.set_password(os.urandom(24).hex())
            db.session.add(service_account)
            db.session.commit()
            print("Created default service_account user.")
        else:
            print("Service account already exists.")

        if not service_account.api_key:
             service_account.regenerate_api_key()
             db.session.commit()

        service_api_key = service_account.api_key
        print("\n" + "="*50)
        print("IMPORTANT: Service Account API Key")
        print(f"Copy this key to your other HiveMatrix module config files:\n")
        print(f"{service_api_key}")
        print("="*50 + "\n")

        # Update the rest of the configuration file
        if not config.has_section('nexus_service'):
            config.add_section('nexus_service')
        config.set('nexus_service', 'api_key', service_api_key)

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

