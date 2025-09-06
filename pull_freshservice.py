import requests
import base64
import os
import sys
import time
import configparser
import json

# --- API Configuration ---
NEXUS_API_URL = 'http://127.0.0.1:5000/api'
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
def populate_database_via_api(companies_data, users_data, api_key):
    headers = {'X-API-Key': api_key, 'Content-Type': 'application/json'}
    print("\nStarting database population...")
    # Process Companies
    for company_data in companies_data:
        custom_fields = company_data.get('custom_fields', {})
        account_number = custom_fields.get(ACCOUNT_NUMBER_FIELD) if custom_fields else None
        
        if not account_number:
            print(f" -> Skipping company '{company_data['name']}' as it has no account number.")
            continue

        response = requests.get(f"{NEXUS_API_URL}/companies", headers=headers, params={'account_number': account_number})
        existing_company = response.json()
        
        company_payload = {
            'name': company_data['name'],
            'account_number': account_number,
            'freshservice_id': company_data['id']
        }

        if not existing_company:
            requests.post(f"{NEXUS_API_URL}/companies", headers=headers, json=company_payload)
            print(f" -> Creating new company: {company_data['name']}")
        else:
            company_id = existing_company[0]['id']
            requests.put(f"{NEXUS_API_URL}/companies/{company_id}", headers=headers, json=company_payload)
            print(f" -> Updating existing company: {company_data['name']}")

    print(" -> Finished processing companies.")

    # Process Users and Contacts
    for user_data in users_data:
        if not user_data.get('primary_email'):
            continue

        company_id = None
        if user_data.get('department_ids'):
            fs_company_id = user_data['department_ids'][0]
            response = requests.get(f"{NEXUS_API_URL}/companies", headers=headers, params={'freshservice_id': fs_company_id})
            company_data_nexus = response.json()
            if company_data_nexus:
                company_id = company_data_nexus[0]['id']
        
        if not company_id:
            print(f" -> Skipping contact for {user_data['primary_email']} as their associated company is not in Nexus.")
            continue

        response = requests.get(f"{NEXUS_API_URL}/contacts", headers=headers, params={'email': user_data['primary_email']})
        existing_contact = response.json()
        
        contact_payload = {
            'name': f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip(),
            'email': user_data['primary_email'],
            'company_id': company_id
        }

        if not existing_contact:
            requests.post(f"{NEXUS_API_URL}/contacts", headers=headers, json=contact_payload)
        else:
            contact_id = existing_contact[0]['id']
            requests.put(f"{NEXUS_API_URL}/contacts/{contact_id}", headers=headers, json=contact_payload)

    print(" -> Finished processing contacts.")


# --- Main Execution ---
if __name__ == "__main__":
    print("--- Running Freshservice Data Sync Script ---")
    try:
        config = get_config()
        FRESHSERVICE_API_KEY = config.get('freshservice', 'api_key')
        FRESHSERVICE_DOMAIN = config.get('freshservice', 'domain')
        NEXUS_API_KEY = config.get('nexus', 'api_key')
        BASE_URL = f"https://{FRESHSERVICE_DOMAIN}"

        auth_str = f"{FRESHSERVICE_API_KEY}:X"
        encoded_auth = base64.b64encode(auth_str.encode()).decode()
        headers = {"Content-Type": "application/json", "Authorization": f"Basic {encoded_auth}"}

        companies = get_all_companies(BASE_URL, headers)
        users = get_all_users(BASE_URL, headers)

        if companies and users:
            populate_database_via_api(companies, users, NEXUS_API_KEY)
            print("\n--- Freshservice Data Sync Successful ---")
        else:
            print("\n--- Freshservice Data Sync Failed: Could not fetch data ---")

    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)
