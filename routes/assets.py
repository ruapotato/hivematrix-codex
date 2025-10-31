from flask import Blueprint, render_template, g, request, redirect, url_for, flash, jsonify
from app.auth import token_required
from models import Asset, Company, Contact, db
from sqlalchemy import asc, desc

assets_bp = Blueprint('assets', __name__, url_prefix='/assets')

@assets_bp.route('/api/search')
@token_required
def search_assets_api():
    """API endpoint for searching assets without page reload."""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    sort_by = request.args.get('sort_by', 'hostname')
    order = request.args.get('order', 'asc')
    search_query = request.args.get('search', '').strip()

    query = Asset.query.join(Company, Asset.company_account_number == Company.account_number, isouter=True)

    # Apply search filter
    if search_query:
        search_pattern = f"%{search_query}%"
        query = query.filter(
            db.or_(
                Asset.hostname.ilike(search_pattern),
                Asset.description.ilike(search_pattern),
                Asset.datto_site_name.ilike(search_pattern),
                Company.name.ilike(search_pattern)
            )
        )

    # Apply sorting
    if sort_by in ['hostname', 'hardware_type', 'operating_system', 'online']:
        column = getattr(Asset, sort_by)
        query = query.order_by(desc(column) if order == 'desc' else asc(column))

    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'success': True,
        'assets': [{
            'id': a.id,
            'hostname': a.hostname,
            'description': a.description,
            'hardware_type': a.hardware_type,
            'operating_system': a.operating_system,
            'antivirus_product': a.antivirus_product,
            'online': a.online,
            'last_logged_in_user': a.last_logged_in_user,
            'web_remote_url': a.web_remote_url,
            'int_ip_address': a.int_ip_address,
            'ext_ip_address': a.ext_ip_address,
            'domain': a.domain,
            'last_seen': a.last_seen,
            'patch_status': a.patch_status,
            'company_name': a.company.name if a.company else None,
            'company_account_number': a.company.account_number if a.company else None
        } for a in pagination.items],
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

@assets_bp.route('/')
@token_required
def list_assets():
    """List all assets with sorting, searching, and pagination."""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    sort_by = request.args.get('sort_by', 'hostname')
    order = request.args.get('order', 'asc')
    search_query = request.args.get('search', '').strip()

    query = Asset.query.join(Company, Asset.company_account_number == Company.account_number, isouter=True)

    # Apply search filter
    if search_query:
        search_pattern = f"%{search_query}%"
        query = query.filter(
            db.or_(
                Asset.hostname.ilike(search_pattern),
                Asset.description.ilike(search_pattern),
                Asset.datto_site_name.ilike(search_pattern),
                Company.name.ilike(search_pattern)
            )
        )

    # Apply sorting
    if sort_by in ['hostname', 'hardware_type', 'operating_system', 'online']:
        column = getattr(Asset, sort_by)
        query = query.order_by(desc(column) if order == 'desc' else asc(column))

    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    assets = pagination.items

    return render_template('assets/list.html',
                         user=g.user,
                         assets=assets,
                         pagination=pagination,
                         sort_by=sort_by,
                         order=order,
                         per_page=per_page,
                         search_query=search_query)

@assets_bp.route('/<int:asset_id>')
@token_required
def asset_details(asset_id):
    """View details for a specific asset."""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    asset = Asset.query.get_or_404(asset_id)

    # Get available contacts from the same company
    available_contacts = []
    if asset.company:
        available_contacts = Contact.query.filter(
            Contact.companies.any(account_number=asset.company_account_number)
        ).order_by(Contact.name).all()

    # UDF field name mappings (customize these based on your Datto setup)
    udf_names = {
        'udf1': 'Entra ID Tenant',
        'udf2': 'BitLocker Key',
        'udf3': 'Disk Information',
        'udf4': 'Enabled Administrators',
        'udf5': 'Windows 11',
        'udf6': 'Backup Usage (TB)',
        'udf7': 'Device Type',
        'udf9': 'Windows Key',
    }

    return render_template('assets/details.html',
                         user=g.user,
                         asset=asset,
                         available_contacts=available_contacts,
                         udf_names=udf_names)

@assets_bp.route('/<int:asset_id>/assign-user', methods=['POST'])
@token_required
def assign_user(asset_id):
    """Assign a contact (user) to an asset (device)."""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    asset = Asset.query.get_or_404(asset_id)
    contact_id = request.form.get('contact_id', type=int)

    if not contact_id:
        flash('Please select a user to assign.', 'error')
        return redirect(url_for('assets.asset_details', asset_id=asset_id))

    contact = Contact.query.get_or_404(contact_id)

    # Check if already assigned
    if contact in asset.contacts:
        flash(f'{contact.name} is already assigned to this device.', 'warning')
    else:
        asset.contacts.append(contact)
        db.session.commit()
        flash(f'Successfully assigned {contact.name} to {asset.hostname}.', 'success')

    return redirect(url_for('assets.asset_details', asset_id=asset_id))

@assets_bp.route('/<int:asset_id>/unassign-user/<int:contact_id>', methods=['POST'])
@token_required
def unassign_user(asset_id, contact_id):
    """Unassign a contact (user) from an asset (device)."""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    asset = Asset.query.get_or_404(asset_id)
    contact = Contact.query.get_or_404(contact_id)

    if contact in asset.contacts:
        asset.contacts.remove(contact)
        db.session.commit()
        flash(f'Successfully unassigned {contact.name} from {asset.hostname}.', 'success')
    else:
        flash(f'{contact.name} is not assigned to this device.', 'warning')

    return redirect(url_for('assets.asset_details', asset_id=asset_id))

@assets_bp.route('/<int:asset_id>/update-contacts', methods=['PUT'])
@token_required
def update_contacts(asset_id):
    """Update asset contact associations."""
    # Check permission
    if g.user.get('permission_level') not in ['admin', 'technician']:
        return jsonify({'error': 'Insufficient permissions'}), 403

    asset = Asset.query.get_or_404(asset_id)
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    try:
        # Update contact associations
        if 'contact_ids' in data:
            # Clear existing contacts
            asset.contacts = []
            # Add selected contacts
            contact_ids = data['contact_ids']
            if contact_ids:
                contacts = Contact.query.filter(Contact.id.in_(contact_ids)).all()
                asset.contacts = contacts

        db.session.commit()

        return jsonify({'success': True, 'message': 'Contacts updated successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
