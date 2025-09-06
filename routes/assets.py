from flask import Blueprint, render_template, request
from models import Asset, Company
from sqlalchemy import asc, desc

assets_bp = Blueprint('assets', __name__, url_prefix='/assets')

@assets_bp.route('/')
def list_assets():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    sort_by = request.args.get('sort_by', 'hostname')
    order = request.args.get('order', 'asc')

    query = Asset.query

    if sort_by == 'company':
        query = query.join(Asset.company)
        if order == 'desc':
            query = query.order_by(desc(Company.name))
        else:
            query = query.order_by(asc(Company.name))
    else:
        valid_sort_columns = ['hostname', 'device_type', 'operating_system']
        if sort_by not in valid_sort_columns:
            sort_by = 'hostname'

        column_to_sort = getattr(Asset, sort_by)

        if order == 'desc':
            query = query.order_by(desc(column_to_sort))
        else:
            query = query.order_by(asc(column_to_sort))

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    assets = pagination.items

    return render_template('assets.html', assets=assets, pagination=pagination, sort_by=sort_by, order=order, per_page=per_page)

