import requests
import os
import sys
import configparser
import json
import pprint

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
    """Authenticates with Datto RMM and returns an access token."""
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

def get_devices_for_site(api_endpoint, access_token, site_uid):
    """Fetches all devices for a specific site UID."""
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

if __name__ == "__main__":
    try:
        config = get_config()
        DATTO_API_ENDPOINT = config.get('datto', 'api_endpoint')
        DATTO_PUBLIC_KEY = config.get('datto', 'public_key')
        DATTO_SECRET_KEY = config.get('datto', 'secret_key')

        token = get_datto_access_token(DATTO_API_ENDPOINT, DATTO_PUBLIC_KEY, DATTO_SECRET_KEY)
        if not token:
            sys.exit("\nFailed to obtain access token. Please check your credentials in nexus.conf.")

        all_sites_data = get_all_sites(DATTO_API_ENDPOINT, token)
        if not all_sites_data:
            sys.exit("Could not retrieve site list from Datto RMM.")

        while True:
            search_type = input("\nSearch for a 'site' or a 'device'? (or 'exit' to quit): ").lower()
            if search_type == 'exit':
                break

            if search_type == 'site':
                site_name = input("Enter the site name to search for: ")
                found_site = None
                for site in all_sites_data:
                    if site_name.lower() in site.get('name', '').lower():
                        found_site = site
                        break

                if found_site:
                    print(f"\n--- Data for Site: {found_site['name']} ---")
                    pprint.pprint(found_site)
                else:
                    print(f"No site found with the name '{site_name}'.")

            elif search_type == 'device':
                hostname = input("Enter the device hostname to search for: ")
                found_device = None
                print("Searching for device across all sites (this may take a moment)...")
                for site in all_sites_data:
                    devices = get_devices_for_site(DATTO_API_ENDPOINT, token, site['uid'])
                    if devices:
                        for device in devices:
                            if hostname.lower() == device.get('hostname', '').lower():
                                found_device = device
                                print(f"Found device in site: {site['name']}")
                                break
                    if found_device:
                        break

                if found_device:
                    print(f"\n--- Data for Device: {found_device['hostname']} ---")
                    pprint.pprint(found_device)
                else:
                    print(f"No device found with the hostname '{hostname}'.")

            else:
                print("Invalid input. Please enter 'site', 'device', or 'exit'.")

    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)
