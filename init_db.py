import os
import sys
import configparser
from getpass import getpass
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError

# Load environment variables from .flaskenv
from dotenv import load_dotenv
load_dotenv('.flaskenv')

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from extensions import db
# Import models so SQLAlchemy knows about them
from models import Company, Contact, Asset, CompanyFeatureOverride, Location, DattoSiteLink

def get_db_credentials(config):
    """Prompts the user for PostgreSQL connection details."""
    print("\n--- PostgreSQL Database Configuration ---")
    
    db_details = {
        'host': 'localhost',
        'port': '5432',
        'user': 'codex_user',
        'dbname': 'codex_db'
    }
    
    # Load existing values if config exists
    if config.has_section('database_credentials'):
        db_details['host'] = config.get('database_credentials', 'db_host', fallback=db_details['host'])
        db_details['port'] = config.get('database_credentials', 'db_port', fallback=db_details['port'])
        db_details['dbname'] = config.get('database_credentials', 'db_dbname', fallback=db_details['dbname'])
        db_details['user'] = config.get('database_credentials', 'db_user', fallback=db_details['user'])

    host = input(f"Host [{db_details['host']}]: ") or db_details['host']
    port = input(f"Port [{db_details['port']}]: ") or db_details['port']
    dbname = input(f"Database Name [{db_details['dbname']}]: ") or db_details['dbname']
    user = input(f"User [{db_details['user']}]: ") or db_details['user']
    password = getpass("Password: ")

    return {
        'host': host,
        'port': port,
        'dbname': dbname,
        'user': user,
        'password': password
    }

def test_db_connection(creds):
    """Tests the database connection."""
    from urllib.parse import quote_plus
    
    # Properly escape the password in case it contains special characters
    escaped_password = quote_plus(creds['password'])
    conn_string = f"postgresql://{creds['user']}:{escaped_password}@{creds['host']}:{creds['port']}/{creds['dbname']}"
    
    try:
        engine = create_engine(conn_string)
        with engine.connect() as connection:
            print("\n✓ Database connection successful!")
            return conn_string, True
    except OperationalError as e:
        print(f"\n✗ Connection failed: {e}", file=sys.stderr)
        return None, False

def get_freshservice_config(config):
    """Prompts the user for Freshservice API configuration."""
    print("\n--- Freshservice Configuration ---")
    
    defaults = {
        'domain': 'your-domain.freshservice.com',
        'api_key': ''
    }
    
    if config.has_section('freshservice'):
        defaults['domain'] = config.get('freshservice', 'domain', fallback=defaults['domain'])
        defaults['api_key'] = config.get('freshservice', 'api_key', fallback=defaults['api_key'])
    
    print("Press Enter to keep current values or skip if not using Freshservice.")
    domain = input(f"Freshservice Domain [{defaults['domain']}]: ") or defaults['domain']
    
    if defaults['api_key'] and defaults['api_key'] not in ['', 'YOUR_FRESHSERVICE_API_KEY']:
        api_key_prompt = f"Freshservice API Key [****{defaults['api_key'][-4:]}]: "
    else:
        api_key_prompt = "Freshservice API Key [none]: "
    
    api_key_input = getpass(api_key_prompt)
    api_key = api_key_input if api_key_input else defaults['api_key']
    
    return {
        'domain': domain,
        'api_key': api_key
    }

def get_datto_config(config):
    """Prompts the user for Datto RMM API configuration."""
    print("\n--- Datto RMM Configuration ---")
    
    defaults = {
        'api_endpoint': 'https://zinfandel-api.centrastage.net',
        'public_key': '',
        'secret_key': ''
    }
    
    if config.has_section('datto'):
        defaults['api_endpoint'] = config.get('datto', 'api_endpoint', fallback=defaults['api_endpoint'])
        defaults['public_key'] = config.get('datto', 'public_key', fallback=defaults['public_key'])
        defaults['secret_key'] = config.get('datto', 'secret_key', fallback=defaults['secret_key'])
    
    print("Press Enter to keep current values or skip if not using Datto RMM.")
    print("\nCommon Datto API endpoints:")
    print("  - US: https://zinfandel-api.centrastage.net")
    print("  - EU: https://concord-api.centrastage.net")
    print("  - AU: https://pinotgrigio-api.centrastage.net")
    
    api_endpoint = input(f"\nDatto API Endpoint [{defaults['api_endpoint']}]: ") or defaults['api_endpoint']
    
    if defaults['public_key'] and defaults['public_key'] not in ['', 'YOUR_DATTO_PUBLIC_KEY']:
        public_key_prompt = f"Datto Public Key [****{defaults['public_key'][-4:]}]: "
    else:
        public_key_prompt = "Datto Public Key [none]: "
    
    public_key_input = input(public_key_prompt)
    public_key = public_key_input if public_key_input else defaults['public_key']
    
    if defaults['secret_key'] and defaults['secret_key'] not in ['', 'YOUR_DATTO_SECRET_KEY']:
        secret_key_prompt = f"Datto Secret Key [****{defaults['secret_key'][-4:]}]: "
    else:
        secret_key_prompt = "Datto Secret Key [none]: "
    
    secret_key_input = getpass(secret_key_prompt)
    secret_key = secret_key_input if secret_key_input else defaults['secret_key']
    
    return {
        'api_endpoint': api_endpoint,
        'public_key': public_key,
        'secret_key': secret_key
    }

def init_db():
    """Interactively configures and initializes the database."""
    instance_path = app.instance_path
    config_path = os.path.join(instance_path, 'codex.conf')
    
    # Use RawConfigParser to avoid interpolation issues with special characters
    config = configparser.RawConfigParser()

    config_exists = os.path.exists(config_path)
    if config_exists:
        config.read(config_path)
        print(f"\n✓ Existing configuration found: {config_path}")
        print("Press Enter to keep existing values, or type new values to update.")
    else:
        print(f"\n→ No existing configuration found. Creating new config: {config_path}")

    # Database configuration
    conn_string = None
    while True:
        creds = get_db_credentials(config)
        conn_string, success = test_db_connection(creds)
        if success:
            if not config.has_section('database'):
                config.add_section('database')
            config.set('database', 'connection_string', conn_string)
            
            if not config.has_section('database_credentials'):
                config.add_section('database_credentials')
            for key, val in creds.items():
                if key != 'password':  # Don't store password in plain text
                    config.set('database_credentials', f'db_{key}', val)
            break
        else:
            retry = input("\nWould you like to try again? (y/n): ").lower()
            if retry != 'y':
                sys.exit("Database configuration aborted.")

    # Freshservice configuration
    fs_config = get_freshservice_config(config)
    if not config.has_section('freshservice'):
        config.add_section('freshservice')
    config.set('freshservice', 'domain', fs_config['domain'])
    config.set('freshservice', 'api_key', fs_config['api_key'])

    # Datto configuration
    datto_config = get_datto_config(config)
    if not config.has_section('datto'):
        config.add_section('datto')
    config.set('datto', 'api_endpoint', datto_config['api_endpoint'])
    config.set('datto', 'public_key', datto_config['public_key'])
    config.set('datto', 'secret_key', datto_config['secret_key'])

    # Save configuration
    with open(config_path, 'w') as configfile:
        config.write(configfile)
    
    print(f"\n✓ Configuration saved to: {config_path}")

    # Initialize database schema
    with app.app_context():
        print("\nInitializing database schema...")
        tables = list(db.metadata.tables.keys())
        print(f"→ Creating {len(tables)} tables: {', '.join(tables)}")
        db.create_all()
        print("✓ Database schema initialized successfully!")

    print("\n" + "="*70)
    print(" 🎉 Codex Initialization Complete!")
    print("="*70)
    print("\nNext steps:")
    print("  1. (Optional) Review configuration: instance/codex.conf")
    print("  2. Sync data from external systems:")
    print("     → python pull_freshservice.py  # Sync companies & contacts")
    print("     → python pull_datto.py          # Sync assets")
    print("  3. Start the Codex service:")
    print("     → flask run --port=5010         # Development")
    print("     → python run.py                 # Production (Waitress)")
    print("\n  Access at: http://localhost:5010")
    print("  (Login via Core/Nexus gateway)")
    print("="*70)

if __name__ == '__main__':
    init_db()
