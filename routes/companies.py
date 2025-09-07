from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from models import db, Company, CompanyFeatureOverride, Location
from sqlalchemy import asc, desc, or_
import configparser
import json
import random
from datetime import datetime

companies_bp = Blueprint('companies', __name__, url_prefix='/companies')

def get_feature_key(feature_name):
    """Converts a feature name like 'Email Security' to 'email_security' for config keys."""
    return feature_name.lower().replace(' ', '_')

def load_plans_from_config(config):
    """Reads plan names and features from the config parser object."""
    plan_names_str = config.get('plans', 'plan_names', fallback='Default Plan')
    plan_names = [p.strip() for p in plan_names_str.split(',')]

    features = {}
    if config.has_section('features'):
        for key, value in config.items('features'):
            feature_name = key.replace('_', ' ').title()
            if 'Sat' in feature_name:
                feature_name = feature_name.replace('Sat', 'SAT')
            if 'Soc' in feature_name:
                feature_name = feature_name.replace('Soc', 'SOC')
            options = [opt.strip() for opt in value.split(',')]
            features[feature_name] = options
    else:
        # Fallback if [features] section is somehow missing
        features = {"Default Feature": ["Option 1", "Not Included"]}

    return plan_names, features

@companies_bp.route('/')
def list_companies():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    sort_by = request.args.get('sort_by', 'name')
    order = request.args.get('order', 'asc')
    search_query = request.args.get('search', '')

    query = Company.query

    if search_query:
        search_term = f'%{search_query}%'
        query = query.filter(or_(
            Company.name.ilike(search_term),
            Company.account_number.ilike(search_term),
            Company.plan_selected.ilike(search_term),
            Company.company_main_number.ilike(search_term),
            Company.head_name.ilike(search_term),
            Company.primary_contact_name.ilike(search_term)
        ))

    valid_sort_columns = ['name', 'account_number', 'plan_selected', 'company_main_number', 'head_name', 'primary_contact_name']
    if sort_by not in valid_sort_columns:
        sort_by = 'name'

    column_to_sort = getattr(Company, sort_by)

    if order == 'desc':
        query = query.order_by(desc(column_to_sort))
    else:
        query = query.order_by(asc(column_to_sort))

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    companies = pagination.items

    return render_template('companies.html', companies=companies, pagination=pagination, sort_by=sort_by, order=order, per_page=per_page, search_query=search_query)

@companies_bp.route('/add', methods=['POST'])
def add_company():
    """Adds a new company with a unique, randomly generated account number."""
    name = request.form.get('name')
    if not name:
        flash('Company name is required.', 'danger')
        return redirect(url_for('companies.list_companies'))

    # Generate a unique 6-digit account number
    while True:
        new_account_number = str(random.randint(100000, 999999))
        if not Company.query.get(new_account_number):
            break

    new_company = Company(
        account_number=new_account_number,
        name=name,
        company_main_number=request.form.get('company_main_number'),
        primary_contact_name=request.form.get('primary_contact_name')
    )
    db.session.add(new_company)
    db.session.commit()
    flash(f"Company '{name}' created successfully with account number {new_account_number}.", 'success')
    return redirect(url_for('companies.list_companies'))


@companies_bp.route('/<string:account_number>')
def company_details(account_number):
    company = Company.query.get_or_404(account_number)

    config = current_app.config.get('NEXUS_CONFIG', configparser.ConfigParser())
    plan_names, features = load_plans_from_config(config)

    # Load all plan features into a dictionary for the template
    all_plan_features = {}
    for p_name in plan_names:
        section_name = f"plan_{p_name.replace(' ', '_')}"
        all_plan_features[p_name] = {}
        for feature_name in features.keys():
            feature_key = get_feature_key(feature_name)
            all_plan_features[p_name][feature_name] = config.get(section_name, feature_key, fallback="Not Included")

    # Determine the features for the currently selected plan
    current_plan_features = all_plan_features.get(company.plan_selected, {})
    overrides = {override.feature_key: {'value': override.value, 'enabled': override.override_enabled} for override in company.feature_overrides}

    final_features = {}
    for feature_name, options in features.items():
        feature_key = get_feature_key(feature_name)
        if feature_key in overrides and overrides[feature_key]['enabled']:
            final_features[feature_name] = overrides[feature_key]['value']
        else:
            final_features[feature_name] = current_plan_features.get(feature_name, "Not Included")

    domains_for_input = ''
    if company.domains:
        try:
            domains_list = json.loads(company.domains)
            domains_for_input = ', '.join(domains_list)
        except (json.JSONDecodeError, TypeError):
            domains_for_input = company.domains

    return render_template(
        'company_details.html',
        company=company,
        plan_features=final_features,
        all_plan_features_json=json.dumps(all_plan_features),
        plans=plan_names,
        contacts=company.contacts,
        features=features,
        overrides=overrides,
        domains_for_input=domains_for_input
    )

@companies_bp.route('/edit/<string:account_number>', methods=['POST'])
def edit_company(account_number):
    company = Company.query.get_or_404(account_number)
    if company:
        company.name = request.form.get('name')
        company.description = request.form.get('description')
        company.plan_selected = request.form.get('plan_selected')
        company.profit_or_non_profit = request.form.get('profit_or_non_profit')
        company.company_main_number = request.form.get('company_main_number')

        # Handle date formatting
        start_date_str = request.form.get('company_start_date', '')
        if start_date_str:
            try:
                # The date picker sends the date in yyyy-mm-dd format
                company.company_start_date = datetime.strptime(start_date_str, '%Y-%m-%d').isoformat()
            except ValueError:
                flash('Invalid date format. Please use YYYY-MM-DD.', 'danger')
                return redirect(url_for('companies.company_details', account_number=account_number))
        else:
            company.company_start_date = None

        company.head_name = request.form.get('head_name')
        company.primary_contact_name = request.form.get('primary_contact_name')
        company.email_system = request.form.get('email_system')
        company.phone_system = request.form.get('phone_system')

        raw_domains = request.form.get('domains', '')
        domains_list = [domain.strip() for domain in raw_domains.split(',') if domain.strip()]
        company.domains = json.dumps(domains_list)

        config = current_app.config.get('NEXUS_CONFIG', configparser.ConfigParser())
        _, features = load_plans_from_config(config)

        plan_section_name = f"plan_{company.plan_selected.replace(' ', '_')}"

        for feature_name in features.keys():
            feature_key = get_feature_key(feature_name)
            override_value = request.form.get(f'override-{feature_key}')
            override_enabled = f'override-{feature_key}-enabled' in request.form

            existing_override = company.feature_overrides.filter_by(feature_key=feature_key).first()

            plan_default_value = config.get(plan_section_name, feature_key, fallback="Not Included")

            if existing_override:
                existing_override.value = override_value if override_enabled else plan_default_value
                existing_override.override_enabled = override_enabled
            else:
                new_override = CompanyFeatureOverride(
                    company_account_number=account_number,
                    feature_key=feature_key,
                    value=override_value if override_enabled else plan_default_value,
                    override_enabled=override_enabled
                )
                db.session.add(new_override)

        db.session.commit()
        flash('Company details updated successfully.', 'success')
    else:
        flash('Company not found.', 'danger')
    return redirect(url_for('companies.company_details', account_number=account_number))

@companies_bp.route('/<string:account_number>/locations/add', methods=['POST'])
def add_location(account_number):
    company = Company.query.get_or_404(account_number)
    name = request.form.get('name')
    address = request.form.get('address')
    phone_number = request.form.get('phone_number')

    if name:
        new_location = Location(
            name=name,
            address=address,
            phone_number=phone_number,
            company_account_number=company.account_number
        )
        db.session.add(new_location)
        db.session.commit()
        flash('New location added successfully.', 'success')
    else:
        flash('Location name is required.', 'danger')
    return redirect(url_for('companies.company_details', account_number=account_number))

@companies_bp.route('/<string:account_number>/locations/edit/<int:location_id>', methods=['POST'])
def edit_location(account_number, location_id):
    location = Location.query.get_or_404(location_id)
    if location.company_account_number != account_number:
        flash('Invalid location.', 'danger')
        return redirect(url_for('companies.company_details', account_number=account_number))

    location.name = request.form.get('name')
    location.address = request.form.get('address')
    location.phone_number = request.form.get('phone_number')
    db.session.commit()
    flash('Location updated successfully.', 'success')
    return redirect(url_for('companies.company_details', account_number=account_number))

@companies_bp.route('/<string:account_number>/locations/delete/<int:location_id>', methods=['POST'])
def delete_location(account_number, location_id):
    location = Location.query.get_or_404(location_id)
    if location.company_account_number != account_number:
        flash('Invalid location.', 'danger')
        return redirect(url_for('companies.company_details', account_number=account_number))

    db.session.delete(location)
    db.session.commit()
    flash('Location deleted successfully.', 'success')
    return redirect(url_for('companies.company_details', account_number=account_number))

@companies_bp.route('/api/plans/<string:plan_name>', methods=['GET'])
def get_plan_features(plan_name):
    config = current_app.config.get('NEXUS_CONFIG', configparser.ConfigParser())
    plan_names, features = load_plans_from_config(config)

    if plan_name not in plan_names:
        return jsonify({"error": "Plan not found"}), 404

    plan_features = {}
    section_name = f"plan_{plan_name.replace(' ', '_')}"
    for feature_name in features.keys():
        feature_key = get_feature_key(feature_name)
        plan_features[feature_name] = config.get(section_name, feature_key, fallback="Not Included")

    return jsonify(plan_features)
