"""
Datto RMM API Client

Provides methods for interacting with Datto RMM API.
"""

import requests
import os
import configparser
from flask import current_app


class DattoClient:
    """Client for interacting with Datto RMM API."""

    def __init__(self):
        """Initialize client with credentials from config."""
        self.api_endpoint, self.api_key, self.api_secret = self._get_credentials()
        self.access_token = None
        self._authenticate()

    def _get_credentials(self):
        """Load Datto RMM credentials from config file."""
        config_path = os.path.join(current_app.instance_path, 'codex.conf')
        if not os.path.exists(config_path):
            raise ValueError(f"Config file not found: {config_path}")

        config = configparser.RawConfigParser()
        config.read(config_path)

        if not config.has_section('datto'):
            raise ValueError("Datto configuration not found in codex.conf")

        api_endpoint = config.get('datto', 'api_endpoint')
        api_key = config.get('datto', 'public_key')
        api_secret = config.get('datto', 'secret_key')

        if not all([api_endpoint, api_key, api_secret]):
            raise ValueError("Datto API credentials not fully configured")

        return api_endpoint, api_key, api_secret

    def _authenticate(self):
        """Authenticate with Datto RMM and get access token."""
        token_url = f"{self.api_endpoint}/auth/oauth/token"
        payload = {
            'grant_type': 'password',
            'username': self.api_key,
            'password': self.api_secret
        }
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': 'Basic cHVibGljLWNsaWVudDpwdWJsaWM='
        }

        try:
            response = requests.post(token_url, headers=headers, data=payload, timeout=30)
            response.raise_for_status()
            self.access_token = response.json().get("access_token")
            current_app.logger.info("Successfully authenticated with Datto RMM")
        except Exception as e:
            current_app.logger.error(f"Error authenticating with Datto: {e}")
            raise

    def get_all_sites(self):
        """
        Fetch all sites from Datto RMM.

        Returns:
            list: List of site dictionaries, or None on error
        """
        all_sites = []
        next_page_url = f"{self.api_endpoint}/api/v2/account/sites"
        headers = {'Authorization': f'Bearer {self.access_token}'}

        try:
            while next_page_url:
                response = requests.get(next_page_url, headers=headers, timeout=30)
                response.raise_for_status()
                data = response.json()
                all_sites.extend(data.get('sites', []))
                next_page_url = data.get('pageDetails', {}).get('nextPageUrl')

            return all_sites

        except Exception as e:
            current_app.logger.error(f"Error fetching Datto sites: {e}")
            return None

    def check_site_variable_exists(self, site_uid, variable_name):
        """
        Check if a specific variable exists for a site.

        Args:
            site_uid: Datto site UID
            variable_name: Name of the variable to check

        Returns:
            bool: True if variable exists, False otherwise
        """
        request_url = f"{self.api_endpoint}/api/v2/site/{site_uid}/variables"
        headers = {'Authorization': f'Bearer {self.access_token}'}

        try:
            response = requests.get(request_url, headers=headers, timeout=30)
            if response.status_code == 404:
                return False

            response.raise_for_status()
            variables = response.json().get("variables", [])

            for var in variables:
                if var.get("name") == variable_name:
                    return True

            return False

        except Exception as e:
            current_app.logger.warning(f"Could not check variables for site {site_uid}: {e}")
            return True  # Assume it exists to avoid overwriting

    def set_site_variable(self, site_uid, variable_name, variable_value):
        """
        Set a variable value for a Datto RMM site.

        Args:
            site_uid: Datto site UID
            variable_name: Name of the variable
            variable_value: Value to set

        Returns:
            bool: True if successful, False otherwise
        """
        request_url = f"{self.api_endpoint}/api/v2/site/{site_uid}/variable"
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        payload = {
            "name": variable_name,
            "value": str(variable_value)
        }

        try:
            response = requests.put(request_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            return True

        except Exception as e:
            current_app.logger.error(f"Error setting variable for site {site_uid}: {e}")
            if hasattr(e, 'response') and e.response:
                current_app.logger.error(f"Response: {e.response.text}")
            return False
