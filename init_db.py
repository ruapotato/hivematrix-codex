#!/usr/bin/env python3
"""
Codex Database Initialization and Migration Script

This script handles both initial setup and schema migrations for production deployments.

Features:
- Interactive configuration setup (database, Freshservice, Datto)
- Intelligent schema migrations (adds new columns without data loss)
- Safe for production use - preserves existing data
- Can be run multiple times safely (idempotent)

Usage:
    python init_db.py                    # Interactive setup
    python init_db.py --test             # Non-interactive: use defaults and test
    python init_db.py --migrate-only     # Skip config, just migrate schema
    python init_db.py --force-rebuild    # Nuclear option: drop and recreate (DEV ONLY)
"""

import os
import sys
import argparse
import configparser
from getpass import getpass
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
from dotenv import load_dotenv

load_dotenv('.flaskenv')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from extensions import db
# Import ALL models so SQLAlchemy knows about them
from models import (
    Company, Contact, Asset, CompanyFeatureOverride, Location,
    DattoSiteLink, TicketDetail, SyncJob
)


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
    print("Codex is the ONLY service that connects to Freshservice.")
    print("All other services (Ledger, KnowledgeTree) pull data from Codex.")

    defaults = {
        'domain': 'your-domain.freshservice.com',
        'api_key': ''
    }

    if config.has_section('freshservice'):
        defaults['domain'] = config.get('freshservice', 'domain', fallback=defaults['domain'])
        defaults['api_key'] = config.get('freshservice', 'api_key', fallback=defaults['api_key'])

    print("\nPress Enter to keep current values or skip if not using Freshservice.")
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
    print("Codex is the ONLY service that connects to Datto RMM.")
    print("All other services (Ledger, KnowledgeTree) pull asset data from Codex.")

    defaults = {
        'api_endpoint': 'https://zinfandel-api.centrastage.net',
        'public_key': '',
        'secret_key': ''
    }

    if config.has_section('datto'):
        defaults['api_endpoint'] = config.get('datto', 'api_endpoint', fallback=defaults['api_endpoint'])
        defaults['public_key'] = config.get('datto', 'public_key', fallback=defaults['public_key'])
        defaults['secret_key'] = config.get('datto', 'secret_key', fallback=defaults['secret_key'])

    print("\nPress Enter to keep current values or skip if not using Datto RMM.")
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


def migrate_schema():
    """
    Intelligently migrates database schema without losing data.

    This function:
    1. Inspects existing tables and columns
    2. Compares with models defined in models.py
    3. Adds missing columns (with defaults)
    4. Creates missing tables
    5. Does NOT drop columns or tables (safe for production)
    """
    print("\n" + "="*80)
    print("DATABASE SCHEMA MIGRATION")
    print("="*80)

    with app.app_context():
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()

        print(f"\nFound {len(existing_tables)} existing tables in database")

        # Get all tables defined in models
        model_tables = db.metadata.tables

        # Track changes
        tables_created = []
        columns_added = []

        # Create tables in dependency order (association tables last)
        # First, create all base tables (no foreign keys to other app tables)
        base_tables = []
        association_tables = []

        for table_name, table in model_tables.items():
            # Association tables typically have multiple foreign keys and no primary key of their own
            # or have 'link' in the name
            if 'link' in table_name.lower() or len([c for c in table.columns if c.foreign_keys]) >= 2:
                association_tables.append((table_name, table))
            else:
                base_tables.append((table_name, table))

        # Create base tables first
        for table_name, table in base_tables:
            if table_name not in existing_tables:
                # Table doesn't exist - create it
                print(f"\n→ Creating new table: {table_name}")
                table.create(db.engine)
                tables_created.append(table_name)
            else:
                # Table exists - check for missing columns (below)
                pass

        # Then create association tables
        for table_name, table in association_tables:
            if table_name not in existing_tables:
                # Table doesn't exist - create it
                print(f"\n→ Creating new association table: {table_name}")
                table.create(db.engine)
                tables_created.append(table_name)
            else:
                # Table exists - check for missing columns (below)
                pass

        # Now check all tables for missing columns
        for table_name, table in base_tables + association_tables:
            if table_name in existing_tables:
                # Table exists - check for missing columns
                existing_columns = {col['name'] for col in inspector.get_columns(table_name)}
                model_columns = {col.name for col in table.columns}
                missing_columns = model_columns - existing_columns

                if missing_columns:
                    print(f"\n→ Updating table '{table_name}' - adding {len(missing_columns)} columns:")
                    for col_name in missing_columns:
                        col = table.columns[col_name]
                        col_type = col.type.compile(db.engine.dialect)

                        # Build ALTER TABLE statement
                        nullable = "NULL" if col.nullable else "NOT NULL"
                        default = ""

                        # Add default value if specified
                        if col.default is not None:
                            if hasattr(col.default, 'arg'):
                                # Column default (e.g., default=True)
                                default_val = col.default.arg
                                if isinstance(default_val, str):
                                    default = f"DEFAULT '{default_val}'"
                                elif isinstance(default_val, bool):
                                    default = f"DEFAULT {str(default_val).upper()}"
                                else:
                                    default = f"DEFAULT {default_val}"

                        # For NOT NULL columns without default, make them nullable for migration
                        if not col.nullable and not default:
                            nullable = "NULL"
                            print(f"   ⚠ Column '{col_name}' is NOT NULL but has no default - making nullable for safety")

                        sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type} {default} {nullable}"

                        try:
                            with db.engine.connect() as conn:
                                conn.execute(text(sql))
                                conn.commit()
                            print(f"   ✓ Added column: {col_name} ({col_type})")
                            columns_added.append(f"{table_name}.{col_name}")
                        except Exception as e:
                            print(f"   ✗ Failed to add column {col_name}: {e}")

        # Summary
        print("\n" + "="*80)
        print("MIGRATION SUMMARY")
        print("="*80)

        if tables_created:
            print(f"\n✓ Created {len(tables_created)} new table(s):")
            for t in tables_created:
                print(f"  - {t}")
        else:
            print("\n• No new tables created")

        if columns_added:
            print(f"\n✓ Added {len(columns_added)} new column(s):")
            for c in columns_added:
                print(f"  - {c}")
        else:
            print("\n• No new columns added")

        if not tables_created and not columns_added:
            print("\n✓ Schema is up to date - no changes needed")

        print("\n" + "="*80)


def force_rebuild():
    """
    DANGEROUS: Drops all tables and recreates from scratch.
    Only use in development!
    """
    print("\n" + "!"*80)
    print("⚠ WARNING: FORCE REBUILD MODE")
    print("!"*80)
    print("\nThis will DELETE ALL DATA in the database!")
    print("This should ONLY be used in development environments.")
    print("\nType 'DELETE ALL DATA' to confirm:")

    confirmation = input("> ")
    if confirmation != "DELETE ALL DATA":
        print("\nAborted.")
        sys.exit(0)

    print("\n→ Dropping all tables...")
    with app.app_context():
        db.drop_all()
        print("✓ All tables dropped")

        print("\n→ Creating fresh schema...")
        db.create_all()
        print("✓ Schema recreated")

    print("\n✓ Force rebuild complete")


def init_db(migrate_only=False, force=False, test_mode=False):
    """Main initialization function."""
    print("\n" + "="*80)
    print("CODEX DATABASE INITIALIZATION")
    print("="*80)

    if force:
        force_rebuild()
        return

    instance_path = app.instance_path
    config_path = os.path.join(instance_path, 'codex.conf')

    # Use RawConfigParser to avoid interpolation issues with special characters
    config = configparser.RawConfigParser()

    if test_mode:
        # Non-interactive test mode - use defaults and show errors
        print("\n→ Running in TEST MODE (non-interactive)")

        # Read existing config if it exists to preserve Freshservice/Datto settings
        if os.path.exists(config_path):
            config.read(config_path)
            print(f"→ Loaded existing configuration from: {config_path}")

        print("Using default credentials:")

        default_creds = {
            'host': 'localhost',
            'port': '5432',
            'dbname': 'codex_db',
            'user': 'codex_user',
            'password': 'Integotec@123'
        }

        print(f"  Host: {default_creds['host']}")
        print(f"  Port: {default_creds['port']}")
        print(f"  Database: {default_creds['dbname']}")
        print(f"  User: {default_creds['user']}")
        print(f"  Password: {'*' * len(default_creds['password'])}")

        print("\nTesting database connection...")
        conn_string, success = test_db_connection(default_creds)

        if success:
            print("\n✓ Connection test PASSED")
            print(f"✓ Connection string: {conn_string.replace(default_creds['password'], '***')}")

            # Save the config
            if not config.has_section('database'):
                config.add_section('database')
            config.set('database', 'connection_string', conn_string)

            if not config.has_section('database_credentials'):
                config.add_section('database_credentials')
            for key, val in default_creds.items():
                if key != 'password':
                    config.set('database_credentials', f'db_{key}', val)

            # Add Freshservice section (with placeholder values in test mode)
            if not config.has_section('freshservice'):
                config.add_section('freshservice')
            if not config.has_option('freshservice', 'domain'):
                config.set('freshservice', 'domain', 'your-domain.freshservice.com')
            if not config.has_option('freshservice', 'api_key'):
                config.set('freshservice', 'api_key', 'YOUR_FRESHSERVICE_API_KEY')

            # Add Datto section (with placeholder values in test mode)
            if not config.has_section('datto'):
                config.add_section('datto')
            if not config.has_option('datto', 'api_endpoint'):
                config.set('datto', 'api_endpoint', 'https://zinfandel-api.centrastage.net')
            if not config.has_option('datto', 'public_key'):
                config.set('datto', 'public_key', 'YOUR_DATTO_PUBLIC_KEY')
            if not config.has_option('datto', 'secret_key'):
                config.set('datto', 'secret_key', 'YOUR_DATTO_SECRET_KEY')

            # Save minimal config
            os.makedirs(instance_path, exist_ok=True)
            with open(config_path, 'w') as configfile:
                config.write(configfile)
            print(f"✓ Configuration saved to: {config_path}")

            # Run migration
            migrate_schema()
            print("\n✓ Test mode complete - database is ready!")
            return
        else:
            print("\n✗ Connection test FAILED")
            print("Please check:")
            print("  1. PostgreSQL is running: sudo systemctl status postgresql")
            print("  2. User exists: sudo -u postgres psql -c \"\\du codex_user\"")
            print("  3. Database exists: sudo -u postgres psql -c \"\\l codex_db\"")
            print("  4. Password is correct: Integotec@123")
            sys.exit(1)

    if not migrate_only:
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
    else:
        # Migrate-only mode: load existing config
        if os.path.exists(config_path):
            config.read(config_path)
            print(f"\n✓ Using existing configuration: {config_path}")
        else:
            print(f"\n✗ No configuration found at {config_path}")
            print("Run without --migrate-only to create configuration first")
            sys.exit(1)

    # Run schema migration
    migrate_schema()

    print("\n" + "="*80)
    print(" 🎉 Codex Initialization Complete!")
    print("="*80)
    print("\nIMPORTANT: Codex is the central data hub for HiveMatrix")
    print("  - Codex syncs from Freshservice & Datto")
    print("  - Ledger pulls billing data from Codex")
    print("  - KnowledgeTree pulls support context from Codex")
    print("="*80)
    print("\nNext steps:")
    print("  1. (Optional) Review configuration: instance/codex.conf")
    print("  2. Sync data from external systems (via Codex dashboard or CLI):")
    print("     → python pull_freshservice.py          # Companies & contacts")
    print("     → python pull_datto.py                 # Assets & backup data")
    print("     → python sync_tickets_from_freshservice.py  # Ticket history")
    print("  3. Start the Codex service:")
    print("     → flask run --port=5010         # Development")
    print("     → python run.py                 # Production (Waitress)")
    print("\n  Access at: http://localhost:5010")
    print("  (Login via Core/Nexus gateway)")
    print("="*80)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Initialize or migrate Codex database schema',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--migrate-only',
        action='store_true',
        help='Skip configuration, only run schema migration'
    )
    parser.add_argument(
        '--force-rebuild',
        action='store_true',
        help='DANGEROUS: Drop all tables and rebuild (DEV ONLY)'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Non-interactive mode: use defaults and test connection'
    )

    args = parser.parse_args()

    init_db(migrate_only=args.migrate_only, force=args.force_rebuild, test_mode=args.test)
