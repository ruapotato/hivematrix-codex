from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Company
from sqlalchemy import asc, desc

companies_bp = Blueprint('companies', __name__, url_prefix='/companies')

@companies_bp.route('/')
def list_companies():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    sort_by = request.args.get('sort_by', 'name')
    order = request.args.get('order', 'asc')

    valid_sort_columns = ['name', 'account_number']
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
    return render_template('company_details.html', company=company)

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
