from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from models import db, Company
from sqlalchemy import asc, desc
import configparser

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

    valid_sort_columns = ['name', 'account_number', 'plan_selected', 'company_main_number', 'head_name', 'primary_contact_name']
    if sort_by not in valid_sort_columns:
        sort_by = 'name'

    query = Company.query
    column_to_sort = getattr(Company, sort_by)

    if order == 'desc':
        query = query.order_by(desc(column_to_sort))
    else:
        query = query.order_by(asc(column_to_sort))

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    companies = pagination.items

    return render_template('companies.html', companies=companies, pagination=pagination, sort_by=sort_by, order=order, per_page=per_page)

@companies_bp.route('/<string:account_number>')
def company_details(account_number):
    company = Company.query.get_or_404(account_number)

    config = current_app.config.get('NEXUS_CONFIG', configparser.ConfigParser())
    plan_names, features = load_plans_from_config(config)

    plan_features = {}
    if company.plan_selected in plan_names:
        section_name = f"plan_{company.plan_selected.replace(' ', '_')}"
        for feature_name in features.keys():
            feature_key = get_feature_key(feature_name)
            plan_features[feature_name] = config.get(section_name, feature_key, fallback="Not Included")

    return render_template('company_details.html', company=company, plan_features=plan_features)

@companies_bp.route('/edit/<string:account_number>', methods=['POST'])
def edit_company(account_number):
    company = Company.query.get_or_404(account_number)
    if company:
        company.name = request.form.get('name')
        company.description = request.form.get('description')
        company.plan_selected = request.form.get('plan_selected')
        company.profit_or_non_profit = request.form.get('profit_or_non_profit')
        company.company_main_number = request.form.get('company_main_number')
        company.address = request.form.get('address')
        company.company_start_date = request.form.get('company_start_date')
        company.head_name = request.form.get('head_name')
        company.primary_contact_name = request.form.get('primary_contact_name')
        company.domains = request.form.get('domains')
        db.session.commit()
        flash('Company details updated successfully.', 'success')
    else:
        flash('Company not found.', 'danger')
    return redirect(url_for('companies.company_details', account_number=account_number))
