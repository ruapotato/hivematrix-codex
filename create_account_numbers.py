#!/usr/bin/env python3
"""
Create Account Numbers for Freshservice Companies

This script assigns unique 6-digit account numbers to companies in Freshservice
that don't already have one. It uses the Freshservice API directly and updates
the Codex database after successful assignments.

Auto-run: This should run automatically after Freshservice sync completes.
"""

import sys
import os
import random
import time

# Add app directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.freshservice_client import FreshserviceClient
from app import app
from models import Company
from extensions import db


def get_existing_account_numbers():
    """Get all existing account numbers from database."""
    with app.app_context():
        companies = Company.query.filter(Company.account_number.isnot(None)).all()
        return {int(c.account_number) for c in companies if c.account_number}


def create_account_numbers():
    """Main function to create account numbers for companies that need them."""
    print("=" * 60)
    print("CREATE ACCOUNT NUMBERS FOR FRESHSERVICE COMPANIES")
    print("=" * 60)

    with app.app_context():
        # Initialize Freshservice client
        fs_client = FreshserviceClient()

        # Get all companies from Freshservice
        print("\n1. Fetching companies from Freshservice...")
        fs_companies = fs_client.get_all_companies()
        if not fs_companies:
            print("ERROR: Could not fetch companies from Freshservice")
            return False

        print(f"   Found {len(fs_companies)} total companies")

        # Get existing account numbers
        existing_numbers = get_existing_account_numbers()
        print(f"   Found {len(existing_numbers)} existing account numbers")

        # Find companies that need account numbers
        companies_to_update = []
        for company in fs_companies:
            custom_fields = company.get('custom_fields', {})
            acc_num = custom_fields.get('account_number')
            if not acc_num:
                companies_to_update.append(company)

        print(f"   Found {len(companies_to_update)} companies needing account numbers\n")

        if not companies_to_update:
            print("✓ All companies already have account numbers!")
            return True

        # Assign new account numbers
        print("2. Assigning new account numbers...")
        updated_count = 0
        failed_count = 0

        for company in companies_to_update:
            company_id = company['id']
            company_name = company['name']

            # Generate unique 6-digit number
            new_number = None
            while new_number is None or new_number in existing_numbers:
                new_number = random.randint(100000, 999999)

            print(f"   → {company_name}: {new_number}")

            # Update in Freshservice
            success = fs_client.update_company_custom_field(
                company_id,
                'account_number',
                str(new_number)
            )

            if success:
                existing_numbers.add(new_number)
                updated_count += 1

                # Update in Codex database
                db_company = Company.query.filter_by(name=company_name).first()
                if db_company:
                    db_company.account_number = str(new_number)
                    try:
                        db.session.commit()
                    except Exception as e:
                        print(f"      Warning: Failed to update database: {e}")
                        db.session.rollback()

                # Be nice to the API
                time.sleep(0.5)
            else:
                print(f"      ERROR: Failed to update {company_name}")
                failed_count += 1

        # Summary
        print("\n" + "=" * 60)
        print(f"✓ Successfully assigned {updated_count} account numbers")
        if failed_count > 0:
            print(f"✗ Failed to assign {failed_count} account numbers")
        print("=" * 60)

        return failed_count == 0


if __name__ == "__main__":
    success = create_account_numbers()
    sys.exit(0 if success else 1)
