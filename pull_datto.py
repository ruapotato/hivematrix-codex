import requests
import os
import sys
import configparser
from datetime import datetime
import warnings

# Add the project root to the path so we can import models
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import db, Company, Asset, DattoSiteLink
from app import app

# Suppress InsecureRequestWarning for self-signed certs in development
from requests.packages.urllib3.exceptions import InsecureRequestWarning
warnings.simplefilter('ignore', InsecureRequestWarning)

# --- Configuration ---
DATTO_VARIABLE_NAME = "AccountNumber"

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

def get_datto_access_token(api_endpoint, api_key, api_secret_key):
    """Authenticates with Datto RMM and returns an access token."""
    token_url = f"{api_endpoint}/auth/oauth/token"
    payload = {
        'grant_type': 'password',
        'username': api_key,
        'password': api_secret_key
    }
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': 'Basic cHVibGljLWNsaWVudDpwdWJsaWM='
    }

    try:
        response = requests.post(token_url, headers=headers, data=payload, timeout=30)
        response.raise_for_status()
        print("Successfully obtained Datto RMM access token.")
        return response.json().get("access_token")
    except requests.exceptions.RequestException as e:
        print(f"Error getting Datto access token: {e}", file=sys.stderr)
        return None

def get_all_sites(api_endpoint, access_token):
    """Fetches all sites from Datto RMM."""
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
    """Fetches a specific variable for a site from Datto RMM."""
    request_url = f"{api_endpoint}/api/v2/site/{site_uid}/variables"
    headers = {'Authorization': f'Bearer {access_token}'}

    try:
        response = requests.get(request_url, headers=headers, timeout=30)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        variables = response.json().get("variables", [])
        for var in variables:
            if var.get("name") == variable_name:
                return var.get("value")
        return None
    except requests.exceptions.RequestException:
        return None

def get_devices_for_site(api_endpoint, access_token, site_uid):
    """Fetches all devices for a specific site UID from Datto RMM."""
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

def process_datto_data(sites, access_token, api_endpoint):
    """Processes Datto RMM data and syncs it with the Codex database."""
    print("\nGrouping Datto sites by AccountNumber...")

    sites_by_account = {}
    for site in sites:
        account_number = get_site_variable(api_endpoint, access_token, site['uid'], DATTO_VARIABLE_NAME)
        if account_number:
            if account_number not in sites_by_account:
                sites_by_account[account_number] = []
            sites_by_account[account_number].append(site)
        else:
            print(f" -> WARNING: No AccountNumber for site '{site['name']}'. Skipping.")

    print("Processing companies and their assets...")

    with app.app_context():
        for account_number, site_list in sites_by_account.items():
            company = db.session.get(Company, account_number)
            if not company:
                print(f" -> WARNING: Company with account '{account_number}' not in Codex. Skipping {len(site_list)} site(s).")
                continue

            print(f"\n--- Processing Company: {company.name} ({account_number}) ---")

            # Get existing assets for this company
            existing_assets = Asset.query.filter_by(company_account_number=account_number).all()
            existing_assets_by_hostname = {asset.hostname: asset for asset in existing_assets}

            all_datto_hostnames_for_company = set()

            for site in site_list:
                datto_uid = site.get('uid')
                site_name = site.get('name')

                # Link Datto site to company
                link = DattoSiteLink.query.filter_by(datto_site_uid=datto_uid).first()
                if not link:
                    link = DattoSiteLink(
                        company_account_number=account_number,
                        datto_site_uid=datto_uid
                    )
                    db.session.add(link)
                    db.session.commit()
                    print(f" -> Linked Datto site '{site_name}' to company '{company.name}'.")

                # Get devices for this site
                devices = get_devices_for_site(api_endpoint, access_token, datto_uid)
                if not devices:
                    continue

                print(f"   -> Found {len(devices)} devices for site '{site_name}'. Syncing...")

                for device_data in devices:
                    hostname = device_data.get('hostname')
                    if not hostname:
                        continue

                    all_datto_hostnames_for_company.add(hostname)

                    # Extract UDF fields
                    udf = device_data.get('udf', {})

                    # Check if asset exists
                    existing_asset = existing_assets_by_hostname.get(hostname)

                    if not existing_asset:
                        # Create new asset
                        asset = Asset(
                            hostname=hostname,
                            company_account_number=account_number
                        )
                        db.session.add(asset)
                        print(f"      -> Created asset '{hostname}'")
                    else:
                        asset = existing_asset

                    # Update asset fields
                    asset.datto_site_name = site_name
                    asset.operating_system = device_data.get('operatingSystem')
                    asset.last_logged_in_user = device_data.get('lastLoggedInUser')
                    asset.hardware_type = (device_data.get('deviceType') or {}).get('category')
                    asset.antivirus_product = (device_data.get('antivirus') or {}).get('antivirusProduct')
                    asset.description = device_data.get('description')
                    asset.ext_ip_address = device_data.get('extIpAddress')
                    asset.int_ip_address = device_data.get('intIpAddress')
                    asset.domain = device_data.get('domain')
                    asset.last_audit_date = format_timestamp(device_data.get('lastAuditDate'))
                    asset.last_reboot = format_timestamp(device_data.get('lastReboot'))
                    asset.last_seen = format_timestamp(device_data.get('lastSeen'))
                    asset.online = device_data.get('online')
                    asset.patch_status = (device_data.get('patchManagement') or {}).get('patchStatus')
                    asset.backup_usage_tb = bytes_to_tb(udf.get('udf6'))
                    asset.enabled_administrators = udf.get('udf4')
                    asset.device_type = udf.get('udf7')
                    asset.portal_url = device_data.get('portalUrl')
                    asset.web_remote_url = device_data.get('webRemoteUrl')

                    try:
                        db.session.commit()
                    except Exception as e:
                        print(f"      -> FAILED to sync asset '{hostname}': {e}", file=sys.stderr)
                        db.session.rollback()

            # Delete assets that no longer exist in Datto
            existing_hostnames = set(existing_assets_by_hostname.keys())
            hostnames_to_delete = existing_hostnames - all_datto_hostnames_for_company

            if hostnames_to_delete:
                print(f"   -> Found {len(hostnames_to_delete)} asset(s) to delete from Codex for '{company.name}'...")
                for hostname in hostnames_to_delete:
                    asset_to_delete = existing_assets_by_hostname[hostname]
                    try:
                        db.session.delete(asset_to_delete)
                        db.session.commit()
                        print(f"      -> Deleted asset '{hostname}' (ID: {asset_to_delete.id})")
                    except Exception as e:
                        print(f"      -> FAILED to delete asset '{hostname}': {e}", file=sys.stderr)
                        db.session.rollback()

    print("\n -> Finished processing all companies and assets.")

# --- Main Execution ---
if __name__ == "__main__":
    print("--- Datto RMM Data Syncer ---")
    try:
        config = get_config()
        DATTO_API_ENDPOINT = config.get('datto', 'api_endpoint')
        DATTO_PUBLIC_KEY = config.get('datto', 'public_key')
        DATTO_SECRET_KEY = config.get('datto', 'secret_key')

        # Get Datto access token
        datto_token = get_datto_access_token(DATTO_API_ENDPOINT, DATTO_PUBLIC_KEY, DATTO_SECRET_KEY)
        if not datto_token:
            print("FATAL: Could not obtain Datto RMM access token.", file=sys.stderr)
            sys.exit(1)

        # Get all sites
        sites = get_all_sites(DATTO_API_ENDPOINT, datto_token)
        if not sites:
            print("FATAL: Could not retrieve sites list from Datto RMM.", file=sys.stderr)
            sys.exit(1)

        # Process and sync data
        process_datto_data(sites, datto_token, DATTO_API_ENDPOINT)
        print("\n--- Datto RMM Data Sync Successful ---")

    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
