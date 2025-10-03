#!/usr/bin/env python3
"""
Sync Ticket Details from Freshservice to Codex Database

This script fetches closed tickets from Freshservice and stores them in the Codex database.
It tracks the last sync timestamp to only pull new/updated tickets on subsequent runs.
"""

import requests
import base64
import os
import sys
import time
import argparse
import configparser
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add the parent directory to the path so we can import from app
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables from .flaskenv before importing app
from dotenv import load_dotenv
dotenv_path = Path(__file__).parent / '.flaskenv'
load_dotenv(dotenv_path)

from app import app
from extensions import db
from models import Company, TicketDetail

# Configuration
FRESHSERVICE_DOMAIN = "integotecllc.freshservice.com"
ACCOUNT_NUMBER_FIELD = "account_number"
MAX_RETRIES = 3
DEFAULT_TICKET_HOURS = 0.25  # 15 minutes default


def get_freshservice_credentials():
    """Load Freshservice API credentials from config file."""
    config_path = os.path.join(app.instance_path, 'codex.conf')
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


def get_latest_ticket_timestamp():
    """Gets the timestamp of the most recently updated ticket in the database."""
    latest = db.session.query(db.func.max(TicketDetail.last_updated_at)).scalar()

    if latest:
        try:
            dt = datetime.fromisoformat(latest.replace('Z', '+00:00'))
            return dt + timedelta(seconds=1)
        except:
            pass

    print("No existing tickets found. Performing initial sync for the past year.")
    return datetime.now(timezone.utc) - timedelta(days=365)


def get_company_map_from_api(base_url, headers):
    """Fetches all companies from Freshservice and returns a map of fs_id to account_number."""
    all_companies = []
    page = 1
    print("Fetching company map from Freshservice API...")

    while True:
        params = {'page': page, 'per_page': 100}
        try:
            response = requests.get(
                f"{base_url}/api/v2/departments",
                headers=headers,
                params=params,
                timeout=90
            )

            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 10))
                print(f"  -> Rate limit hit, waiting {retry_after}s...")
                time.sleep(retry_after)
                continue

            response.raise_for_status()
            data = response.json()
            companies_on_page = data.get('departments', [])

            if not companies_on_page:
                break

            all_companies.extend(companies_on_page)
            page += 1
            time.sleep(0.5)

        except requests.exceptions.RequestException as e:
            print(f"ERROR fetching companies: {e}", file=sys.stderr)
            return None

    # Build the mapping
    fs_id_to_account_map = {}
    for company in all_companies:
        fs_id = company.get('id')
        custom_fields = company.get('custom_fields', {}) or {}
        account_number = custom_fields.get(ACCOUNT_NUMBER_FIELD)

        if fs_id and account_number:
            fs_id_to_account_map[fs_id] = str(account_number)

    print(f"Successfully mapped {len(fs_id_to_account_map)} companies with account numbers.")
    return fs_id_to_account_map


def get_updated_tickets(base_url, headers, since_timestamp):
    """Fetch all closed tickets updated since the given timestamp."""
    all_tickets = []
    since_str = since_timestamp.strftime('%Y-%m-%dT%H:%M:%SZ')
    query = f"(updated_at:>'{since_str}' AND status:5)"  # Status 5 = Closed
    page = 1

    print(f"Fetching CLOSED tickets updated since {since_str}...")

    while True:
        params = {'query': f'"{query}"', 'page': page, 'per_page': 100}
        try:
            response = requests.get(
                f"{base_url}/api/v2/tickets/filter",
                headers=headers,
                params=params,
                timeout=90
            )

            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 10))
                print(f"  -> Rate limit hit, waiting {retry_after}s...")
                time.sleep(retry_after)
                continue

            response.raise_for_status()
            data = response.json()
            tickets_on_page = data.get('tickets', [])

            if not tickets_on_page:
                break

            all_tickets.extend(tickets_on_page)
            print(f"  -> Fetched page {page}, total tickets: {len(all_tickets)}")
            page += 1
            time.sleep(1)

        except requests.exceptions.RequestException as e:
            print(f"ERROR fetching tickets: {e}", file=sys.stderr)
            return None

    return all_tickets


def get_time_entries_for_ticket(base_url, headers, ticket_id):
    """Fetch total hours logged for a specific ticket."""
    total_hours = 0
    endpoint = f"{base_url}/api/v2/tickets/{ticket_id}/time_entries"
    retries = 0

    while retries < MAX_RETRIES:
        try:
            response = requests.get(endpoint, headers=headers, timeout=60)

            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 10))
                print(f"    [!] Rate limit on ticket #{ticket_id}. Retrying in {retry_after}s...")
                time.sleep(retry_after)
                retries += 1
                continue

            if response.status_code == 404:
                return 0

            response.raise_for_status()
            data = response.json()
            time_entries = data.get('time_entries', [])

            for entry in time_entries:
                time_str = entry.get('time_spent', '00:00')
                try:
                    parts = time_str.split(':')
                    if len(parts) == 2:
                        h, m = map(int, parts)
                        total_hours += h + (m / 60.0)
                    elif len(parts) == 3:
                        h, m, s = map(int, parts)
                        total_hours += h + (m / 60.0) + (s / 3600.0)
                except ValueError:
                    pass

            return total_hours

        except requests.exceptions.RequestException as e:
            print(f"  -> WARN: Could not fetch time for ticket {ticket_id}: {e}", file=sys.stderr)
            retries += 1
            time.sleep(5)

    print(f"  -> ERROR: Failed to fetch time for ticket {ticket_id} after {MAX_RETRIES} retries.", file=sys.stderr)
    return 0


def get_ticket_conversations(base_url, headers, ticket_id):
    """Fetch conversation history for a ticket."""
    endpoint = f"{base_url}/api/v2/tickets/{ticket_id}/conversations"
    retries = 0

    while retries < MAX_RETRIES:
        try:
            response = requests.get(endpoint, headers=headers, timeout=60)

            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 10))
                time.sleep(retry_after)
                retries += 1
                continue

            if response.status_code == 404:
                return []

            response.raise_for_status()
            data = response.json()
            return data.get('conversations', [])

        except requests.exceptions.RequestException as e:
            print(f"  -> WARN: Could not fetch conversations for ticket {ticket_id}: {e}", file=sys.stderr)
            retries += 1
            time.sleep(5)

    print(f"  -> ERROR: Failed to fetch conversations for ticket {ticket_id} after {MAX_RETRIES} retries.", file=sys.stderr)
    return []


def strip_html(html_content):
    """Remove HTML tags and return plain text."""
    if not html_content:
        return ""
    import re
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', html_content)
    # Decode HTML entities
    import html
    text = html.unescape(text)
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def sync_tickets(full_sync=False):
    """Main sync function."""
    with app.app_context():
        # Get Freshservice credentials
        try:
            api_key = get_freshservice_credentials()
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            print("\nPlease ensure Freshservice API credentials are configured in instance/codex.conf", file=sys.stderr)
            print("Add a section like:\n[freshservice]\napi_key = your_api_key_here", file=sys.stderr)
            return 1

        # Setup API authentication
        base_url = f"https://{FRESHSERVICE_DOMAIN}"
        auth_str = f"{api_key}:X"
        encoded_auth = base64.b64encode(auth_str.encode()).decode()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Basic {encoded_auth}"
        }

        # Get company mapping
        fs_id_to_account_map = get_company_map_from_api(base_url, headers)
        if not fs_id_to_account_map:
            print("ERROR: Could not build company map. Aborting.", file=sys.stderr)
            return 1

        # Determine sync start time
        if full_sync:
            print("Full sync requested. Clearing existing ticket data...")
            TicketDetail.query.delete()
            db.session.commit()
            last_sync_time = datetime.now(timezone.utc) - timedelta(days=365)
        else:
            last_sync_time = get_latest_ticket_timestamp()

        # Fetch tickets
        tickets = get_updated_tickets(base_url, headers, last_sync_time)
        if tickets is None:
            print("ERROR: Failed to fetch tickets. Aborting.", file=sys.stderr)
            return 1

        if not tickets:
            print("\nNo new or updated tickets found.")
            return 0

        # Process tickets
        print(f"\nProcessing {len(tickets)} tickets and fetching time entries...")
        processed = 0

        for ticket in tickets:
            department_id = ticket.get('department_id')
            account_number = fs_id_to_account_map.get(department_id)

            if not account_number:
                continue

            ticket_id = ticket['id']
            print(f"  -> Processing Ticket #{ticket_id}...")

            # Fetch time entries
            total_hours = get_time_entries_for_ticket(base_url, headers, ticket_id)

            if total_hours == 0:
                total_hours = DEFAULT_TICKET_HOURS
                print(f"    -> No time entries found. Assigning default {DEFAULT_TICKET_HOURS} hours.")

            # Fetch conversation history
            print(f"    -> Fetching conversation history...")
            conversations = get_ticket_conversations(base_url, headers, ticket_id)

            # Create or update ticket record
            ticket_record = TicketDetail.query.get(ticket_id)
            if not ticket_record:
                ticket_record = TicketDetail(ticket_id=ticket_id)

            ticket_record.company_account_number = account_number
            ticket_record.ticket_number = str(ticket_id)
            ticket_record.subject = ticket.get('subject', 'No Subject')
            ticket_record.description = ticket.get('description', '')
            ticket_record.description_text = strip_html(ticket.get('description_text') or ticket.get('description', ''))
            ticket_record.status = ticket.get('status_name', 'Closed')
            ticket_record.priority = ticket.get('priority_name', 'Medium')
            ticket_record.requester_email = ticket.get('requester', {}).get('email') if isinstance(ticket.get('requester'), dict) else None
            ticket_record.requester_name = ticket.get('requester', {}).get('name') if isinstance(ticket.get('requester'), dict) else None
            ticket_record.created_at = ticket.get('created_at')
            ticket_record.last_updated_at = ticket.get('updated_at')
            ticket_record.closed_at = ticket.get('updated_at')
            ticket_record.total_hours_spent = total_hours

            # Store conversations as JSON
            import json
            conversation_data = []
            note_data = []

            for conv in conversations:
                conv_entry = {
                    'id': conv.get('id'),
                    'body': strip_html(conv.get('body', '')),
                    'body_html': conv.get('body', ''),
                    'from_email': conv.get('from_email'),
                    'to_emails': conv.get('to_emails', []),
                    'created_at': conv.get('created_at'),
                    'updated_at': conv.get('updated_at'),
                    'incoming': conv.get('incoming', False),
                    'private': conv.get('private', False),
                    'user_id': conv.get('user_id'),
                    'support_email': conv.get('support_email')
                }

                # Separate private notes from public conversations
                if conv.get('private'):
                    note_data.append(conv_entry)
                else:
                    conversation_data.append(conv_entry)

            ticket_record.conversations = json.dumps(conversation_data) if conversation_data else None
            ticket_record.notes = json.dumps(note_data) if note_data else None

            print(f"    -> Stored {len(conversation_data)} conversations and {len(note_data)} notes")

            db.session.add(ticket_record)
            processed += 1

            # Commit in batches
            if processed % 50 == 0:
                db.session.commit()
                print(f"  -> Committed {processed} tickets so far...")

        # Final commit
        db.session.commit()
        print(f"\n✓ Successfully synced {processed} tickets.")

        return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync ticket details from Freshservice to Codex.")
    parser.add_argument('--full-sync', action='store_true', help="Force a full sync of all tickets from the past year.")
    args = parser.parse_args()

    print("--- Codex Ticket Sync Script ---")
    exit_code = sync_tickets(full_sync=args.full_sync)
    sys.exit(exit_code)
