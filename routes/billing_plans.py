from flask import Blueprint, render_template, g, request, redirect, url_for, flash, jsonify
from app.auth import token_required, admin_required
from models import db, BillingPlan, FeatureOption, PlanFeature
from collections import defaultdict

billing_plans_bp = Blueprint('billing_plans', __name__, url_prefix='/billing-plans')

@billing_plans_bp.route('/')
@token_required
def list_plans():
    """View and manage billing plans."""
    # Get all plans grouped by plan name
    all_plans = BillingPlan.query.order_by(BillingPlan.plan_name, BillingPlan.term_length).all()

    grouped_plans = defaultdict(list)
    for plan in all_plans:
        # Load dynamic features into a dictionary for easy access in template
        plan.feature_dict = {}
        for plan_feature in plan.features:
            plan.feature_dict[plan_feature.feature_type] = plan_feature.feature_value

        grouped_plans[plan.plan_name].append(plan)

    # Get feature options grouped by category
    all_features = FeatureOption.query.order_by(FeatureOption.feature_type, FeatureOption.display_name).all()

    feature_options = defaultdict(list)
    feature_types = set()
    for feature in all_features:
        feature_options[feature.feature_type].append(feature)
        feature_types.add(feature.feature_type)

    feature_types = sorted(list(feature_types))

    return render_template('billing_plans/list.html',
                         user=g.user,
                         grouped_plans=grouped_plans,
                         feature_options=feature_options,
                         feature_types=feature_types)


@billing_plans_bp.route('/save', methods=['POST'])
@admin_required
def save_plans():
    """Save changes to billing plans."""
    plan_name = request.form.get('plan_name')
    plan_ids = request.form.getlist('plan_ids')
    bulk_edit = request.form.get('bulk_edit', 'false') == 'true'

    try:
        # If bulk edit mode, get values from first plan and apply to all
        if bulk_edit and len(plan_ids) > 0:
            first_plan_id = plan_ids[0]

            # Read values from first plan
            values = {
                'per_user_cost': float(request.form.get(f'per_user_cost_{first_plan_id}', 0)),
                'per_workstation_cost': float(request.form.get(f'per_workstation_cost_{first_plan_id}', 0)),
                'per_server_cost': float(request.form.get(f'per_server_cost_{first_plan_id}', 0)),
                'per_vm_cost': float(request.form.get(f'per_vm_cost_{first_plan_id}', 0)),
                'per_switch_cost': float(request.form.get(f'per_switch_cost_{first_plan_id}', 0)),
                'per_firewall_cost': float(request.form.get(f'per_firewall_cost_{first_plan_id}', 0)),
                'per_hour_ticket_cost': float(request.form.get(f'per_hour_ticket_cost_{first_plan_id}', 0)),
                'backup_base_fee_workstation': float(request.form.get(f'backup_base_fee_workstation_{first_plan_id}', 0)),
                'backup_base_fee_server': float(request.form.get(f'backup_base_fee_server_{first_plan_id}', 0)),
                'backup_included_tb': float(request.form.get(f'backup_included_tb_{first_plan_id}', 1.0)),
                'backup_per_tb_fee': float(request.form.get(f'backup_per_tb_fee_{first_plan_id}', 0)),
                'support_level': request.form.get(f'support_level_{first_plan_id}', 'Billed Hourly')
            }

            # Get all feature types and their values from first plan
            feature_values = {}
            all_features = FeatureOption.query.with_entities(FeatureOption.feature_type).distinct().all()
            for (feature_type,) in all_features:
                feature_values[feature_type] = request.form.get(f'feature_{feature_type}_{first_plan_id}', 'Not Included')

            # Apply to all plans
            for plan_id in plan_ids:
                plan = BillingPlan.query.get(int(plan_id))
                if not plan:
                    continue

                # Apply pricing values
                for key, value in values.items():
                    setattr(plan, key, value)

                # Apply feature values using PlanFeature table
                for feature_type, feature_value in feature_values.items():
                    plan_feature = PlanFeature.query.filter_by(
                        plan_id=plan.id,
                        feature_type=feature_type
                    ).first()

                    if plan_feature:
                        plan_feature.feature_value = feature_value
                    else:
                        plan_feature = PlanFeature(
                            plan_id=plan.id,
                            feature_type=feature_type,
                            feature_value=feature_value
                        )
                        db.session.add(plan_feature)
        else:
            # Normal save - each plan individually
            for plan_id in plan_ids:
                plan = BillingPlan.query.get(int(plan_id))
                if not plan:
                    continue

                # Update costs
                plan.per_user_cost = float(request.form.get(f'per_user_cost_{plan_id}', 0))
                plan.per_workstation_cost = float(request.form.get(f'per_workstation_cost_{plan_id}', 0))
                plan.per_server_cost = float(request.form.get(f'per_server_cost_{plan_id}', 0))
                plan.per_vm_cost = float(request.form.get(f'per_vm_cost_{plan_id}', 0))
                plan.per_switch_cost = float(request.form.get(f'per_switch_cost_{plan_id}', 0))
                plan.per_firewall_cost = float(request.form.get(f'per_firewall_cost_{plan_id}', 0))
                plan.per_hour_ticket_cost = float(request.form.get(f'per_hour_ticket_cost_{plan_id}', 0))
                plan.backup_base_fee_workstation = float(request.form.get(f'backup_base_fee_workstation_{plan_id}', 0))
                plan.backup_base_fee_server = float(request.form.get(f'backup_base_fee_server_{plan_id}', 0))
                plan.backup_included_tb = float(request.form.get(f'backup_included_tb_{plan_id}', 1.0))
                plan.backup_per_tb_fee = float(request.form.get(f'backup_per_tb_fee_{plan_id}', 0))

                # Update support level
                plan.support_level = request.form.get(f'support_level_{plan_id}', 'Billed Hourly')

                # Update features dynamically using PlanFeature table
                all_features = FeatureOption.query.with_entities(FeatureOption.feature_type).distinct().all()
                for (feature_type,) in all_features:
                    feature_value = request.form.get(f'feature_{feature_type}_{plan_id}', 'Not Included')

                    # Find or create PlanFeature record
                    plan_feature = PlanFeature.query.filter_by(
                        plan_id=plan.id,
                        feature_type=feature_type
                    ).first()

                    if plan_feature:
                        plan_feature.feature_value = feature_value
                    else:
                        plan_feature = PlanFeature(
                            plan_id=plan.id,
                            feature_type=feature_type,
                            feature_value=feature_value
                        )
                        db.session.add(plan_feature)

        db.session.commit()

        if bulk_edit:
            flash(f'✓ Saved changes to {plan_name} (bulk edit applied to all terms)', 'success')
        else:
            flash(f'✓ Saved changes to {plan_name}', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'✗ Error saving plans: {str(e)}', 'error')

    return redirect(url_for('billing_plans.list_plans'))


@billing_plans_bp.route('/delete', methods=['POST'])
@admin_required
def delete_plan():
    """Delete an entire billing plan (all terms)."""
    plan_name = request.form.get('plan_name')

    try:
        deleted_count = BillingPlan.query.filter_by(plan_name=plan_name).delete()
        db.session.commit()
        flash(f'✓ Deleted {plan_name} ({deleted_count} terms)', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'✗ Error deleting plan: {str(e)}', 'error')

    return redirect(url_for('billing_plans.list_plans'))


@billing_plans_bp.route('/create', methods=['POST'])
@admin_required
def create_plan():
    """Create a new billing plan."""
    new_plan_name = request.form.get('new_plan_name', '').strip()

    if not new_plan_name:
        flash('✗ Plan name is required', 'error')
        return redirect(url_for('billing_plans.list_plans'))

    try:
        # Create plan for all 4 term lengths
        terms = ['Month to Month', '1-Year', '2-Year', '3-Year']
        for term in terms:
            plan = BillingPlan(
                plan_name=new_plan_name,
                term_length=term,
                per_user_cost=0,
                per_workstation_cost=0,
                per_server_cost=0,
                per_vm_cost=0,
                per_switch_cost=0,
                per_firewall_cost=0,
                per_hour_ticket_cost=90,
                backup_base_fee_workstation=25,
                backup_base_fee_server=50,
                backup_included_tb=1.0,
                backup_per_tb_fee=15.0,
                support_level='Billed Hourly',
                antivirus='Not Included',
                soc='Not Included',
                password_manager='Not Included',
                sat='Not Included',
                email_security='Not Included',
                network_management='Not Included'
            )
            db.session.add(plan)

        db.session.commit()
        flash(f'✓ Created new plan: {new_plan_name}', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'✗ Error creating plan: {str(e)}', 'error')

    return redirect(url_for('billing_plans.list_plans'))


@billing_plans_bp.route('/features/categories/add', methods=['POST'])
@admin_required
def add_feature_category():
    """Add a new feature category."""
    category_name = request.form.get('category_name', '').strip()

    if not category_name:
        flash('✗ Category name is required', 'error')
        return redirect(url_for('billing_plans.list_plans'))

    try:
        # Convert to snake_case for database storage
        category_key = category_name.lower().replace(' ', '_')

        # Check if category already exists
        existing = FeatureOption.query.filter_by(feature_type=category_key).first()
        if existing:
            flash(f'✗ Category "{category_name}" already exists', 'error')
            return redirect(url_for('billing_plans.list_plans'))

        # Create a default "Not Included" option for this category
        feature = FeatureOption(
            feature_type=category_key,
            display_name='Not Included',
            description=None
        )
        db.session.add(feature)
        db.session.commit()
        flash(f'✓ Created new category: {category_name}', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'✗ Error creating category: {str(e)}', 'error')

    return redirect(url_for('billing_plans.list_plans'))


@billing_plans_bp.route('/features/add', methods=['POST'])
@admin_required
def add_feature_option():
    """Add a new feature option."""
    feature_category = request.form.get('feature_type')
    option_value = request.form.get('option_name', '').strip()

    if not option_value:
        flash('✗ Option name is required', 'error')
        return redirect(url_for('billing_plans.list_plans'))

    try:
        feature = FeatureOption(
            feature_type=feature_category,
            display_name=option_value,
            description=None
        )
        db.session.add(feature)
        db.session.commit()
        flash(f'✓ Added {option_value} to {feature_category}', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'✗ Error adding feature: {str(e)}', 'error')

    return redirect(url_for('billing_plans.list_plans'))


@billing_plans_bp.route('/features/<int:option_id>/edit', methods=['POST'])
@admin_required
def edit_feature_option(option_id):
    """Edit a feature option."""
    new_name = request.form.get('option_name', '').strip()

    if not new_name:
        flash('✗ Option name is required', 'error')
        return redirect(url_for('billing_plans.list_plans'))

    try:
        feature = FeatureOption.query.get(option_id)
        if feature:
            feature.display_name = new_name
            db.session.commit()
            flash(f'✓ Updated feature option', 'success')
        else:
            flash('✗ Feature option not found', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'✗ Error updating feature: {str(e)}', 'error')

    return redirect(url_for('billing_plans.list_plans'))


@billing_plans_bp.route('/features/<int:option_id>/delete', methods=['POST'])
@admin_required
def delete_feature_option(option_id):
    """Delete a feature option."""
    try:
        feature = FeatureOption.query.get(option_id)
        if feature:
            db.session.delete(feature)
            db.session.commit()
            flash(f'✓ Deleted feature option', 'success')
        else:
            flash('✗ Feature option not found', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'✗ Error deleting feature: {str(e)}', 'error')

    return redirect(url_for('billing_plans.list_plans'))


@billing_plans_bp.route('/api/bulk-plans', methods=['GET'])
@token_required
def bulk_plans_api():
    """
    Bulk export API: Returns all unique billing plan configurations.
    Returns plan_name+term_length -> features mapping for all plans.
    This allows Ledger to fetch all plan data in ONE call.
    """
    from models import Company

    # Get all unique plan+term combinations from companies
    companies = Company.query.all()
    unique_plans = {}

    for company in companies:
        plan_name = company.billing_plan
        term = company.contract_term_length or 'Month to Month'

        if not plan_name:
            continue

        cache_key = f"{plan_name}|{term}"

        if cache_key not in unique_plans:
            # Fetch plan details from database
            plan = BillingPlan.query.filter_by(
                plan_name=plan_name,
                term_length=term
            ).first()

            if plan:
                unique_plans[cache_key] = {
                    'plan_name': plan.plan_name,
                    'term_length': plan.term_length,
                    'support_level': plan.support_level,
                    'antivirus': plan.antivirus or 'Not Included',
                    'soc': plan.soc or 'Not Included',
                    'password_manager': plan.password_manager or 'Not Included',
                    'sat': plan.sat or 'Not Included',
                    'email_security': plan.email_security or 'Not Included',
                    'network_management': plan.network_management or 'Not Included',
                }

    return jsonify({
        'plans': unique_plans
    })


@billing_plans_bp.route('/export', methods=['GET'])
@admin_required
def export_plans():
    """Export all billing plans and feature options to JSON (dynamic feature format)."""
    from flask import make_response
    import json

    # Get all billing plans
    all_plans = BillingPlan.query.order_by(BillingPlan.plan_name, BillingPlan.term_length).all()

    # Get all feature options
    all_features = FeatureOption.query.order_by(FeatureOption.feature_type, FeatureOption.display_name).all()

    # Format plans data - NEW DICTIONARY FORMAT (not hardcoded)
    plans_data = []
    for plan in all_plans:
        plan_dict = {
            'plan_name': plan.plan_name,
            'term_length': plan.term_length,
            'per_user_cost': float(plan.per_user_cost or 0),
            'per_workstation_cost': float(plan.per_workstation_cost or 0),
            'per_server_cost': float(plan.per_server_cost or 0),
            'per_vm_cost': float(plan.per_vm_cost or 0),
            'per_switch_cost': float(plan.per_switch_cost or 0),
            'per_firewall_cost': float(plan.per_firewall_cost or 0),
            'per_hour_ticket_cost': float(plan.per_hour_ticket_cost or 0),
            'backup_base_fee_workstation': float(plan.backup_base_fee_workstation or 0),
            'backup_base_fee_server': float(plan.backup_base_fee_server or 0),
            'backup_included_tb': float(plan.backup_included_tb or 1.0),
            'backup_per_tb_fee': float(plan.backup_per_tb_fee or 0),
            'support_level': plan.support_level or 'Billed Hourly',
            'features': {}
        }

        # Add dynamic features
        for plan_feature in plan.features:
            plan_dict['features'][plan_feature.feature_type] = plan_feature.feature_value

        plans_data.append(plan_dict)

    # Format features data
    features_data = []
    for feature in all_features:
        features_data.append({
            'feature_type': feature.feature_type,
            'display_name': feature.display_name
        })

    export_data = {
        "plans": plans_data,
        "feature_options": features_data
    }

    # Create response with JSON file
    response = make_response(json.dumps(export_data, indent=4))
    response.headers['Content-Type'] = 'application/json'
    response.headers['Content-Disposition'] = 'attachment; filename=billing_plans_export.json'

    return response


@billing_plans_bp.route('/copy-terms', methods=['POST'])
@admin_required
def copy_terms():
    """Copy values from one term to all other terms for a plan."""
    plan_name = request.form.get('plan_name')
    source_term = request.form.get('source_term')

    if not plan_name or not source_term:
        flash('✗ Missing plan name or source term', 'error')
        return redirect(url_for('billing_plans.list_plans'))

    try:
        # Get the source plan
        source_plan = BillingPlan.query.filter_by(
            plan_name=plan_name,
            term_length=source_term
        ).first()

        if not source_plan:
            flash('✗ Source plan not found', 'error')
            return redirect(url_for('billing_plans.list_plans'))

        # Get all other terms for this plan
        target_plans = BillingPlan.query.filter(
            BillingPlan.plan_name == plan_name,
            BillingPlan.term_length != source_term
        ).all()

        # Copy values to each target plan
        copied_count = 0
        for target in target_plans:
            target.per_user_cost = source_plan.per_user_cost
            target.per_workstation_cost = source_plan.per_workstation_cost
            target.per_server_cost = source_plan.per_server_cost
            target.per_vm_cost = source_plan.per_vm_cost
            target.per_switch_cost = source_plan.per_switch_cost
            target.per_firewall_cost = source_plan.per_firewall_cost
            target.per_hour_ticket_cost = source_plan.per_hour_ticket_cost
            target.backup_base_fee_workstation = source_plan.backup_base_fee_workstation
            target.backup_base_fee_server = source_plan.backup_base_fee_server
            target.backup_included_tb = source_plan.backup_included_tb
            target.backup_per_tb_fee = source_plan.backup_per_tb_fee
            target.support_level = source_plan.support_level
            target.antivirus = source_plan.antivirus
            target.soc = source_plan.soc
            target.password_manager = source_plan.password_manager
            target.sat = source_plan.sat
            target.email_security = source_plan.email_security
            target.network_management = source_plan.network_management
            copied_count += 1

        db.session.commit()
        flash(f'✓ Copied {source_term} values to {copied_count} other terms for {plan_name}', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'✗ Error copying terms: {str(e)}', 'error')

    return redirect(url_for('billing_plans.list_plans'))


@billing_plans_bp.route('/import', methods=['POST'])
@admin_required
def import_plans():
    """Import billing plans and feature options from JSON file using smart detection."""
    import json
    from routes.billing_plans_import import import_billing_data

    if 'json_file' not in request.files:
        flash('✗ No file uploaded', 'error')
        return redirect(url_for('billing_plans.list_plans'))

    file = request.files['json_file']

    if file.filename == '':
        flash('✗ No file selected', 'error')
        return redirect(url_for('billing_plans.list_plans'))

    if not file.filename.endswith('.json'):
        flash('✗ File must be a JSON file', 'error')
        return redirect(url_for('billing_plans.list_plans'))

    try:
        # Read and parse JSON
        data = json.load(file)

        from app import helm_logger
        # Support both new and old formats
        plans_count = len(data.get('plans', data.get('default_plans_data', [])))
        features_count = len(data.get('feature_options', data.get('default_features', [])))
        helm_logger.info(f"Import started - found {plans_count} plans and {features_count} features in JSON")

        # Use smart importer
        stats = import_billing_data(data, skip_existing=True)

        # Check for errors
        if stats['plans_errors'] > 0 or stats['features_errors'] > 0:
            error_summary = '; '.join(stats['errors'][:3])  # Show first 3 errors
            if len(stats['errors']) > 3:
                error_summary += f' ... and {len(stats['errors']) - 3} more errors'
            flash(f'⚠ Import completed with errors: {error_summary}', 'warning')

        # Show success message
        flash(f'✓ Import complete! Plans: {stats["plans_imported"]} imported, {stats["plans_skipped"]} skipped, {stats["plans_errors"]} errors. Features: {stats["features_imported"]} imported, {stats["features_skipped"]} skipped, {stats["features_errors"]} errors.', 'success')

    except json.JSONDecodeError as e:
        from app import helm_logger
        helm_logger.error(f"JSON parsing error: {str(e)}")
        flash(f'✗ Invalid JSON file: {str(e)}. Please check your JSON syntax.', 'error')
    except Exception as e:
        from app import helm_logger
        import traceback
        error_details = traceback.format_exc()
        helm_logger.error(f"Import failed: {str(e)}\n{error_details}")
        flash(f'✗ Import failed: {str(e)}', 'error')

    return redirect(url_for('billing_plans.list_plans'))
