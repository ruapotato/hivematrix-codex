#!/usr/bin/env python3
"""
Rebuild Codex Database

This script will:
1. Drop all existing tables in the Codex database
2. Recreate all tables with the new schema
3. Initialize any necessary data

WARNING: This will delete ALL existing data!
"""

import sys
import os
from dotenv import load_dotenv

load_dotenv('.flaskenv')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from extensions import db

def rebuild_database():
    """Drop all tables and recreate with new schema."""
    print("="*80)
    print("Codex Database Rebuild")
    print("="*80)
    print("\nWARNING: This will DELETE ALL existing data in the Codex database!")
    print("This action cannot be undone.")

    response = input("\nType 'YES' to continue: ")
    if response != 'YES':
        print("\nAborted.")
        sys.exit(0)

    print("\nProceeding with database rebuild...")

    with app.app_context():
        print("\n1. Dropping all existing tables...")
        db.drop_all()
        print("   ✓ All tables dropped")

        print("\n2. Creating new schema...")
        db.create_all()
        print("   ✓ New schema created")

        print("\n3. Verifying tables...")
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()

        print(f"   ✓ Found {len(tables)} tables:")
        for table in sorted(tables):
            print(f"     - {table}")

    print("\n" + "="*80)
    print("Database rebuild complete!")
    print("="*80)
    print("\nNext steps:")
    print("1. Run: python pull_freshservice.py")
    print("2. Run: python pull_datto.py")
    print("3. Verify data in the Codex dashboard")

if __name__ == '__main__':
    rebuild_database()
