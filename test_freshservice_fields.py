#!/usr/bin/env python3
"""
Test script to see what fields Freshservice returns for companies/departments.
This will help us map all available fields to our Codex models.
"""

import requests
import base64
import json
import configparser
import os
import sys

def get_config():
    """Load configuration from codex.conf"""
    instance_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
    config_path = os.path.join(instance_path, 'codex.conf')
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found at {config_path}")

    config = configparser.RawConfigParser()
    config.read(config_path)
    return config

def test_department_fields():
    """Fetch a few departments and show all fields returned."""
    config = get_config()
    api_key = config.get('freshservice', 'api_key')
    domain = config.get('freshservice', 'domain')
    base_url = f"https://{domain}"

    # Create auth header
    auth_str = f"{api_key}:X"
    encoded_auth = base64.b64encode(auth_str.encode()).decode()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {encoded_auth}"
    }

    print("="*80)
    print("Testing Freshservice Department/Company Fields")
    print("="*80)

    # Fetch first page of departments
    endpoint = f"{base_url}/api/v2/departments"
    params = {'page': 1, 'per_page': 3}  # Just get 3 for testing

    try:
        response = requests.get(endpoint, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        departments = data.get('departments', [])

        if not departments:
            print("\nNo departments found!")
            return

        print(f"\nFound {len(departments)} departments. Showing detailed fields:\n")

        for i, dept in enumerate(departments, 1):
            print(f"\n{'='*80}")
            print(f"DEPARTMENT #{i}: {dept.get('name', 'Unknown')}")
            print('='*80)

            # Show all top-level fields
            print("\n--- Top-Level Fields ---")
            for key, value in dept.items():
                if key != 'custom_fields':
                    if isinstance(value, (list, dict)):
                        print(f"  {key}: {json.dumps(value, indent=4)}")
                    else:
                        print(f"  {key}: {value}")

            # Show custom fields separately
            if 'custom_fields' in dept and dept['custom_fields']:
                print("\n--- Custom Fields ---")
                for key, value in dept['custom_fields'].items():
                    print(f"  {key}: {value}")
            else:
                print("\n--- Custom Fields ---")
                print("  (No custom fields)")

            print("\n" + "-"*80)

    except requests.exceptions.RequestException as e:
        print(f"\nError fetching departments: {e}", file=sys.stderr)
        return

def test_requester_fields():
    """Fetch a few requesters/users and show all fields returned."""
    config = get_config()
    api_key = config.get('freshservice', 'api_key')
    domain = config.get('freshservice', 'domain')
    base_url = f"https://{domain}"

    # Create auth header
    auth_str = f"{api_key}:X"
    encoded_auth = base64.b64encode(auth_str.encode()).decode()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {encoded_auth}"
    }

    print("\n\n")
    print("="*80)
    print("Testing Freshservice Requester/User Fields")
    print("="*80)

    # Fetch first page of requesters
    endpoint = f"{base_url}/api/v2/requesters"
    params = {'page': 1, 'per_page': 2}  # Just get 2 for testing

    try:
        response = requests.get(endpoint, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        requesters = data.get('requesters', [])

        if not requesters:
            print("\nNo requesters found!")
            return

        print(f"\nFound {len(requesters)} requesters. Showing detailed fields:\n")

        for i, user in enumerate(requesters, 1):
            print(f"\n{'='*80}")
            print(f"REQUESTER #{i}: {user.get('first_name', '')} {user.get('last_name', '')}")
            print('='*80)

            # Show all top-level fields
            print("\n--- Top-Level Fields ---")
            for key, value in user.items():
                if key != 'custom_fields':
                    if isinstance(value, (list, dict)):
                        print(f"  {key}: {json.dumps(value, indent=4)}")
                    else:
                        print(f"  {key}: {value}")

            # Show custom fields separately
            if 'custom_fields' in user and user['custom_fields']:
                print("\n--- Custom Fields ---")
                for key, value in user['custom_fields'].items():
                    print(f"  {key}: {value}")
            else:
                print("\n--- Custom Fields ---")
                print("  (No custom fields)")

            print("\n" + "-"*80)

    except requests.exceptions.RequestException as e:
        print(f"\nError fetching requesters: {e}", file=sys.stderr)
        return

if __name__ == "__main__":
    print("\n")
    print("#"*80)
    print("# Freshservice API Field Inspector")
    print("# This script shows what fields are available from Freshservice")
    print("#"*80)

    try:
        test_department_fields()
        test_requester_fields()

        print("\n\n")
        print("="*80)
        print("Test Complete!")
        print("="*80)
        print("\nReview the output above to see all available fields.")
        print("Use this to update the Codex models and pull_freshservice.py script.")

    except Exception as e:
        print(f"\n\nFATAL ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
