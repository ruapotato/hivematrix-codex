#!/usr/bin/env python3
"""
Initialize Billing Plans and Features

Loads default billing plans and feature options from config.override.json
into the Codex database. This should be run once during setup or when
plans need to be reset/updated.
"""

import json
from app import app
from extensions import db
from models import BillingPlan, FeatureOption

# Column mapping from config array to model fields
# Based on config.override.json structure
PLAN_COLUMNS = [
    'plan_name',                      # 0
    'term_length',                    # 1
    'per_user_cost',                  # 2
    'per_workstation_cost',           # 3
    'per_server_cost',                # 4
    'per_vm_cost',                    # 5
    'per_switch_cost',                # 6
    'per_firewall_cost',              # 7
    'per_hour_ticket_cost',           # 8
    'backup_base_fee_workstation',    # 9
    'backup_base_fee_server',         # 10
    'backup_cost_per_gb_workstation', # 11
    'backup_cost_per_gb_server',      # 12
    'support_level',                  # 13
    'antivirus',                      # 14
    'soc',                            # 15
    'password_manager',               # 16
    'sat',                            # 17
    'email_security',                 # 18
    'network_management'              # 19
]


def load_config():
    """Load plans and features from config.override.json"""
    try:
        with open('config.override.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("ERROR: config.override.json not found")
        return None


def init_plans(app):
    """Initialize billing plans from config"""
    config = load_config()
    if not config:
        return False

    with app.app_context():
        # Clear existing plans
        print("Clearing existing billing plans...")
        BillingPlan.query.delete()

        # Load new plans
        plans_data = config.get('default_plans_data', [])
        print(f"Loading {len(plans_data)} billing plans...")

        for plan_array in plans_data:
            # Convert array to dict
            plan_dict = {}
            for i, col_name in enumerate(PLAN_COLUMNS):
                if i < len(plan_array):
                    plan_dict[col_name] = plan_array[i]

            # Create plan
            plan = BillingPlan(**plan_dict)
            db.session.add(plan)
            print(f"  + {plan_dict['plan_name']} ({plan_dict['term_length']})")

        db.session.commit()
        print(f"✓ Loaded {len(plans_data)} billing plans")
        return True


def init_features(app):
    """Initialize feature options from config"""
    config = load_config()
    if not config:
        return False

    with app.app_context():
        # Clear existing features
        print("\nClearing existing feature options...")
        FeatureOption.query.delete()

        # Load new features
        features_data = config.get('default_features', [])
        print(f"Loading {len(features_data)} feature options...")

        for feature_array in features_data:
            if len(feature_array) >= 2:
                category = feature_array[0]
                value = feature_array[1]

                feature = FeatureOption(
                    feature_category=category,
                    option_value=value
                )
                db.session.add(feature)
                print(f"  + {category}: {value}")

        db.session.commit()
        print(f"✓ Loaded {len(features_data)} feature options")
        return True


def main():
    """Main initialization function"""
    print("=" * 70)
    print("Initializing Billing Plans and Features")
    print("=" * 70)

    # Create tables if they don't exist
    with app.app_context():
        db.create_all()
        print("✓ Database tables created/verified\n")

    # Initialize plans
    if not init_plans(app):
        print("✗ Failed to initialize billing plans")
        return 1

    # Initialize features
    if not init_features(app):
        print("✗ Failed to initialize feature options")
        return 1

    print("\n" + "=" * 70)
    print("✓ Initialization complete!")
    print("=" * 70)
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
