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
    
    contact = Contact.query.get_or_404(contact_id)
    
    return render_template('contacts/details.html',
                         user=g.user,
                         contact=contact)
