import requests
import base64
import os
import sys
import time
import configparser
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add the project root to the path so we can import models
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import db, Company, Contact, Location, contact_company_link
from app import app

# --- Configuration ---
ACCOUNT_NUMBER_FIELD = "account_number"

def get_config():
    """Loads the configuration from codex.conf in the instance folder."""
    instance_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
    config_path = os.path.join(instance_path, 'codex.conf')
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found at {config_path}")

    print(f"Loading configuration from: {config_path}")
    config = configparser.RawConfigParser()
    config.read(config_path)
    return config

def get_all_companies(base_url, headers):
    """Fetches all departments (companies) from Freshservice."""
    print("Fetching companies from Freshservice...")
    all_companies = []
    page = 1
    endpoint = f"{base_url}/api/v2/departments"

    while True:
        try:
            params = {'page': page, 'per_page': 100}
            response = requests.get(endpoint, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            companies_on_page = data.get('departments', [])

            if not companies_on_page:
                break

            all_companies.extend(companies_on_page)
            page += 1

        except requests.exceptions.RequestException as e:
            print(f"Error fetching Freshservice companies: {e}", file=sys.stderr)
            return None

    print(f" Found {len(all_companies)} companies in Freshservice.")
    return all_companies

def get_all_users(base_url, headers):
    """Fetches all requesters (users) from Freshservice."""
    print("\nFetching all users from Freshservice...")
    all_users = []
    page = 1
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

            if not users_on_page:
                break

            all_users.extend(users_on_page)
            page += 1

        except requests.exceptions.RequestException as e:
            print(f"   -> Error fetching users on page {page}: {e}", file=sys.stderr)
            return None

    print(f" Found {len(all_users)} total users in Freshservice.")
    return all_users

def populate_database(companies_data, users_data):
    """Populates the Codex database with companies and contacts."""
    print("\nStarting database population...")

    with app.app_context():
        # --- COMPANY PROCESSING ---
        print("Processing companies...")
        fs_dept_id_to_account_number = {}

        for company_data in companies_data:
            custom_fields = company_data.get('custom_fields', {})
            account_number = custom_fields.get(ACCOUNT_NUMBER_FIELD) if custom_fields else None
            fs_id = company_data.get('id')
            address = custom_fields.get('address')
            main_phone = custom_fields.get('company_main_number')

            if not account_number:
                print(f" -> Skipping company '{company_data['name']}' as it has no account number.")
                continue

            account_number_str = str(account_number)
            fs_dept_id_to_account_number[fs_id] = account_number_str

            # Check if company exists
            company = db.session.get(Company, account_number_str)

            if not company:
                print(f" -> Creating new company: {company_data['name']}")
                company = Company(account_number=account_number_str)
                db.session.add(company)
            else:
                print(f" -> Updating existing company: {company_data['name']}")

            # Update company fields
            company.name = company_data['name']
            company.freshservice_id = fs_id
            company.description = company_data.get('description')
            company.plan_selected = custom_fields.get('plan_selected')
            company.profit_or_non_profit = custom_fields.get('profit_or_non_profit')
            company.company_main_number = main_phone
            company.company_start_date = custom_fields.get('company_start_date')
            company.head_name = company_data.get('head_name')
            company.primary_contact_name = company_data.get('prime_user_name')
            company.domains = json.dumps(company_data.get('domains', []))

            db.session.commit()

            # Handle location
            if address:
                location = Location.query.filter_by(
                    company_account_number=account_number_str,
                    name="Main Office"
                ).first()

                if not location:
                    location = Location(
                        name="Main Office",
                        company_account_number=account_number_str
                    )
                    db.session.add(location)

                location.address = address
                location.phone_number = main_phone
                db.session.commit()
                print(f"   -> Synced 'Main Office' location for {company_data['name']}")

        print(" -> Finished processing companies.")
        print("\nProcessing contacts...")

        # --- CONTACT PROCESSING ---
        for user_data in users_data:
            email = user_data.get('primary_email')
            if not email:
                continue

            try:
                # Check if contact exists by email
                existing_contact = Contact.query.filter_by(email=email).first()

                # Get company account numbers from Freshservice department IDs
                fs_company_account_numbers = {
                    fs_dept_id_to_account_number.get(dept_id)
                    for dept_id in user_data.get('department_ids', [])
                    if fs_dept_id_to_account_number.get(dept_id)
                }

                if not existing_contact:
                    # Create new contact
                    contact = Contact(
                        name=f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip(),
                        email=email,
                        title=user_data.get('job_title'),
                        active=user_data.get('active', True),
                        mobile_phone_number=user_data.get('mobile_phone_number'),
                        work_phone_number=user_data.get('work_phone_number'),
                        secondary_emails=json.dumps(user_data.get('secondary_emails', []))
                    )
                    db.session.add(contact)
                    db.session.flush()  # Get the contact ID

                    # Add company associations
                    for account_number in fs_company_account_numbers:
                        company = db.session.get(Company, account_number)
                        if company:
                            contact.companies.append(company)

                    print(f" -> Created contact: {contact.name} ({email})")
                else:
                    # Update existing contact
                    existing_contact.name = f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()
                    existing_contact.title = user_data.get('job_title')
                    existing_contact.active = user_data.get('active', True)
                    existing_contact.mobile_phone_number = user_data.get('mobile_phone_number')
                    existing_contact.work_phone_number = user_data.get('work_phone_number')
                    existing_contact.secondary_emails = json.dumps(user_data.get('secondary_emails', []))

                    # Merge company associations (keep existing, add new ones from FS)
                    existing_account_numbers = {c.account_number for c in existing_contact.companies}
                    all_account_numbers = existing_account_numbers.union(fs_company_account_numbers)

                    # Update company associations
                    existing_contact.companies = []
                    for account_number in all_account_numbers:
                        company = db.session.get(Company, account_number)
                        if company:
                            existing_contact.companies.append(company)

                    print(f" -> Updated contact: {existing_contact.name} ({email})")

                db.session.commit()

            except Exception as e:
                print(f"  -> ERROR processing contact {email}: {e}", file=sys.stderr)
                db.session.rollback()

        print(" -> Finished processing contacts.")

# --- Main Execution ---
if __name__ == "__main__":
    print("--- Running Freshservice Data Sync Script ---")
    try:
        config = get_config()
        FRESHSERVICE_API_KEY = config.get('freshservice', 'api_key')
        FRESHSERVICE_DOMAIN = config.get('freshservice', 'domain')
        BASE_URL = f"https://{FRESHSERVICE_DOMAIN}"

        # Create auth header
        auth_str = f"{FRESHSERVICE_API_KEY}:X"
        encoded_auth = base64.b64encode(auth_str.encode()).decode()
        fs_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Basic {encoded_auth}"
        }

        # Fetch data from Freshservice
        companies = get_all_companies(BASE_URL, fs_headers)
        users = get_all_users(BASE_URL, fs_headers)

        if companies and users:
            populate_database(companies, users)
            print("\n--- Freshservice Data Sync Successful ---")
        else:
            print("\n--- Freshservice Data Sync Failed: Could not fetch data from Freshservice ---")
            sys.exit(1)

    except Exception as e:
        print(f"\nAn unexpected error occurred during Freshservice sync: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
