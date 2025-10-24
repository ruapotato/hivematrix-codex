from flask import Blueprint, render_template, g, request, redirect, url_for, flash, jsonify
from app.auth import token_required, admin_required
from models import db, BillingPlan, FeatureOption
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
        grouped_plans[plan.plan_name].append(plan)

    # Get feature options grouped by category
    all_features = FeatureOption.query.order_by(FeatureOption.feature_category, FeatureOption.option_value).all()

    feature_options = defaultdict(list)
    feature_types = set()
    for feature in all_features:
        feature_options[feature.feature_category].append(feature)
        feature_types.add(feature.feature_category)

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

    try:
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
            plan.backup_cost_per_gb_workstation = float(request.form.get(f'backup_cost_per_gb_workstation_{plan_id}', 0))
            plan.backup_cost_per_gb_server = float(request.form.get(f'backup_cost_per_gb_server_{plan_id}', 0))

            # Update support level
            plan.support_level = request.form.get(f'support_level_{plan_id}', 'Billed Hourly')

            # Update features
            plan.antivirus = request.form.get(f'feature_antivirus_{plan_id}', 'Not Included')
            plan.soc = request.form.get(f'feature_soc_{plan_id}', 'Not Included')
            plan.password_manager = request.form.get(f'feature_password_manager_{plan_id}', 'Not Included')
            plan.sat = request.form.get(f'feature_sat_{plan_id}', 'Not Included')
            plan.email_security = request.form.get(f'feature_email_security_{plan_id}', 'Not Included')
            plan.network_management = request.form.get(f'feature_network_management_{plan_id}', 'Not Included')

        db.session.commit()
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
                backup_cost_per_gb_workstation=1.0,
                backup_cost_per_gb_server=15.0,
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
            feature_category=feature_category,
            option_value=option_value
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
            feature.option_value = new_name
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
