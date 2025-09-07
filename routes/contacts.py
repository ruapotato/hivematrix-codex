from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Contact, Asset, Company
from decorators import admin_required
from sqlalchemy import asc, desc, func, or_
from sqlalchemy.orm import joinedload
import json

contacts_bp = Blueprint('contacts', __name__, url_prefix='/contacts')

@contacts_bp.route('/')
def list_contacts():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    sort_by = request.args.get('sort_by', 'name')
    order = request.args.get('order', 'asc')
    search_query = request.args.get('search', '')
    show_inactive = request.args.get('show_inactive', 'false').lower() == 'true'

    query = Contact.query

    if not show_inactive:
        query = query.filter(Contact.active == True)

    if search_query:
        search_term = f'%{search_query}%'
        # Join for searching by company name
        query = query.outerjoin(Contact.companies).filter(or_(
            Contact.name.ilike(search_term),
            Contact.email.ilike(search_term),
            Contact.title.ilike(search_term),
            Contact.mobile_phone_number.ilike(search_term),
            Contact.work_phone_number.ilike(search_term),
            Company.name.ilike(search_term)
        ))

    if sort_by == 'company':
        # Join for sorting
        query = query.join(Contact.companies)
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

    # Apply distinct to prevent duplicates from joins
    query = query.distinct()

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    contacts = pagination.items
    all_companies = Company.query.order_by(Company.name).all()

    return render_template('contacts.html', contacts=contacts, pagination=pagination, sort_by=sort_by, order=order, per_page=per_page, companies=all_companies, search_query=search_query, show_inactive=show_inactive)

@contacts_bp.route('/add', methods=['POST'])
def add_contact():
    """Adds a new contact."""
    name = request.form.get('name')
    email = request.form.get('email')
    company_account_numbers = request.form.getlist('company_account_numbers')

    if not all([name, email, company_account_numbers]):
        flash('Name, email, and at least one company are required fields.', 'danger')
        return redirect(url_for('contacts.list_contacts'))

    if Contact.query.filter_by(email=email).first():
        flash(f"A contact with the email '{email}' already exists.", 'danger')
        return redirect(url_for('contacts.list_contacts'))

    new_contact = Contact(
        name=name,
        email=email,
        title=request.form.get('title'),
        work_phone_number=request.form.get('work_phone_number'),
        mobile_phone_number=request.form.get('mobile_phone_number'),
        active=True
    )

    for acc_num in company_account_numbers:
        company = db.session.get(Company, acc_num)
        if company:
            new_contact.companies.append(company)

    db.session.add(new_contact)
    db.session.commit()
    flash(f"Contact '{name}' created successfully.", 'success')
    return redirect(url_for('contacts.list_contacts'))

@contacts_bp.route('/<int:contact_id>', methods=['GET', 'POST'])
def contact_details(contact_id):
    contact = Contact.query.get_or_404(contact_id)
    all_companies = Company.query.order_by(Company.name).all()

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

    # Correctly query assets based on all associated companies
    company_account_numbers = [c.account_number for c in contact.companies]
    company_assets = Asset.query.filter(Asset.company_account_number.in_(company_account_numbers)).all()

    # Sanitize secondary emails for the edit modal input
    secondary_emails_for_input = ''
    if contact.secondary_emails:
        try:
            emails_list = json.loads(contact.secondary_emails)
            if isinstance(emails_list, list):
                secondary_emails_for_input = ', '.join(emails_list)
            else:
                secondary_emails_for_input = contact.secondary_emails
        except (json.JSONDecodeError, TypeError):
            secondary_emails_for_input = contact.secondary_emails

    return render_template('contact_details.html', contact=contact, company_assets=company_assets, all_companies=all_companies, secondary_emails_for_input=secondary_emails_for_input)

@contacts_bp.route('/edit/<int:contact_id>', methods=['POST'])
def edit_contact(contact_id):
    contact = Contact.query.get_or_404(contact_id)
    if contact:
        contact.name = request.form.get('name')
        contact.email = request.form.get('email')
        contact.title = request.form.get('title')
        contact.employment_type = request.form.get('employment_type')
        contact.active = request.form.get('active') == 'true'
        contact.mobile_phone_number = request.form.get('mobile_phone_number')
        contact.work_phone_number = request.form.get('work_phone_number')

        raw_secondary_emails = request.form.get('secondary_emails', '')
        emails_list = [email.strip() for email in raw_secondary_emails.split(',') if email.strip()]
        contact.secondary_emails = json.dumps(emails_list)

        # Update company associations
        company_account_numbers = request.form.getlist('company_account_numbers')
        contact.companies = []
        for acc_num in company_account_numbers:
            company = db.session.get(Company, acc_num)
            if company:
                contact.companies.append(company)

        db.session.commit()
        flash('Contact details updated successfully.', 'success')
    else:
        flash('Contact not found.', 'danger')
    return redirect(url_for('contacts.contact_details', contact_id=contact_id))

@contacts_bp.route('/delete/<int:contact_id>', methods=['POST'])
@admin_required
def delete_contact(contact_id):
    """Deletes a contact."""
    contact = Contact.query.get_or_404(contact_id)
    if contact:
        # Manually clear the asset associations to be safe.
        contact.assets = []
        contact.companies = []
        db.session.commit()

        db.session.delete(contact)
        db.session.commit()
        flash(f"Contact '{contact.name}' has been deleted successfully.", 'success')
    else:
        flash('Contact not found.', 'danger')

    return redirect(url_for('contacts.list_contacts'))

