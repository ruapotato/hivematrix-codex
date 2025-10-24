from flask import Blueprint, render_template, g, request
from app.auth import token_required
from models import Contact, db
from sqlalchemy import asc, desc

contacts_bp = Blueprint('contacts', __name__, url_prefix='/contacts')

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

    query = Contact.query

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
                         search_query=search_query)

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
