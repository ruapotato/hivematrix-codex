from flask import Blueprint, render_template, g, request
from app.auth import token_required
from models import Asset
from sqlalchemy import asc, desc

assets_bp = Blueprint('assets', __name__, url_prefix='/assets')

@assets_bp.route('/')
@token_required
def list_assets():
    """List all assets with sorting and pagination."""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    sort_by = request.args.get('sort_by', 'hostname')
    order = request.args.get('order', 'asc')
    
    query = Asset.query
    
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
                         per_page=per_page)

@assets_bp.route('/<int:asset_id>')
@token_required
def asset_details(asset_id):
    """View details for a specific asset."""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403
    
    asset = Asset.query.get_or_404(asset_id)
    
    return render_template('assets/details.html',
                         user=g.user,
                         asset=asset)
