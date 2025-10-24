#!/usr/bin/env python3
"""
Push Account Numbers to Datto RMM

This script syncs account numbers from Codex/Freshservice to Datto RMM sites
as site variables. It matches Datto site names to Freshservice company names
and pushes the AccountNumber variable.

Special cases:
- "Redbarn" in Datto → "Redbarn Cannabis" in Freshservice

Auto-run: This should run automatically after Datto sync completes.
"""

import sys
import os
import time

# Add app directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from app.datto_client import DattoClient
from models import Company
from extensions import db


# Special mapping rules
REDBARN_KEYWORD = "Redbarn"
REDBARN_FRESHSERVICE_TARGET = "Redbarn Cannabis"
DATTO_VARIABLE_NAME = "AccountNumber"


def push_account_numbers():
    """Main function to push account numbers from Codex to Datto RMM."""
    print("=" * 60)
    print("PUSH ACCOUNT NUMBERS TO DATTO RMM")
    print("=" * 60)

    with app.app_context():
        # Initialize Datto client
        datto_client = DattoClient()

        # Get all companies from Codex database
        print("\n1. Loading companies from Codex database...")
        companies = Company.query.filter(Company.account_number.isnot(None)).all()
        company_map = {c.name.strip(): c.account_number for c in companies if c.name}
        print(f"   Found {len(company_map)} companies with account numbers")

        # Get all sites from Datto RMM
        print("\n2. Fetching sites from Datto RMM...")
        datto_sites = datto_client.get_all_sites()
        if not datto_sites:
            print("ERROR: Could not fetch sites from Datto RMM")
            return False

        print(f"   Found {len(datto_sites)} Datto RMM sites\n")

        # Match Datto sites to Freshservice companies
        actions = []
        unmapped_sites = []

        print("3. Matching Datto sites to Freshservice companies...")
        for site in datto_sites:
            datto_name = (site.get('name') or '').strip()
            datto_uid = site.get('uid')
            fs_name_match = None

            # Special case: Redbarn
            if REDBARN_KEYWORD in datto_name:
                fs_name_match = REDBARN_FRESHSERVICE_TARGET
            else:
                # Find longest matching Freshservice name in Datto site name
                # This prevents "A" from matching "A-1 Movers" if both exist
                best_match = ''
                for fs_name in company_map.keys():
                    if fs_name in datto_name and len(fs_name) > len(best_match):
                        best_match = fs_name
                if best_match:
                    fs_name_match = best_match

            if fs_name_match and fs_name_match in company_map:
                account_number = company_map[fs_name_match]
                actions.append({
                    'datto_site_name': datto_name,
                    'datto_site_uid': datto_uid,
                    'account_number': account_number,
                    'fs_company_name': fs_name_match
                })
            else:
                unmapped_sites.append(datto_name)

        print(f"   Matched {len(actions)} sites")
        print(f"   Unmapped {len(unmapped_sites)} sites\n")

        # Push account numbers to Datto
        print("4. Pushing account numbers to Datto RMM...")
        success_count = 0
        fail_count = 0
        already_set_count = 0

        for action in sorted(actions, key=lambda x: x['datto_site_name']):
            datto_name = action['datto_site_name']
            datto_uid = action['datto_site_uid']
            acc_num = action['account_number']
            fs_name = action['fs_company_name']

            print(f"   → {datto_name} ({fs_name}): {acc_num}")

            # Check if variable already exists
            if datto_client.check_site_variable_exists(datto_uid, DATTO_VARIABLE_NAME):
                print("      ℹ  Already set, skipping")
                already_set_count += 1
                continue

            # Push the variable
            success = datto_client.set_site_variable(
                datto_uid,
                DATTO_VARIABLE_NAME,
                str(acc_num)
            )

            if success:
                print("      ✓ Success")
                success_count += 1
            else:
                print("      ✗ Failed")
                fail_count += 1

            # Be nice to the API
            time.sleep(0.5)

        # Summary
        print("\n" + "=" * 60)
        print(f"✓ Successfully pushed {success_count} account numbers")
        print(f"ℹ  Skipped {already_set_count} sites (already set)")
        if fail_count > 0:
            print(f"✗ Failed to push {fail_count} account numbers")
        print("=" * 60)

        if unmapped_sites:
            print("\nUnmapped Datto Sites (no matching company):")
            for name in sorted(unmapped_sites):
                print(f"  - {name}")

        return fail_count == 0


if __name__ == "__main__":
    success = push_account_numbers()
    sys.exit(0 if success else 1)
