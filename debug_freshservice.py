# ruapotato/hivematrix-nexus/hivematrix-nexus-main/debug_freshservice.py

import requests
import base64
import os
import sys
import configparser
import json
import time

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

if __name__ == "__main__":
    try:
        config = get_config()
        FRESHSERVICE_API_KEY = config.get('freshservice', 'api_key')
        FRESHSERVICE_DOMAIN = config.get('freshservice', 'domain')
        BASE_URL = f"https://{FRESHSERVICE_DOMAIN}"

        auth_str = f"{FRESHSERVICE_API_KEY}:X"
        encoded_auth = base64.b64encode(auth_str.encode()).decode()
        headers = {"Content-Type": "application/json", "Authorization": f"Basic {encoded_auth}"}

        search_type = input("Do you want to search for a 'company' or a 'contact'? ").lower().strip()

        if search_type == 'company':
            company_name = input("Enter the company name to search for: ")
            companies = get_all_companies(BASE_URL, headers)
            if companies:
                found_company = next((c for c in companies if c['name'].lower() == company_name.lower()), None)
                if found_company:
                    print("\n--- Company Data ---")
                    print(json.dumps(found_company, indent=2))
                else:
                    print(f"\nCould not find a company named '{company_name}'.")

        elif search_type == 'contact':
            contact_name = input("Enter the contact's full name to search for: ")
            users = get_all_users(BASE_URL, headers)
            if users:
                found_user = next((u for u in users if f"{u.get('first_name', '')} {u.get('last_name', '')}".strip().lower() == contact_name.lower()), None)
                if found_user:
                    print("\n--- Contact Data ---")
                    print(json.dumps(found_user, indent=2))
                else:
                    print(f"\nCould not find a contact named '{contact_name}'.")
        else:
            print("Invalid selection. Please run the script again and enter 'company' or 'contact'.")

    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

