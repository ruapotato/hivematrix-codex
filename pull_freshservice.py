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

            if not account_number:
                print(f" -> Skipping company '{company_data['name']}' as it has no account number.")
                continue

            account_number_str = str(account_number)
            fs_dept_id_to_account_number[fs_id] = account_number_str

            # Check if company exists
            company = db.session.get(Company, account_number_str)

            if not company:
                print(f" -> Creating new company: {company_data['name']}")
                company = Company(
                    account_number=account_number_str,
                    freshservice_id=fs_id
                )
                db.session.add(company)
            else:
                print(f" -> Updating existing company: {company_data['name']}")

            # Core Freshservice fields (from top-level)
            company.freshservice_id = fs_id
            company.name = company_data.get('name')
            company.description = company_data.get('description')
            company.created_at = company_data.get('created_at')
            company.updated_at = company_data.get('updated_at')

            # Company head/prime user
            company.head_user_id = company_data.get('head_user_id')
            company.head_name = company_data.get('head_name')
            company.prime_user_id = company_data.get('prime_user_id')
            company.prime_user_name = company_data.get('prime_user_name')

            # Domains
            company.domains = json.dumps(company_data.get('domains', []))

            # Workspace
            company.workspace_id = company_data.get('workspace_id')

            # Custom fields from Freshservice
            company.plan_selected = custom_fields.get('plan_selected')
            company.managed_users = custom_fields.get('managed_users')
            company.managed_devices = custom_fields.get('managed_devices')
            company.managed_network = custom_fields.get('managed_network')
            company.contract_term = custom_fields.get('contract_term')
            company.contract_start_date = custom_fields.get('contract_start_date')
            company.profit_or_non_profit = custom_fields.get('profit_or_non_profit')
            company.company_main_number = custom_fields.get('company_main_number')
            company.address = custom_fields.get('address')
            company.company_start_date = custom_fields.get('company_start_date')

            # Additional fields (aliases for compatibility)
            company.billing_plan = custom_fields.get('plan_selected') or custom_fields.get('billing_plan')
            company.contract_term_length = custom_fields.get('contract_term')
            company.support_level = custom_fields.get('support_level')
            company.phone_system = custom_fields.get('phone_system')
            company.email_system = custom_fields.get('email_system')
            company.datto_portal_url = custom_fields.get('datto_portal_url')

            db.session.commit()

        print(" -> Finished processing companies.")

        # --- COMPANY DELETION ---
        # Delete companies that exist in Codex but not in Freshservice
        print("\nChecking for deleted companies...")

        # Get all Freshservice IDs from the fetched data
        fs_company_ids = set()
        for company_data in companies_data:
            custom_fields = company_data.get('custom_fields', {})
            account_number = custom_fields.get(ACCOUNT_NUMBER_FIELD) if custom_fields else None
            if account_number:
                fs_company_ids.add(company_data.get('id'))

        # Get all companies currently in Codex
        all_codex_companies = Company.query.all()

        companies_to_delete = []
        for company in all_codex_companies:
            if company.freshservice_id not in fs_company_ids:
                companies_to_delete.append(company)

        if companies_to_delete:
            print(f" -> Found {len(companies_to_delete)} companies to delete:")
            for company in companies_to_delete:
                print(f"    - Deleting: {company.name} (Account: {company.account_number}, FS ID: {company.freshservice_id})")
                db.session.delete(company)

            db.session.commit()
            print(f" -> Deleted {len(companies_to_delete)} companies from Codex")
        else:
            print(" -> No companies to delete")

        print("\nProcessing contacts...")

        # --- CONTACT PROCESSING ---
        for user_data in users_data:
            email = user_data.get('primary_email')
            fs_user_id = user_data.get('id')

            if not email:
                continue

            try:
                # Check if contact exists by Freshservice ID
                existing_contact = Contact.query.filter_by(freshservice_id=fs_user_id).first()

                # Get company account numbers from Freshservice department IDs
                fs_company_account_numbers = {
                    fs_dept_id_to_account_number.get(dept_id)
                    for dept_id in user_data.get('department_ids', [])
                    if fs_dept_id_to_account_number.get(dept_id)
                }

                # Prepare full name
                full_name = f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()
                if not full_name:
                    full_name = email.split('@')[0]  # Fallback to email username

                # Prepare custom fields
                custom_fields = user_data.get('custom_fields', {})

                if not existing_contact:
                    # Create new contact
                    contact = Contact(
                        freshservice_id=fs_user_id,
                        first_name=user_data.get('first_name'),
                        last_name=user_data.get('last_name'),
                        name=full_name,
                        primary_email=email,
                        email=email,
                        active=user_data.get('active', True),
                        is_agent=user_data.get('is_agent', False),
                        vip_user=user_data.get('vip_user', False),
                        has_logged_in=user_data.get('has_logged_in', False),
                        mobile_phone_number=user_data.get('mobile_phone_number'),
                        work_phone_number=user_data.get('work_phone_number'),
                        address=user_data.get('address'),
                        secondary_emails=json.dumps(user_data.get('secondary_emails', [])),
                        job_title=user_data.get('job_title'),
                        title=user_data.get('job_title'),
                        department_ids=json.dumps(user_data.get('department_ids', [])),
                        department_names=user_data.get('department_names'),
                        reporting_manager_id=user_data.get('reporting_manager_id'),
                        location_id=user_data.get('location_id'),
                        location_name=user_data.get('location_name'),
                        language=user_data.get('language', 'en'),
                        time_zone=user_data.get('time_zone'),
                        time_format=user_data.get('time_format'),
                        can_see_all_tickets_from_associated_departments=user_data.get('can_see_all_tickets_from_associated_departments', False),
                        can_see_all_changes_from_associated_departments=user_data.get('can_see_all_changes_from_associated_departments', False),
                        created_at=user_data.get('created_at'),
                        updated_at=user_data.get('updated_at'),
                        external_id=user_data.get('external_id'),
                        background_information=user_data.get('background_information'),
                        work_schedule_id=user_data.get('work_schedule_id'),
                        user_number=custom_fields.get('user_number')
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
                    existing_contact.first_name = user_data.get('first_name')
                    existing_contact.last_name = user_data.get('last_name')
                    existing_contact.name = full_name
                    existing_contact.primary_email = email
                    existing_contact.email = email
                    existing_contact.active = user_data.get('active', True)
                    existing_contact.is_agent = user_data.get('is_agent', False)
                    existing_contact.vip_user = user_data.get('vip_user', False)
                    existing_contact.has_logged_in = user_data.get('has_logged_in', False)
                    existing_contact.mobile_phone_number = user_data.get('mobile_phone_number')
                    existing_contact.work_phone_number = user_data.get('work_phone_number')
                    existing_contact.address = user_data.get('address')
                    existing_contact.secondary_emails = json.dumps(user_data.get('secondary_emails', []))
                    existing_contact.job_title = user_data.get('job_title')
                    existing_contact.title = user_data.get('job_title')
                    existing_contact.department_ids = json.dumps(user_data.get('department_ids', []))
                    existing_contact.department_names = user_data.get('department_names')
                    existing_contact.reporting_manager_id = user_data.get('reporting_manager_id')
                    existing_contact.location_id = user_data.get('location_id')
                    existing_contact.location_name = user_data.get('location_name')
                    existing_contact.language = user_data.get('language', 'en')
                    existing_contact.time_zone = user_data.get('time_zone')
                    existing_contact.time_format = user_data.get('time_format')
                    existing_contact.can_see_all_tickets_from_associated_departments = user_data.get('can_see_all_tickets_from_associated_departments', False)
                    existing_contact.can_see_all_changes_from_associated_departments = user_data.get('can_see_all_changes_from_associated_departments', False)
                    existing_contact.updated_at = user_data.get('updated_at')
                    existing_contact.external_id = user_data.get('external_id')
                    existing_contact.background_information = user_data.get('background_information')
                    existing_contact.work_schedule_id = user_data.get('work_schedule_id')
                    existing_contact.user_number = custom_fields.get('user_number')

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

        # --- CONTACT DELETION ---
        # Delete contacts that exist in Codex but not in Freshservice
        print("\nChecking for deleted contacts...")

        # Get all Freshservice user IDs from the fetched data
        fs_user_ids = {user_data.get('id') for user_data in users_data if user_data.get('primary_email')}

        # Get all contacts currently in Codex
        all_codex_contacts = Contact.query.all()

        contacts_to_delete = []
        for contact in all_codex_contacts:
            if contact.freshservice_id not in fs_user_ids:
                contacts_to_delete.append(contact)

        if contacts_to_delete:
            print(f" -> Found {len(contacts_to_delete)} contacts to delete:")
            for contact in contacts_to_delete:
                print(f"    - Deleting: {contact.name} ({contact.email}, FS ID: {contact.freshservice_id})")
                db.session.delete(contact)

            db.session.commit()
            print(f" -> Deleted {len(contacts_to_delete)} contacts from Codex")
        else:
            print(" -> No contacts to delete")

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
