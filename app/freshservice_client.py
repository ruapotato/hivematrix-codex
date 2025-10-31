"""
FreshService API Client Helper

Provides on-demand ticket fetching and company management for FreshService API.
"""

import requests
import base64
import os
import time
import configparser
from flask import current_app


class FreshserviceClient:
    """Client for interacting with Freshservice API."""

    def __init__(self):
        """Initialize client with credentials from config."""
        self.base_url = "https://integotecllc.freshservice.com"
        self.api_key = self._get_credentials()
        self.headers = self._build_headers()

    def _get_credentials(self):
        """Load Freshservice API credentials from config file."""
        config_path = os.path.join(current_app.instance_path, 'codex.conf')
        if not os.path.exists(config_path):
            raise ValueError(f"Config file not found: {config_path}")

        config = configparser.RawConfigParser()
        config.read(config_path)

        if not config.has_section('freshservice'):
            raise ValueError("Freshservice configuration not found in codex.conf")

        api_key = config.get('freshservice', 'api_key')
        if not api_key:
            raise ValueError("Freshservice API key not configured")

        return api_key

    def _build_headers(self):
        """Build authorization headers for API requests."""
        auth_str = f"{self.api_key}:X"
        b64_auth = base64.b64encode(auth_str.encode()).decode()
        return {
            'Authorization': f'Basic {b64_auth}',
            'Content-Type': 'application/json'
        }

    def get_all_companies(self):
        """
        Fetch all companies (departments) from Freshservice.

        Returns:
            list: List of company dictionaries, or None on error
        """
        all_companies = []
        page = 1
        per_page = 100

        try:
            while True:
                response = requests.get(
                    f"{self.base_url}/api/v2/departments",
                    headers=self.headers,
                    params={'page': page, 'per_page': per_page},
                    timeout=30
                )

                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 5))
                    current_app.logger.warning(f"Rate limited, waiting {retry_after}s")
                    time.sleep(retry_after)
                    continue

                response.raise_for_status()
                data = response.json()
                companies = data.get('departments', [])

                if not companies:
                    break

                all_companies.extend(companies)

                if len(companies) < per_page:
                    break

                page += 1

            return all_companies

        except Exception as e:
            current_app.logger.error(f"Error fetching companies: {e}")
            return None

    def update_company_custom_field(self, company_id, field_name, field_value):
        """
        Update a custom field for a company/department.

        Args:
            company_id: Freshservice company/department ID
            field_name: Custom field name (e.g., 'account_number')
            field_value: Value to set

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # First, get the current department to see its structure
            get_response = requests.get(
                f"{self.base_url}/api/v2/departments/{company_id}",
                headers=self.headers,
                timeout=30
            )
            get_response.raise_for_status()
            current_dept = get_response.json().get('department', {})

            # Build payload - use entire department object with custom field updated
            payload = {
                "name": current_dept.get('name'),
                "description": current_dept.get('description'),
                "head_user_id": current_dept.get('head_user_id'),
                "prime_user_id": current_dept.get('prime_user_id'),
                "domains": current_dept.get('domains', []),
                "custom_fields": current_dept.get('custom_fields', {})
            }

            # Update the specific custom field
            payload['custom_fields'][field_name] = field_value

            response = requests.put(
                f"{self.base_url}/api/v2/departments/{company_id}",
                headers=self.headers,
                json=payload,
                timeout=30
            )

            response.raise_for_status()
            return True

        except Exception as e:
            current_app.logger.error(f"Error updating company {company_id}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                current_app.logger.error(f"Response status: {e.response.status_code}")
                current_app.logger.error(f"Response body: {e.response.text}")
            return False


# Legacy function for backward compatibility
def get_freshservice_credentials():
    """Load Freshservice API credentials from config file."""
    config_path = os.path.join(current_app.instance_path, 'codex.conf')
    if not os.path.exists(config_path):
        raise ValueError(f"Config file not found: {config_path}")

    config = configparser.RawConfigParser()
    config.read(config_path)

    if not config.has_section('freshservice'):
        raise ValueError("Freshservice configuration not found in codex.conf")

    api_key = config.get('freshservice', 'api_key')
    if not api_key:
        raise ValueError("Freshservice API key not configured")

    return api_key


def fetch_ticket_from_freshservice(ticket_id):
    """
    Fetch a single ticket from FreshService API.

    Args:
        ticket_id: The FreshService ticket ID

    Returns:
        dict: Ticket data in the format expected by Brain Hair, or None if not found
    """
    try:
        # Get credentials
        api_key = get_freshservice_credentials()

        # Set up auth header
        auth_str = f"{api_key}:X"
        b64_auth = base64.b64encode(auth_str.encode()).decode()
        headers = {
            'Authorization': f'Basic {b64_auth}',
            'Content-Type': 'application/json'
        }

        # Fetch ticket from FreshService
        base_url = "https://integotecllc.freshservice.com"
        response = requests.get(
            f"{base_url}/api/v2/tickets/{ticket_id}",
            headers=headers,
            timeout=30
        )

        if response.status_code == 404:
            return None

        response.raise_for_status()
        data = response.json()
        ticket = data.get('ticket', {})

        # Also fetch conversations
        conv_response = requests.get(
            f"{base_url}/api/v2/tickets/{ticket_id}/conversations",
            headers=headers,
            timeout=30
        )
        conversations = []
        if conv_response.status_code == 200:
            conversations = conv_response.json().get('conversations', [])

        # Map FreshService ticket to our format
        from models import Company

        # Try to find company by custom field
        company_id = None
        company_name = None
        custom_fields = ticket.get('custom_fields', {}) or {}
        account_number = custom_fields.get('account_number')

        if account_number:
            company = Company.query.get(str(account_number))
            if company:
                company_id = company.account_number
                company_name = company.name

        # Extract notes from conversations
        notes = []
        for conv in conversations:
            if conv.get('private'):  # Private notes only
                notes.append({
                    'created_at': conv.get('created_at'),
                    'text': conv.get('body_text', ''),
                    'user': conv.get('user_id')
                })

        # Map status codes to names
        status_map = {
            2: 'Open',
            3: 'Pending',
            4: 'Resolved',
            5: 'Closed'
        }

        # Map priority codes to names
        priority_map = {
            1: 'Low',
            2: 'Medium',
            3: 'High',
            4: 'Urgent'
        }

        return {
            'id': ticket.get('id'),
            'ticket_number': ticket.get('id'),  # FreshService doesn't have separate ticket numbers
            'subject': ticket.get('subject', ''),
            'description': ticket.get('description', ''),
            'description_text': ticket.get('description_text', ''),
            'status': status_map.get(ticket.get('status'), 'Unknown'),
            'priority': priority_map.get(ticket.get('priority'), 'Medium'),
            'company_id': company_id,
            'company_name': company_name,
            'requester_email': ticket.get('email', ''),
            'requester_name': ticket.get('name', ''),
            'created_at': ticket.get('created_at'),
            'last_updated_at': ticket.get('updated_at'),
            'closed_at': ticket.get('closed_at'),
            'total_hours_spent': 0,  # Would need separate API call to get time entries
            'conversations': conversations,
            'notes': notes,
            'source': 'freshservice'  # Mark that this came from FreshService
        }

    except Exception as e:
        current_app.logger.error(f"Error fetching ticket {ticket_id} from FreshService: {e}")
        return None
