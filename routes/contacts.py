from flask import Blueprint, render_template, g, request
from app.auth import token_required
from models import Contact
from sqlalchemy import asc, desc

contacts_bp = Blueprint('contacts', __name__, url_prefix='/contacts')

@contacts_bp.route('/')
@token_required
def list_contacts():
    """List all contacts with sorting and pagination."""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    sort_by = request.args.get('sort_by', 'name')
    order = request.args.get('order', 'asc')
    
    query = Contact.query
    
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
                         per_page=per_page)

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
