from flask import Blueprint, render_template, g, request, jsonify
from app.auth import token_required
from models import Contact, db
from sqlalchemy import asc, desc

contacts_bp = Blueprint('contacts', __name__, url_prefix='/contacts')

@contacts_bp.route('/api/search')
@token_required
def search_contacts_api():
    """API endpoint for searching contacts without page reload."""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    sort_by = request.args.get('sort_by', 'name')
    order = request.args.get('order', 'asc')
    search_query = request.args.get('search', '').strip()
    show_inactive = request.args.get('show_inactive', '0') == '1'

    query = Contact.query

    # Hide inactive contacts by default
    if not show_inactive:
        query = query.filter(Contact.active == True)

    # Apply search filter
    if search_query:
        search_pattern = f"%{search_query}%"
        query = query.filter(
            db.or_(
                Contact.name.ilike(search_pattern),
                Contact.email.ilike(search_pattern),
                Contact.mobile_phone_number.ilike(search_pattern),
                Contact.work_phone_number.ilike(search_pattern)
            )
        )

    # Apply sorting
    if sort_by in ['name', 'email', 'active']:
        column = getattr(Contact, sort_by)
        query = query.order_by(desc(column) if order == 'desc' else asc(column))

    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'success': True,
        'contacts': [{
            'id': c.id,
            'name': c.name,
            'email': c.email,
            'mobile_phone_number': c.mobile_phone_number,
            'work_phone_number': c.work_phone_number,
            'active': c.active,
            'company_count': len(c.companies)
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

@contacts_bp.route('/')
@token_required
def list_contacts():
    """List all contacts with sorting, searching, and pagination."""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    sort_by = request.args.get('sort_by', 'name')
    order = request.args.get('order', 'asc')
    search_query = request.args.get('search', '').strip()
    show_inactive = request.args.get('show_inactive', '0') == '1'

    query = Contact.query

    # Hide inactive contacts by default
    if not show_inactive:
        query = query.filter(Contact.active == True)

    # Apply search filter
    if search_query:
        search_pattern = f"%{search_query}%"
        query = query.filter(
            db.or_(
                Contact.name.ilike(search_pattern),
                Contact.email.ilike(search_pattern),
                Contact.mobile_phone_number.ilike(search_pattern),
                Contact.work_phone_number.ilike(search_pattern)
            )
        )

    # Apply sorting
    if sort_by in ['name', 'email', 'active']:
        column = getattr(Contact, sort_by)
        query = query.order_by(desc(column) if order == 'desc' else asc(column))

    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    contacts = pagination.items

    return render_template('contacts/list.html',
                         user=g.user,
                         contacts=contacts,
                         pagination=pagination,
                         sort_by=sort_by,
                         order=order,
                         per_page=per_page,
                         search_query=search_query,
                         show_inactive=show_inactive)

@contacts_bp.route('/<int:contact_id>')
@token_required
def contact_details(contact_id):
    """View details for a specific contact."""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    from models import Company, Asset
    import json

    contact = Contact.query.get_or_404(contact_id)

    # Parse secondary emails from JSON array to comma-separated string
    secondary_emails_display = ''
    if contact.secondary_emails:
        try:
            emails_array = json.loads(contact.secondary_emails)
            if isinstance(emails_array, list):
                secondary_emails_display = ', '.join(emails_array)
            else:
                secondary_emails_display = contact.secondary_emails
        except:
            secondary_emails_display = contact.secondary_emails

    # Get all companies for dropdown
    all_companies = Company.query.order_by(Company.name).all()

    # Get all assets from the contact's companies for dropdown
    company_account_numbers = [c.account_number for c in contact.companies]
    available_assets = Asset.query.filter(
        Asset.company_account_number.in_(company_account_numbers)
    ).order_by(Asset.hostname).all() if company_account_numbers else []

    return render_template('contacts/details.html',
                         user=g.user,
                         contact=contact,
                         secondary_emails_display=secondary_emails_display,
                         all_companies=all_companies,
                         available_assets=available_assets)

@contacts_bp.route('/<int:contact_id>/update', methods=['PUT'])
@token_required
def update_contact(contact_id):
    """Update contact details."""
    # Check permission
    if g.user.get('permission_level') not in ['admin', 'technician']:
        return jsonify({'error': 'Insufficient permissions'}), 403

    from models import Company, Asset
    contact = Contact.query.get_or_404(contact_id)
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    try:
        # Update basic fields
        if 'first_name' in data:
            contact.first_name = data['first_name']
        if 'last_name' in data:
            contact.last_name = data['last_name']
            # Update computed name field
            if contact.first_name and contact.last_name:
                contact.name = f"{contact.first_name} {contact.last_name}"
            elif contact.first_name:
                contact.name = contact.first_name
            elif contact.last_name:
                contact.name = contact.last_name

        if 'email' in data:
            contact.email = data['email']
            contact.primary_email = data['email']

        if 'job_title' in data:
            contact.job_title = data['job_title']
            contact.title = data['job_title']

        if 'mobile_phone_number' in data:
            contact.mobile_phone_number = data['mobile_phone_number']

        if 'work_phone_number' in data:
            contact.work_phone_number = data['work_phone_number']

        if 'secondary_emails' in data:
            import json
            # Convert comma-separated string to JSON array for storage
            emails_str = data['secondary_emails'].strip()
            if emails_str:
                # Split by comma and clean up whitespace
                emails_list = [email.strip() for email in emails_str.split(',') if email.strip()]
                contact.secondary_emails = json.dumps(emails_list)
            else:
                contact.secondary_emails = None

        if 'location_name' in data:
            contact.location_name = data['location_name']

        if 'time_zone' in data:
            contact.time_zone = data['time_zone']

        if 'address' in data:
            contact.address = data['address']

        if 'background_information' in data:
            contact.background_information = data['background_information']

        # Update boolean fields
        if 'active' in data:
            contact.active = data['active']

        if 'vip_user' in data:
            contact.vip_user = data['vip_user']

        if 'is_agent' in data:
            contact.is_agent = data['is_agent']

        # Update company associations
        if 'company_account_numbers' in data:
            # Clear existing companies
            contact.companies = []
            # Add selected companies
            company_account_numbers = data['company_account_numbers']
            if company_account_numbers:
                companies = Company.query.filter(
                    Company.account_number.in_(company_account_numbers)
                ).all()
                contact.companies = companies

        # Update asset associations
        if 'asset_ids' in data:
            # Clear existing assets
            contact.assets = []
            # Add selected assets
            asset_ids = data['asset_ids']
            if asset_ids:
                assets = Asset.query.filter(Asset.id.in_(asset_ids)).all()
                contact.assets = assets

        db.session.commit()

        return jsonify({'success': True, 'message': 'Contact updated successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
