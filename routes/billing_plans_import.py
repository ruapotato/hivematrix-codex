"""
Billing plans importer for the new dictionary-based JSON format.
Supports dynamic features stored in the PlanFeature table.
"""
from models import BillingPlan, FeatureOption, PlanFeature, db
from app import helm_logger


def import_billing_data(data, skip_existing=True):
    """
    Import billing plans and features from JSON data (new dictionary format).

    Expected JSON structure:
    {
        "plans": [
            {
                "plan_name": "MSP Basic",
                "term_length": "Month to Month",
                "per_user_cost": 0.00,
                ...
                "features": {
                    "antivirus": "SentinelOne",
                    "soc": "Not Included"
                }
            }
        ],
        "feature_options": [
            {
                "feature_type": "antivirus",
                "display_name": "SentinelOne"
            }
        ]
    }

    Args:
        data: Dictionary with 'plans' and 'feature_options' keys
        skip_existing: If True, skip plans/features that already exist

    Returns:
        Dictionary with import statistics
    """
    stats = {
        'plans_imported': 0,
        'plans_skipped': 0,
        'plans_errors': 0,
        'features_imported': 0,
        'features_skipped': 0,
        'features_errors': 0,
        'errors': []
    }

    try:
        # Validate JSON structure
        if 'feature_options' not in data or 'plans' not in data:
            raise ValueError("Invalid JSON format. Expected 'plans' and 'feature_options' keys.")

        # Import feature options first (needed for validation)
        helm_logger.info(f"Processing {len(data['feature_options'])} feature options...")

        for feature_data in data['feature_options']:
            try:
                feature_type = feature_data.get('feature_type')
                display_name = feature_data.get('display_name')

                if not feature_type or not display_name:
                    stats['features_errors'] += 1
                    stats['errors'].append(f"Invalid feature data: missing feature_type or display_name")
                    continue

                # Check if exists
                if skip_existing:
                    existing = FeatureOption.query.filter_by(
                        feature_type=feature_type,
                        display_name=display_name
                    ).first()

                    if existing:
                        stats['features_skipped'] += 1
                        continue

                # Create new feature option
                feature = FeatureOption(
                    feature_type=feature_type,
                    display_name=display_name,
                    description=feature_data.get('description')
                )
                db.session.add(feature)
                stats['features_imported'] += 1

            except Exception as e:
                stats['features_errors'] += 1
                error_msg = f"Error importing feature option: {str(e)}"
                stats['errors'].append(error_msg)
                helm_logger.error(error_msg)

        # Commit feature options before importing plans
        db.session.commit()
        helm_logger.info(f"Feature options imported: {stats['features_imported']}, skipped: {stats['features_skipped']}, errors: {stats['features_errors']}")

        # Import billing plans
        helm_logger.info(f"Processing {len(data['plans'])} billing plans...")

        for plan_data in data['plans']:
            try:
                plan_name = plan_data.get('plan_name')
                term_length = plan_data.get('term_length')

                if not plan_name or not term_length:
                    stats['plans_errors'] += 1
                    stats['errors'].append(f"Invalid plan data: missing plan_name or term_length")
                    continue

                # Check if exists
                if skip_existing:
                    existing = BillingPlan.query.filter_by(
                        plan_name=plan_name,
                        term_length=term_length
                    ).first()

                    if existing:
                        stats['plans_skipped'] += 1
                        helm_logger.debug(f"Skipping existing plan: {plan_name} ({term_length})")
                        continue

                # Create billing plan with pricing data
                plan = BillingPlan(
                    plan_name=plan_name,
                    term_length=term_length,
                    per_user_cost=float(plan_data.get('per_user_cost', 0)),
                    per_workstation_cost=float(plan_data.get('per_workstation_cost', 0)),
                    per_server_cost=float(plan_data.get('per_server_cost', 0)),
                    per_vm_cost=float(plan_data.get('per_vm_cost', 0)),
                    per_switch_cost=float(plan_data.get('per_switch_cost', 0)),
                    per_firewall_cost=float(plan_data.get('per_firewall_cost', 0)),
                    per_hour_ticket_cost=float(plan_data.get('per_hour_ticket_cost', 0)),
                    backup_base_fee_workstation=float(plan_data.get('backup_base_fee_workstation', 0)),
                    backup_base_fee_server=float(plan_data.get('backup_base_fee_server', 0)),
                    backup_included_tb=float(plan_data.get('backup_included_tb', 1.0)),
                    backup_per_tb_fee=float(plan_data.get('backup_per_tb_fee', 0)),
                    support_level=plan_data.get('support_level', 'Billed Hourly')
                )
                db.session.add(plan)
                db.session.flush()  # Get the plan.id for features

                # Import dynamic features
                features = plan_data.get('features', {})
                for feature_type, feature_value in features.items():
                    plan_feature = PlanFeature(
                        plan_id=plan.id,
                        feature_type=feature_type,
                        feature_value=feature_value
                    )
                    db.session.add(plan_feature)

                stats['plans_imported'] += 1
                helm_logger.debug(f"Imported plan: {plan_name} ({term_length}) with {len(features)} features")

            except Exception as e:
                stats['plans_errors'] += 1
                error_msg = f"Error importing plan {plan_data.get('plan_name', 'unknown')}: {str(e)}"
                stats['errors'].append(error_msg)
                helm_logger.error(error_msg)

        # Commit all plans
        db.session.commit()
        helm_logger.info(f"Plans imported: {stats['plans_imported']}, skipped: {stats['plans_skipped']}, errors: {stats['plans_errors']}")

    except Exception as e:
        db.session.rollback()
        error_msg = f"Import failed: {str(e)}"
        stats['errors'].append(error_msg)
        helm_logger.error(error_msg)
        raise

    return stats
