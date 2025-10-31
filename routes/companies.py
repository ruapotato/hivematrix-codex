from flask import Blueprint, render_template, g, request, redirect, url_for, jsonify
from app.auth import token_required
from models import Company, BillingPlan, Location, CompanyFeatureOverride, FeatureOption, db
from sqlalchemy import asc, desc

companies_bp = Blueprint('companies', __name__, url_prefix='/companies')

@companies_bp.route('/api/search')
@token_required
def search_companies_api():
    """API endpoint for searching companies without page reload."""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    sort_by = request.args.get('sort_by', 'name')
    order = request.args.get('order', 'asc')
    search_query = request.args.get('search', '').strip()

    query = Company.query

    # Apply search filter
    if search_query:
        search_pattern = f"%{search_query}%"
        query = query.filter(
            db.or_(
                Company.name.ilike(search_pattern),
                Company.account_number.ilike(search_pattern),
                Company.description.ilike(search_pattern)
            )
        )

    # Apply sorting
    if sort_by in ['name', 'account_number', 'plan_selected', 'email_system', 'phone_system', 'contract_end_date']:
        column = getattr(Company, sort_by)
        query = query.order_by(desc(column) if order == 'desc' else asc(column))

    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'success': True,
        'companies': [{
            'account_number': c.account_number,
            'name': c.name,
            'description': c.description,
            'plan_selected': c.plan_selected,
            'email_system': c.email_system,
            'phone_system': c.phone_system,
            'contract_end_date': c.contract_end_date
        } for c in pagination.items],
        'pagination': {
            'page': pagination.page,
            'pages': pagination.pages,
            'total': pagination.total,
            'has_prev': pagination.has_prev,
            'has_next': pagination.has_next,
            'prev_num': pagination.prev_num,
            'next_num': pagination.next_num
        }
    })

@companies_bp.route('/')
@token_required
def list_companies():
    """List all companies with sorting, searching, and pagination."""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    sort_by = request.args.get('sort_by', 'name')
    order = request.args.get('order', 'asc')
    search_query = request.args.get('search', '').strip()

    query = Company.query

    # Apply search filter
    if search_query:
        search_pattern = f"%{search_query}%"
        query = query.filter(
            db.or_(
                Company.name.ilike(search_pattern),
                Company.account_number.ilike(search_pattern),
                Company.description.ilike(search_pattern)
            )
        )

    # Apply sorting
    if sort_by in ['name', 'account_number', 'plan_selected', 'email_system', 'phone_system', 'contract_end_date']:
        column = getattr(Company, sort_by)
        query = query.order_by(desc(column) if order == 'desc' else asc(column))

    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    companies = pagination.items

    return render_template('companies/list.html',
                         user=g.user,
                         companies=companies,
                         pagination=pagination,
                         sort_by=sort_by,
                         order=order,
                         per_page=per_page,
                         search_query=search_query)

@companies_bp.route('/<string:account_number>')
@token_required
def company_details(account_number):
    """View details for a specific company."""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    company = Company.query.get_or_404(account_number)

    # Parse domains JSON if present
    import json
    domain_list = []
    if company.domains:
        try:
            domain_list = json.loads(company.domains)
        except (json.JSONDecodeError, TypeError):
            domain_list = []

    # Get billing plan features and company overrides
    plan_features = None
    client_features = {}

    if company.billing_plan or company.plan_selected:
        plan_name = company.billing_plan or company.plan_selected
        term = company.contract_term_length or company.contract_term or 'Month to Month'

        plan_features = BillingPlan.query.filter_by(
            plan_name=plan_name,
            term_length=term
        ).first()

        # Build client features combining plan defaults and company overrides
        if plan_features:
            # Define feature mapping with display names
            feature_mapping = {
                'antivirus': 'Antivirus',
                'soc': 'SOC (Security Operations Center)',
                'password_manager': 'Password Manager',
                'sat': 'Security Awareness Training',
                'email_security': 'Email Security',
                'network_management': 'Network Management'
            }

            # Get company-specific overrides
            overrides = {
                override.feature_key: override.value
                for override in company.feature_overrides
                if override.override_enabled
            }

            # Build combined features dictionary
            for feature_key, display_name in feature_mapping.items():
                if feature_key in overrides:
                    # Company has custom override
                    client_features[display_name] = {
                        'value': overrides[feature_key],
                        'is_override': True
                    }
                else:
                    # Use plan default
                    plan_value = getattr(plan_features, feature_key, None)
                    client_features[display_name] = {
                        'value': plan_value,
                        'is_override': False
                    }

    # Get email and phone options for dropdowns
    email_options = FeatureOption.query.filter_by(feature_type='email').order_by(FeatureOption.display_name).all()
    phone_options = FeatureOption.query.filter_by(feature_type='phone').order_by(FeatureOption.display_name).all()

    # Get all billing plans for dropdown
    billing_plans = BillingPlan.query.with_entities(
        BillingPlan.plan_name
    ).distinct().order_by(BillingPlan.plan_name).all()
    billing_plan_names = [p.plan_name for p in billing_plans]

    return render_template('companies/details.html',
                         user=g.user,
                         company=company,
                         domain_list=domain_list,
                         client_features=client_features,
                         email_options=email_options,
                         phone_options=phone_options,
                         billing_plan_names=billing_plan_names)

# Location API endpoints

@companies_bp.route('/<string:account_number>/locations', methods=['GET'])
@token_required
def get_locations(account_number):
    """Get all additional locations for a company (excluding main address from Freshservice)."""
    company = Company.query.get_or_404(account_number)

    locations = Location.query.filter_by(company_account_number=account_number).all()

    return jsonify({
        'success': True,
        'locations': [{
            'id': loc.id,
            'name': loc.name,
            'address': loc.address,
            'phone_number': loc.phone_number
        } for loc in locations]
    })

@companies_bp.route('/<string:account_number>/locations', methods=['POST'])
@token_required
def add_location(account_number):
    """Add a new location to a company."""
    if g.user.get('permission_level') not in ['admin', 'technician']:
        return jsonify({'error': 'Insufficient permissions'}), 403

    company = Company.query.get_or_404(account_number)

    data = request.get_json()
    if not data or not data.get('name') or not data.get('address'):
        return jsonify({'error': 'Name and address are required'}), 400

    location = Location(
        name=data['name'],
        address=data['address'],
        phone_number=data.get('phone_number'),
        company_account_number=account_number
    )

    db.session.add(location)
    db.session.commit()

    return jsonify({
        'success': True,
        'location': {
            'id': location.id,
            'name': location.name,
            'address': location.address,
            'phone_number': location.phone_number
        }
    })

@companies_bp.route('/<string:account_number>/locations/<int:location_id>', methods=['DELETE'])
@token_required
def delete_location(account_number, location_id):
    """Delete a location."""
    if g.user.get('permission_level') not in ['admin', 'technician']:
        return jsonify({'error': 'Insufficient permissions'}), 403

    location = Location.query.filter_by(
        id=location_id,
        company_account_number=account_number
    ).first_or_404()

    db.session.delete(location)
    db.session.commit()

    return jsonify({'success': True})

@companies_bp.route('/<string:account_number>/update', methods=['PUT'])
@token_required
def update_company(account_number):
    """Update company details."""
    if g.user.get('permission_level') not in ['admin', 'technician']:
        return jsonify({'error': 'Insufficient permissions'}), 403

    company = Company.query.get_or_404(account_number)
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Update all editable fields
    editable_fields = [
        'name', 'description', 'billing_plan', 'support_level',
        'email_system', 'phone_system', 'contract_term_length',
        'managed_users', 'managed_devices', 'managed_network',
        'company_main_number', 'address', 'datto_portal_url', 'domains',
        'head_user_id', 'prime_user_id', 'company_start_date',
        'contract_start_date', 'contract_end_date'
    ]

    for field in editable_fields:
        if field in data:
            value = data[field]
            # Convert empty strings to None for optional fields
            if value == '':
                value = None
            # Convert numeric IDs to proper type
            if field in ['head_user_id', 'prime_user_id'] and value:
                value = int(value)
            setattr(company, field, value)

    # Update head_name and prime_user_name if IDs changed
    if 'head_user_id' in data and data['head_user_id']:
        from models import Contact
        contact = Contact.query.filter_by(freshservice_id=int(data['head_user_id'])).first()
        if contact:
            company.head_name = contact.name

    if 'prime_user_id' in data and data['prime_user_id']:
        from models import Contact
        contact = Contact.query.filter_by(freshservice_id=int(data['prime_user_id'])).first()
        if contact:
            company.prime_user_name = contact.name

    try:
        db.session.commit()
        return jsonify({'success': True, 'message': 'Company updated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
