import requests
import os
import sys
import time
import configparser
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Company, Asset

def get_db_session():
    """Creates a new SQLAlchemy session."""
    instance_path = os.environ.get('NEXUS_INSTANCE_PATH', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance'))
    db_path = os.path.join(instance_path, 'nexus_brainhair.db')
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found at {db_path}")
    # Add a timeout to the connection
    engine = create_engine(f'sqlite:///{db_path}', connect_args={'timeout': 15})
    Session = sessionmaker(bind=engine)
    return Session()

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

# --- Database Functions ---
def populate_assets_database(session, sites, access_token, api_endpoint):
    print("\nProcessing sites and devices...")
    for site in sites:
        # Try to find the company by its Datto Site UID first
        company = session.query(Company).filter_by(datto_site_uid=site['uid']).first()

        # If not found, try to find by name
        if not company:
            company = session.query(Company).filter_by(name=site['name']).first()

        if not company:
            print(f" -> Company '{site['name']}' not found in DB. Creating new entry.")
            company = Company(name=site['name'], datto_site_uid=site['uid'])
            session.add(company)
            session.commit() # Commit here to get a company ID for assets
        else:
            # Ensure the datto_site_uid is set if we found the company by name
            if not company.datto_site_uid:
                company.datto_site_uid = site['uid']
                session.commit()
            print(f" -> Found company '{site['name']}'. Fetching devices...")


        devices = get_devices_for_site(api_endpoint, access_token, site['uid'])
        if devices:
            print(f"   -> Found {len(devices)} devices. Updating database...")
            for device_data in devices:
                # Use a more specific query to find assets to avoid hostname conflicts between companies
                asset = session.query(Asset).filter_by(hostname=device_data['hostname'], company_id=company.id).first()
                if not asset:
                    asset = Asset(hostname=device_data['hostname'], company_id=company.id)
                    session.add(asset)

                # Update asset details
                asset.device_type = (device_data.get('deviceType') or {}).get('category')
                asset.operating_system = device_data.get('operatingSystem')
                asset.last_logged_in_user = device_data.get('lastLoggedInUser')

    session.commit()
    print(" -> Finished processing assets.")


# --- Main Execution ---
if __name__ == "__main__":
    print("--- Datto RMM Data Syncer ---")
    try:
        config = get_config()
        DATTO_API_ENDPOINT = config.get('datto', 'api_endpoint')
        DATTO_PUBLIC_KEY = config.get('datto', 'public_key')
        DATTO_SECRET_KEY = config.get('datto', 'secret_key')

        token = get_datto_access_token(DATTO_API_ENDPOINT, DATTO_PUBLIC_KEY, DATTO_SECRET_KEY)
        if not token:
            sys.exit("\n- Failed to obtain access token.")

        sites = get_all_sites(DATTO_API_ENDPOINT, token)
        if sites:
            db_session = get_db_session()
            try:
                populate_assets_database(db_session, sites, token, DATTO_API_ENDPOINT)
                print("\n--- Datto RMM Data Sync Successful ---")
            finally:
                db_session.close()
        else:
            print("\nCould not retrieve sites list.")

    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

