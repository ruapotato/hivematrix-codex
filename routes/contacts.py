from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Contact, Asset, Company
from decorators import admin_required
from sqlalchemy import asc, desc, func

contacts_bp = Blueprint('contacts', __name__, url_prefix='/contacts')

@contacts_bp.route('/')
def list_contacts():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    sort_by = request.args.get('sort_by', 'name')
    order = request.args.get('order', 'asc')

    query = Contact.query

    if sort_by == 'company':
        query = query.join(Contact.company)
        if order == 'desc':
            query = query.order_by(desc(Company.name))
        else:
            query = query.order_by(asc(Company.name))
    elif sort_by == 'associated_assets':
        query = query.outerjoin(Contact.assets).group_by(Contact.id)
        if order == 'desc':
            query = query.order_by(desc(func.count(Asset.id)))
        else:
            query = query.order_by(asc(func.count(Asset.id)))
    else:
        valid_sort_columns = ['name', 'email', 'active', 'mobile_phone_number', 'work_phone_number']
        if sort_by not in valid_sort_columns:
            sort_by = 'name'
        column_to_sort = getattr(Contact, sort_by)
        if order == 'desc':
            query = query.order_by(desc(column_to_sort))
        else:
            query = query.order_by(asc(column_to_sort))

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    contacts = pagination.items

    return render_template('contacts.html', contacts=contacts, pagination=pagination, sort_by=sort_by, order=order, per_page=per_page)


@contacts_bp.route('/<int:contact_id>', methods=['GET', 'POST'])
def contact_details(contact_id):
    contact = Contact.query.get_or_404(contact_id)
    if request.method == 'POST':
        # Link assets
        asset_ids = request.form.getlist('asset_ids')
        contact.assets = []
        for asset_id in asset_ids:
            asset = Asset.query.get(asset_id)
            if asset:
                contact.assets.append(asset)
        db.session.commit()
        flash('Contact assets updated successfully.', 'success')
        return redirect(url_for('contacts.contact_details', contact_id=contact_id))

    # Correctly query assets based on the company's account number
    company_assets = Asset.query.filter_by(company_account_number=contact.company_account_number).all()
    return render_template('contact_details.html', contact=contact, company_assets=company_assets)

@contacts_bp.route('/edit/<int:contact_id>', methods=['POST'])
def edit_contact(contact_id):
    contact = Contact.query.get_or_404(contact_id)
    if contact:
        contact.name = request.form.get('name')
        contact.email = request.form.get('email')
        contact.title = request.form.get('title')
        contact.employment_type = request.form.get('employment_type')
        contact.active = 'active' in request.form
        contact.mobile_phone_number = request.form.get('mobile_phone_number')
        contact.work_phone_number = request.form.get('work_phone_number')
        contact.secondary_emails = request.form.get('secondary_emails')
        db.session.commit()
        flash('Contact details updated successfully.', 'success')
    else:
        flash('Contact not found.', 'danger')
    return redirect(url_for('contacts.contact_details', contact_id=contact_id))
