import requests
import os
import sys
import configparser
from datetime import datetime
import warnings

# Suppress InsecureRequestWarning for self-signed certs in development
from requests.packages.urllib3.exceptions import InsecureRequestWarning
warnings.simplefilter('ignore', InsecureRequestWarning)

# --- API Configuration ---
NEXUS_API_URL = 'https://127.0.0.1:5000/api'
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

def format_timestamp(ts):
    """Converts millisecond epoch timestamp to a readable string."""
    if not ts:
        return None
    return datetime.fromtimestamp(ts / 1000).strftime('%Y-%m-%d %H:%M:%S')

def bytes_to_tb(b):
    """Converts bytes to terabytes and returns a formatted string."""
    if not b:
        return None
    try:
        b_float = float(b)
        tb = b_float / (1024**4)
        return f"{tb:.2f}"
    except (ValueError, TypeError):
        return None

def process_datto_data(sites, access_token, api_endpoint, nexus_token):
    if not nexus_token:
        print("Cannot proceed without a Nexus API token.", file=sys.stderr)
        return

    headers = {'Authorization': f'Bearer {nexus_token}', 'Content-Type': 'application/json'}
    from main import create_app
    from models import db, Company, DattoSiteLink

    # Group sites by account number
    sites_by_account = {}
    print("\nGrouping Datto sites by AccountNumber...")
    for site in sites:
        account_number = get_site_variable(api_endpoint, access_token, site['uid'], DATTO_VARIABLE_NAME)
        if account_number:
            if account_number not in sites_by_account:
                sites_by_account[account_number] = []
            sites_by_account[account_number].append(site)
        else:
            print(f" -> WARNING: No AccountNumber for site '{site['name']}'. Skipping.")

    print("Processing companies and their assets...")
    app = create_app()
    with app.app_context():
        for account_number, site_list in sites_by_account.items():
            company = db.session.get(Company, account_number)
            if not company:
                print(f" -> WARNING: Company with account '{account_number}' not in Nexus. Skipping {len(site_list)} site(s).")
                continue

            print(f"\n--- Processing Company: {company.name} ({account_number}) ---")

            # Get all assets currently in Nexus for this company
            nexus_assets_response = requests.get(f"{NEXUS_API_URL}/assets", headers=headers, params={'company_account_number': account_number}, verify=False)
            nexus_assets_response.raise_for_status()
            nexus_assets_by_hostname = {asset['hostname']: asset for asset in nexus_assets_response.json()}

            all_datto_hostnames_for_company = set()

            for site in site_list:
                datto_uid = site.get('uid')
                site_name = site.get('name') # Get the site name
                link = DattoSiteLink.query.filter_by(datto_site_uid=datto_uid).first()
                if not link:
                    link = DattoSiteLink(company_account_number=account_number, datto_site_uid=datto_uid)
                    db.session.add(link)
                    db.session.commit()
                    print(f" -> Linked Datto site '{site['name']}' to company '{company.name}'.")

                devices = get_devices_for_site(api_endpoint, access_token, datto_uid)
                if devices:
                    print(f"   -> Found {len(devices)} devices for site '{site['name']}'. Syncing...")
                    for device_data in devices:
                        hostname = device_data.get('hostname')
                        if not hostname:
                            continue

                        all_datto_hostnames_for_company.add(hostname)

                        udf = device_data.get('udf', {})
                        asset_payload = {
                            'hostname': hostname,
                            'company_account_number': account_number,
                            'datto_site_name': site_name, # Add site name to payload
                            'operating_system': device_data.get('operatingSystem'),
                            'last_logged_in_user': device_data.get('lastLoggedInUser'),
                            'hardware_type': (device_data.get('deviceType') or {}).get('category'),
                            'antivirus_product': (device_data.get('antivirus') or {}).get('antivirusProduct'),
                            'description': device_data.get('description'),
                            'ext_ip_address': device_data.get('extIpAddress'),
                            'int_ip_address': device_data.get('intIpAddress'),
                            'domain': device_data.get('domain'),
                            'last_audit_date': format_timestamp(device_data.get('lastAuditDate')),
                            'last_reboot': format_timestamp(device_data.get('lastReboot')),
                            'last_seen': format_timestamp(device_data.get('lastSeen')),
                            'online': device_data.get('online'),
                            'patch_status': (device_data.get('patchManagement') or {}).get('patchStatus'),
                            'backup_usage_tb': bytes_to_tb(udf.get('udf6')),
                            'enabled_administrators': udf.get('udf4'),
                            'device_type': udf.get('udf7'),
                            'portal_url': device_data.get('portalUrl'),
                            'web_remote_url': device_data.get('webRemoteUrl'),
                        }

                        existing_asset = nexus_assets_by_hostname.get(hostname)

                        if not existing_asset:
                            post_asset_response = requests.post(f"{NEXUS_API_URL}/assets", headers=headers, json=asset_payload, verify=False)
                            post_asset_response.raise_for_status()
                        else:
                            asset_id = existing_asset['id']
                            put_asset_response = requests.put(f"{NEXUS_API_URL}/assets/{asset_id}", headers=headers, json=asset_payload, verify=False)
                            put_asset_response.raise_for_status()

            # Now, compare the complete list of Datto assets for this company against Nexus
            nexus_hostnames = set(nexus_assets_by_hostname.keys())
            hostnames_to_delete = nexus_hostnames - all_datto_hostnames_for_company

            if hostnames_to_delete:
                print(f"   -> Found {len(hostnames_to_delete)} asset(s) to delete from Nexus for '{company.name}'...")
                for hostname in hostnames_to_delete:
                    asset_to_delete = nexus_assets_by_hostname[hostname]
                    asset_id = asset_to_delete['id']
                    delete_response = requests.delete(f"{NEXUS_API_URL}/assets/{asset_id}", headers=headers, verify=False)
                    if delete_response.status_code == 200:
                        print(f"      -> Deleted asset '{hostname}' (ID: {asset_id})")
                    else:
                        print(f"      -> FAILED to delete asset '{hostname}' (ID: {asset_id}): {delete_response.text}", file=sys.stderr)

    print("\n -> Finished processing all companies and assets.")


if __name__ == "__main__":
    print("--- Datto RMM Data Syncer ---")
    try:
        config = get_config()
        DATTO_API_ENDPOINT = config.get('datto', 'api_endpoint')
        DATTO_PUBLIC_KEY = config.get('datto', 'public_key')
        DATTO_SECRET_KEY = config.get('datto', 'secret_key')
        NEXUS_USERNAME = config.get('nexus_auth', 'username')
        NEXUS_PASSWORD = config.get('nexus_auth', 'password')

        nexus_token = get_nexus_token(NEXUS_USERNAME, NEXUS_PASSWORD)
        if not nexus_token:
            sys.exit(1)

        datto_token = get_datto_access_token(DATTO_API_ENDPOINT, DATTO_PUBLIC_KEY, DATTO_SECRET_KEY)
        if not datto_token:
            sys.exit(1)

        sites = get_all_sites(DATTO_API_ENDPOINT, datto_token)
        if sites:
            process_datto_data(sites, datto_token, DATTO_API_ENDPOINT, nexus_token)
            print("\n--- Datto RMM Data Sync Successful ---")
        else:
            print("\nCould not retrieve sites list.")

    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)
