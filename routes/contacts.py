from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Contact, Asset
from decorators import admin_required

# Corrected Blueprint definition
contacts_bp = Blueprint('contacts', __name__, url_prefix='/contacts')

@contacts_bp.route('/')
def list_contacts():
    contacts = Contact.query.all()
    return render_template('contacts.html', contacts=contacts)

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

    company_assets = Asset.query.filter_by(company_id=contact.company_id).all()
    return render_template('contact_details.html', contact=contact, company_assets=company_assets)

