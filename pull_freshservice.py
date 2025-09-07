# ruapotato/hivematrix-nexus/hivematrix-nexus-main/pull_freshservice.py

import requests
import base64
import os
import sys
import time
import configparser
import json
import warnings

# Suppress InsecureRequestWarning for self-signed certs in development
from requests.packages.urllib3.exceptions import InsecureRequestWarning
warnings.simplefilter('ignore', InsecureRequestWarning)

# --- API Configuration ---
NEXUS_API_URL = 'https://127.0.0.1:5000/api'
ACCOUNT_NUMBER_FIELD = "account_number"

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

def get_nexus_token(username, password):
    """Authenticates with the Nexus API and returns a JWT."""
    try:
        # NOTE: verify=False is used here for local development with a self-signed certificate.
        # In a production environment, you would use a trusted certificate and remove this.
        response = requests.post(f"{NEXUS_API_URL}/token", json={'username': username, 'password': password}, timeout=10, verify=False)
        response.raise_for_status()
        token = response.json().get('token')
        if not token:
            print("Failed to retrieve token from Nexus API.", file=sys.stderr)
            return None
        print("Successfully obtained Nexus API token.")
        return token
    except requests.exceptions.RequestException as e:
        print(f"Error authenticating with Nexus API: {e}", file=sys.stderr)
        return None

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
def populate_database_via_api(companies_data, users_data, nexus_token):
    if not nexus_token:
        print("Cannot proceed without a Nexus API token.", file=sys.stderr)
        return
    headers = {'Authorization': f'Bearer {nexus_token}', 'Content-Type': 'application/json'}
    print("\nStarting database population...")

    fs_dept_id_to_account_number = {}
    users_by_department = {}

    # Pre-process users to group them by department
    for user in users_data:
        for dept_id in user.get('department_ids', []):
            if dept_id not in users_by_department:
                users_by_department[dept_id] = []
            users_by_department[dept_id].append(user)

    # Process Companies
    for company_data in companies_data:
        custom_fields = company_data.get('custom_fields', {})
        account_number = custom_fields.get(ACCOUNT_NUMBER_FIELD) if custom_fields else None
        fs_id = company_data.get('id')
        address = custom_fields.get('address')
        main_phone = custom_fields.get('company_main_number')

        if not account_number:
            print(f" -> Skipping company '{company_data['name']}' as it has no account number.")
            continue

        fs_dept_id_to_account_number[fs_id] = str(account_number)

        response = requests.get(f"{NEXUS_API_URL}/companies/{account_number}", headers=headers, verify=False)
        company_payload = {
            'name': company_data['name'], 'account_number': str(account_number), 'freshservice_id': fs_id,
            'description': company_data.get('description'), 'plan_selected': custom_fields.get('plan_selected'),
            'profit_or_non_profit': custom_fields.get('profit_or_non_profit'), 'company_main_number': main_phone,
            'company_start_date': custom_fields.get('company_start_date'), 'head_name': company_data.get('head_name'),
            'primary_contact_name': company_data.get('prime_user_name'), 'domains': json.dumps(company_data.get('domains', []))
        }

        if response.status_code == 404:
            print(f" -> Creating new company: {company_data['name']}")
            requests.post(f"{NEXUS_API_URL}/companies", headers=headers, json=company_payload, verify=False).raise_for_status()
        else:
            response.raise_for_status()
            print(f" -> Updating existing company: {company_data['name']}")
            requests.put(f"{NEXUS_API_URL}/companies/{account_number}", headers=headers, json=company_payload, verify=False).raise_for_status()

        if address:
            from models import db, Location
            from main import app
            with app.app_context():
                location = Location.query.filter_by(company_account_number=account_number, name="Main Office").first()
                if not location:
                    location = Location(name="Main Office", company_account_number=account_number)
                    db.session.add(location)
                location.address = address
                location.phone_number = main_phone
                db.session.commit()
                print(f"   -> Synced 'Main Office' location for {company_data['name']}")

    print(" -> Finished processing companies.")
    print("\nProcessing contacts...")

    # Process Users/Contacts
    for user_data in users_data:
        email = user_data.get('primary_email')
        if not email:
            continue

        contact_response = requests.get(f"{NEXUS_API_URL}/contacts", headers=headers, params={'email': email}, verify=False)
        contact_response.raise_for_status()
        existing_contact_list = contact_response.json()
        existing_contact = existing_contact_list[0] if existing_contact_list else None

        fs_company_account_numbers = {fs_dept_id_to_account_number.get(dept_id) for dept_id in user_data.get('department_ids', []) if fs_dept_id_to_account_number.get(dept_id)}

        contact_payload = {
            'name': f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip(),
            'email': email, 'title': user_data.get('job_title'), 'active': user_data.get('active'),
            'mobile_phone_number': user_data.get('mobile_phone_number'), 'work_phone_number': user_data.get('work_phone_number'),
            'secondary_emails': json.dumps(user_data.get('secondary_emails', []))
        }

        if not existing_contact:
            contact_payload['company_account_numbers'] = list(fs_company_account_numbers)
            requests.post(f"{NEXUS_API_URL}/contacts", headers=headers, json=contact_payload, verify=False).raise_for_status()
        else:
            contact_id = existing_contact['id']
            detailed_contact_res = requests.get(f"{NEXUS_API_URL}/contacts/{contact_id}", headers=headers, verify=False)
            detailed_contact_res.raise_for_status()
            nexus_company_account_numbers = set(detailed_contact_res.json().get('company_account_numbers', []))

            all_account_numbers = nexus_company_account_numbers.union(fs_company_account_numbers)
            contact_payload['company_account_numbers'] = list(all_account_numbers)

            requests.put(f"{NEXUS_API_URL}/contacts/{contact_id}", headers=headers, json=contact_payload, verify=False).raise_for_status()

    print(" -> Finished processing contacts.")


# --- Main Execution ---
if __name__ == "__main__":
    print("--- Running Freshservice Data Sync Script ---")
    try:
        config = get_config()
        FRESHSERVICE_API_KEY = config.get('freshservice', 'api_key')
        FRESHSERVICE_DOMAIN = config.get('freshservice', 'domain')
        NEXUS_USERNAME = config.get('nexus_auth', 'username')
        NEXUS_PASSWORD = config.get('nexus_auth', 'password')
        BASE_URL = f"https://{FRESHSERVICE_DOMAIN}"

        nexus_token = get_nexus_token(NEXUS_USERNAME, NEXUS_PASSWORD)
        if not nexus_token:
            sys.exit(1)

        auth_str = f"{FRESHSERVICE_API_KEY}:X"
        encoded_auth = base64.b64encode(auth_str.encode()).decode()
        fs_headers = {"Content-Type": "application/json", "Authorization": f"Basic {encoded_auth}"}

        companies = get_all_companies(BASE_URL, fs_headers)
        users = get_all_users(BASE_URL, fs_headers)

        if companies and users:
            populate_database_via_api(companies, users, nexus_token)
            print("\n--- Freshservice Data Sync Successful ---")
        else:
            print("\n--- Freshservice Data Sync Failed: Could not fetch data ---")
            sys.exit(1)

    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

