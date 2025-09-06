import requests
import base64
import os
import sys
import time
import configparser
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Company, User as NexusUser, Contact

def get_db_session():
    """Creates a new SQLAlchemy session."""
    # The instance path is passed as an environment variable by the scheduler
    instance_path = os.environ.get('NEXUS_INSTANCE_PATH', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance'))
    db_path = os.path.join(instance_path, 'nexus_brainhair.db')
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found at {db_path}")
    # Add a timeout to the connection to prevent database locked errors
    engine = create_engine(f'sqlite:///{db_path}', connect_args={'timeout': 15})
    Session = sessionmaker(bind=engine)
    return Session()

def get_config():
    """Loads the configuration from nexus.conf in the instance folder."""
    instance_path = os.environ.get('NEXUS_INSTANCE_PATH', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance'))
    config_path = os.path.join(instance_path, 'nexus.conf')
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found at {config_path}")

    print(f"Loading configuration from: {config_path}")
    config = configparser.ConfigParser()
    config.read(config_path)
    return config

# --- API Functions ---
def get_all_companies(base_url, headers):
    print("Fetching companies from Freshservice...")
    all_companies, page = [], 1
    endpoint = f"{base_url}/api/v2/departments"
    while True:
        try:
            params = {'page': page, 'per_page': 100}
            response = requests.get(endpoint, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            companies_on_page = data.get('departments', [])
            if not companies_on_page: break
            all_companies.extend(companies_on_page)
            page += 1
        except requests.exceptions.RequestException as e:
            print(f"Error fetching Freshservice companies: {e}", file=sys.stderr)
            return None
    print(f" Found {len(all_companies)} companies in Freshservice.")
    return all_companies

def get_all_users(base_url, headers):
    print("\nFetching all users from Freshservice...")
    all_users, page = [], 1
    endpoint = f"{base_url}/api/v2/requesters"
    while True:
        params = {'page': page, 'per_page': 100}
        try:
            response = requests.get(endpoint, headers=headers, params=params, timeout=30)
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 5))
                print(f"   -> Rate limit exceeded, waiting {retry_after}s...")
                time.sleep(retry_after)
                continue
            response.raise_for_status()
            data = response.json()
            users_on_page = data.get('requesters', [])
            if not users_on_page: break
            all_users.extend(users_on_page)
            page += 1
        except requests.exceptions.RequestException as e:
            print(f"   -> Error fetching users on page {page}: {e}", file=sys.stderr)
            return None
    print(f" Found {len(all_users)} total users in Freshservice.")
    return all_users

# --- Database Functions ---
def populate_database(session, companies_data, users_data):
    print("\nStarting database population...")
    # Process Companies
    for company_data in companies_data:
        # First, try to find an existing company by its unique Freshservice ID
        company = session.query(Company).filter_by(freshservice_id=company_data['id']).first()

        if not company:
            # If not found by ID, try to find by name to avoid creating duplicates
            company = session.query(Company).filter_by(name=company_data['name']).first()
            if not company:
                # If still not found, create a new company object
                print(f" -> Creating new company: {company_data['name']}")
                company = Company(name=company_data['name'])
                session.add(company)
            else:
                print(f" -> Updating existing company by name: {company_data['name']}")
        else:
            print(f" -> Updating existing company by Freshservice ID: {company_data['name']}")

        # Update the company's attributes
        company.name = company_data['name']
        company.freshservice_id = company_data['id']
        # Add other fields as necessary from company_data['custom_fields'] if they exist
        custom_fields = company_data.get('custom_fields', {})
        if custom_fields:
            company.account_number = custom_fields.get('account_number_2')

    # Commit company changes to ensure IDs are available for contacts
    session.commit()
    print(" -> Finished processing companies.")

    # Process Users and Contacts
    for user_data in users_data:
        if not user_data.get('primary_email'):
            continue # Skip users without an email

        # Check if contact exists
        contact = session.query(Contact).filter_by(email=user_data['primary_email']).first()
        if not contact:
            contact = Contact(email=user_data['primary_email'])
            session.add(contact)

        contact.name = f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()

        # Associate with company
        if user_data.get('department_ids'):
            company = session.query(Company).filter_by(freshservice_id=user_data['department_ids'][0]).first()
            if company:
                contact.company_id = company.id

    # Commit all remaining changes
    session.commit()
    print(" -> Finished processing contacts.")


# --- Main Execution ---
if __name__ == "__main__":
    print("--- Running Freshservice Data Sync Script ---")
    try:
        config = get_config()
        FRESHSERVICE_API_KEY = config.get('freshservice', 'api_key')
        FRESHSERVICE_DOMAIN = config.get('freshservice', 'domain')
        BASE_URL = f"https://{FRESHSERVICE_DOMAIN}"

        auth_str = f"{FRESHSERVICE_API_KEY}:X"
        encoded_auth = base64.b64encode(auth_str.encode()).decode()
        headers = {"Content-Type": "application/json", "Authorization": f"Basic {encoded_auth}"}

        companies = get_all_companies(BASE_URL, headers)
        users = get_all_users(BASE_URL, headers)

        if companies and users:
            db_session = get_db_session()
            try:
                populate_database(db_session, companies, users)
                print("\n--- Freshservice Data Sync Successful ---")
            finally:
                db_session.close()
        else:
            print("\n--- Freshservice Data Sync Failed: Could not fetch data ---")

    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

