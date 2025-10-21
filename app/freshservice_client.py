"""
FreshService API Client Helper

Provides on-demand ticket fetching from FreshService API.
"""

import requests
import base64
import os
import configparser
from flask import current_app


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
