import requests
import os
import sys
import configparser
import json

# --- API Configuration ---
NEXUS_API_URL = 'http://127.0.0.1:5000/api'
DATTO_VARIABLE_NAME = "AccountNumber"

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

def get_datto_access_token(api_endpoint, api_key, api_secret_key):
    token_url = f"{api_endpoint}/auth/oauth/token"
    payload = {'grant_type': 'password', 'username': api_key, 'password': api_secret_key}
    headers = {'Content-Type': 'application/x-www-form-urlencoded', 'Authorization': 'Basic cHVibGljLWNsaWVudDpwdWJsaWM='}
    try:
        response = requests.post(token_url, headers=headers, data=payload, timeout=30)
        response.raise_for_status()
        print("Successfully obtained Datto RMM access token.")
        return response.json().get("access_token")
    except requests.exceptions.RequestException as e:
        print(f"Error getting Datto access token: {e}", file=sys.stderr)
        return None

def get_all_sites(api_endpoint, access_token):
    all_sites = []
    next_page_url = f"{api_endpoint}/api/v2/account/sites"
    headers = {'Authorization': f'Bearer {access_token}'}
    print("Fetching all sites from Datto RMM...")
    while next_page_url:
        try:
            response = requests.get(next_page_url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            all_sites.extend(data.get('sites', []))
            next_page_url = data.get('pageDetails', {}).get('nextPageUrl')
        except requests.exceptions.RequestException as e:
            print(f"Error fetching sites: {e}", file=sys.stderr)
            return None
    print(f"Found {len(all_sites)} sites.")
    return all_sites

def get_site_variable(api_endpoint, access_token, site_uid, variable_name):
    request_url = f"{api_endpoint}/api/v2/site/{site_uid}/variables"
    headers = {'Authorization': f'Bearer {access_token}'}
    try:
        response = requests.get(request_url, headers=headers, timeout=30)
        if response.status_code == 404: return None
        response.raise_for_status()
        variables = response.json().get("variables", [])
        for var in variables:
            if var.get("name") == variable_name:
                return var.get("value")
        return None
    except requests.exceptions.RequestException:
        return None


def get_devices_for_site(api_endpoint, access_token, site_uid):
    all_devices = []
    next_page_url = f"{api_endpoint}/api/v2/site/{site_uid}/devices"
    headers = {'Authorization': f'Bearer {access_token}'}
    while next_page_url:
        try:
            response = requests.get(next_page_url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            all_devices.extend(data.get('devices', []))
            next_page_url = data.get('pageDetails', {}).get('nextPageUrl')
        except requests.exceptions.RequestException as e:
            print(f"Error fetching devices for site {site_uid}: {e}", file=sys.stderr)
            return None
    return all_devices

def populate_assets_via_api(sites, access_token, api_endpoint, api_key):
    headers = {'X-API-Key': api_key, 'Content-Type': 'application/json'}
    print("\nProcessing sites and devices...")
    for site in sites:
        account_number = get_site_variable(api_endpoint, access_token, site['uid'], DATTO_VARIABLE_NAME)

        if not account_number:
            print(f" -> Skipping site '{site['name']}' as it is missing the '{DATTO_VARIABLE_NAME}' variable.")
            continue

        response = requests.get(f"{NEXUS_API_URL}/companies", headers=headers, params={'account_number': account_number})
        company_data = response.json()

        company_payload = {
            'name': site['name'],
            'account_number': account_number,
            'datto_site_uid': site['uid']
        }

        if not company_data:
            print(f" -> Company with account number '{account_number}' not found. Creating new entry for '{site['name']}'.")
            response = requests.post(f"{NEXUS_API_URL}/companies", headers=headers, json=company_payload)
            company_id = response.json()['id']
        else:
            company_id = company_data[0]['id']
            requests.put(f"{NEXUS_API_URL}/companies/{company_id}", headers=headers, json=company_payload)
            print(f" -> Found company '{site['name']}'. Fetching devices...")

        devices = get_devices_for_site(api_endpoint, access_token, site['uid'])
        if devices:
            print(f"   -> Found {len(devices)} devices. Updating database...")
            for device_data in devices:
                response = requests.get(f"{NEXUS_API_URL}/assets", headers=headers, params={'hostname': device_data['hostname'], 'company_id': company_id})
                asset_data = response.json()

                asset_payload = {
                    'hostname': device_data['hostname'], 'company_id': company_id,
                    'device_type': (device_data.get('deviceType') or {}).get('category'),
                    'operating_system': device_data.get('operatingSystem'),
                    'last_logged_in_user': device_data.get('lastLoggedInUser')
                }

                if not asset_data:
                    requests.post(f"{NEXUS_API_URL}/assets", headers=headers, json=asset_payload)
                else:
                    asset_id = asset_data[0]['id']
                    requests.put(f"{NEXUS_API_URL}/assets/{asset_id}", headers=headers, json=asset_payload)

    print(" -> Finished processing assets.")


# --- Main Execution ---
if __name__ == "__main__":
    print("--- Datto RMM Data Syncer ---")
    try:
        config = get_config()
        DATTO_API_ENDPOINT = config.get('datto', 'api_endpoint')
        DATTO_PUBLIC_KEY = config.get('datto', 'public_key')
        DATTO_SECRET_KEY = config.get('datto', 'secret_key')
        NEXUS_API_KEY = config.get('nexus', 'api_key')


        token = get_datto_access_token(DATTO_API_ENDPOINT, DATTO_PUBLIC_KEY, DATTO_SECRET_KEY)
        if not token:
            sys.exit("\n- Failed to obtain access token.")

        sites = get_all_sites(DATTO_API_ENDPOINT, token)
        if sites:
            populate_assets_via_api(sites, token, DATTO_API_ENDPOINT, NEXUS_API_KEY)
            print("\n--- Datto RMM Data Sync Successful ---")
        else:
            print("\nCould not retrieve sites list.")

    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)
