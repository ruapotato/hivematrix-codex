#!/usr/bin/env python3
"""
Freshservice Account Number Setter

Assigns unique random 6-digit account numbers to Freshservice departments (companies)
that don't already have one. This script should run BEFORE pull_freshservice.py to
ensure all companies have account numbers before being synced to Codex.
"""

import requests
import base64
import json
import os
import sys
import time
import random
import configparser

# --- Configuration ---
ACCOUNT_NUMBER_FIELD = "account_number"
COMPANIES_PER_PAGE = 100
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds


def get_config():
    """Loads the configuration from codex.conf in the instance folder."""
    instance_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
    config_path = os.path.join(instance_path, 'codex.conf')
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found at {config_path}")

    config = configparser.RawConfigParser()
    config.read(config_path)
    return config


def get_all_companies(base_url, headers):
    """Fetches all companies (departments) from the Freshservice API."""
    all_companies = []
    page = 1
    endpoint = f"{base_url}/api/v2/departments"

    while True:
        params = {'page': page, 'per_page': COMPANIES_PER_PAGE}
        try:
            response = requests.get(endpoint, headers=headers, params=params, timeout=30)
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', RETRY_DELAY))
                print(f"Rate limit exceeded. Waiting {retry_after} seconds...")
                time.sleep(retry_after)
                continue
            response.raise_for_status()
            data = response.json()
            companies_on_page = data.get('departments', [])
            if not companies_on_page:
                break
            all_companies.extend(companies_on_page)
            if len(companies_on_page) < COMPANIES_PER_PAGE:
                break
            page += 1
        except requests.exceptions.RequestException as e:
            print(f"Error fetching companies: {e}", file=sys.stderr)
            return None
    return all_companies


def update_company_account_number(base_url, headers, company_id, account_number):
    """Updates a single company with a new account number."""
    endpoint = f"{base_url}/api/v2/departments/{company_id}"

    payload = {
        "custom_fields": {
            ACCOUNT_NUMBER_FIELD: account_number
        }
    }

    try:
        response = requests.put(endpoint, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(f"Failed to update company ID {company_id}: {e}", file=sys.stderr)
        if hasattr(e, 'response') and e.response:
            print(f"Response: {e.response.text}", file=sys.stderr)
        return False


# --- Main Execution ---
if __name__ == "__main__":
    print("=" * 60)
    print("FRESHSERVICE ACCOUNT NUMBER SETTER")
    print("=" * 60)

    try:
        config = get_config()
        API_KEY = config.get('freshservice', 'api_key')
        DOMAIN = config.get('freshservice', 'domain')
        BASE_URL = f"https://{DOMAIN}"

        auth_str = f"{API_KEY}:X"
        encoded_auth = base64.b64encode(auth_str.encode()).decode()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Basic {encoded_auth}"
        }

        # 1. Fetch all companies
        print("\n1. Fetching companies from Freshservice...")
        companies = get_all_companies(BASE_URL, headers)
        if companies is None:
            print("Could not fetch companies. Aborting.", file=sys.stderr)
            sys.exit(1)

        print(f"   Found {len(companies)} total companies in Freshservice.")

        # 2. Find existing account numbers and companies that need one
        existing_numbers = set()
        companies_to_update = []

        for company in companies:
            custom_fields = company.get('custom_fields', {})
            acc_num = custom_fields.get(ACCOUNT_NUMBER_FIELD)
            if acc_num:
                # Add the number to our set to prevent creating duplicates
                existing_numbers.add(int(acc_num))
            else:
                companies_to_update.append(company)

        print(f"   Found {len(existing_numbers)} companies with existing account numbers.")
        print(f"   Found {len(companies_to_update)} companies that need a new account number.")

        if not companies_to_update:
            print("\n✓ All companies already have an account number. Nothing to do.")
            sys.exit(0)

        # 3. Generate and assign unique numbers
        print("\n2. Assigning New Account Numbers...")
        updated_count = 0
        for company in companies_to_update:
            new_number = None
            while new_number is None or new_number in existing_numbers:
                new_number = random.randint(100000, 999999)

            company_id = company['id']
            company_name = company['name']

            print(f"   → Updating '{company_name}' (ID: {company_id}) with new account number: {new_number}")

            # 4. Update the company in Freshservice
            success = update_company_account_number(BASE_URL, headers, company_id, new_number)

            if success:
                existing_numbers.add(new_number)
                updated_count += 1
                # Be respectful of API rate limits
                time.sleep(0.5)
            else:
                print(f"   ✗ Skipping '{company_name}' due to update failure.")

        print("\n" + "=" * 60)
        print(f"✓ Successfully updated {updated_count} companies.")
        print("=" * 60)

    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
