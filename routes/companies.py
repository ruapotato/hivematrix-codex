from flask import Blueprint, render_template, g, request, redirect, url_for
from app.auth import token_required
from models import Company, db
from sqlalchemy import asc, desc

companies_bp = Blueprint('companies', __name__, url_prefix='/companies')

@companies_bp.route('/')
@token_required
def list_companies():
    """List all companies with sorting and pagination."""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    sort_by = request.args.get('sort_by', 'name')
    order = request.args.get('order', 'asc')
    
    query = Company.query
    
    # Apply sorting
    if sort_by in ['name', 'account_number', 'plan_selected']:
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
                         per_page=per_page)

@companies_bp.route('/<string:account_number>')
@token_required
def company_details(account_number):
    """View details for a specific company."""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    company = Company.query.get_or_404(account_number)

    return render_template('companies/details.html',
                         user=g.user,
                         company=company)
