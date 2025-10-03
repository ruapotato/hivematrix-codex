from flask import render_template, g, jsonify, request
from app import app
from .auth import token_required, admin_required
from models import Company, Contact, Asset, Location
import subprocess
import os

@app.route('/')
@token_required
def index():
    """Main dashboard route."""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403
    
    # Get counts for dashboard
    company_count = Company.query.count()
    contact_count = Contact.query.count()
    asset_count = Asset.query.count()
    
    return render_template('dashboard.html', 
                         user=g.user,
                         company_count=company_count,
                         contact_count=contact_count,
                         asset_count=asset_count)

@app.route('/sync/freshservice', methods=['POST'])
@admin_required
def sync_freshservice():
    """Trigger Freshservice sync script."""
    try:
        script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'pull_freshservice.py')
        result = subprocess.run(
            ['python', script_path],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        return jsonify({
            'success': result.returncode == 0,
            'output': result.stdout,
            'error': result.stderr
        })
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'error': 'Script timed out after 5 minutes'
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/sync/datto', methods=['POST'])
@admin_required
def sync_datto():
    """Trigger Datto RMM sync script."""
    try:
        script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'pull_datto.py')
        result = subprocess.run(
            ['python', script_path],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        return jsonify({
            'success': result.returncode == 0,
            'output': result.stdout,
            'error': result.stderr
        })
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'error': 'Script timed out after 5 minutes'
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# --- API Endpoints for Service-to-Service Communication ---

@app.route('/api/companies')
@token_required
def api_get_all_companies():
    """Get all companies - used by Ledger service."""
    companies = Company.query.all()
    return jsonify([{
        'account_number': c.account_number,
        'name': c.name,
        'description': c.description,
        'billing_plan': c.plan_selected,
        'profit_or_non_profit': c.profit_or_non_profit,
        'company_main_number': c.company_main_number,
        'company_start_date': c.company_start_date,
        'domains': c.domains,
        'phone_system': c.phone_system,
        'email_system': c.email_system
    } for c in companies])


@app.route('/api/companies/bulk')
@token_required
def api_get_all_companies_bulk():
    """Get all companies with their assets, contacts, and locations in one call - optimized for Ledger."""
    companies = Company.query.all()
    result = []

    for company in companies:
        assets = Asset.query.filter_by(company_account_number=company.account_number).all()

        result.append({
            'company': {
                'account_number': company.account_number,
                'name': company.name,
                'description': company.description,
                'billing_plan': company.plan_selected,
                'profit_or_non_profit': company.profit_or_non_profit,
                'company_main_number': company.company_main_number,
                'company_start_date': company.company_start_date,
                'domains': company.domains,
                'phone_system': company.phone_system,
                'email_system': company.email_system
            },
            'assets': [{
                'id': a.id,
                'hostname': a.hostname,
                'hardware_type': a.hardware_type,
                'operating_system': a.operating_system,
                'device_type': a.device_type,
                'last_logged_in_user': a.last_logged_in_user,
                'antivirus_product': a.antivirus_product,
                'ext_ip_address': a.ext_ip_address,
                'int_ip_address': a.int_ip_address,
                'domain': a.domain,
                'online': a.online,
                'last_seen': a.last_seen,
                'backup_usage_tb': a.backup_usage_tb
            } for a in assets],
            'contacts': [{
                'id': c.id,
                'name': c.name,
                'email': c.email,
                'title': c.title,
                'employment_type': c.employment_type,
                'active': c.active,
                'mobile_phone_number': c.mobile_phone_number,
                'work_phone_number': c.work_phone_number,
                'secondary_emails': c.secondary_emails
            } for c in company.contacts],
            'locations': [{
                'id': l.id,
                'name': l.name,
                'address': l.address,
                'phone_number': l.phone_number
            } for l in company.locations]
        })

    return jsonify(result)


@app.route('/api/companies/<account_number>')
@token_required
def api_get_company(account_number):
    """Get single company by account number - used by Ledger service."""
    company = Company.query.get(account_number)
    if not company:
        return {'error': 'Company not found'}, 404

    return jsonify({
        'account_number': company.account_number,
        'name': company.name,
        'description': company.description,
        'billing_plan': company.plan_selected,
        'profit_or_non_profit': company.profit_or_non_profit,
        'company_main_number': company.company_main_number,
        'company_start_date': company.company_start_date,
        'domains': company.domains,
        'phone_system': company.phone_system,
        'email_system': company.email_system
    })


@app.route('/api/companies/<account_number>/assets')
@token_required
def api_get_company_assets(account_number):
    """Get all assets for a company - used by Ledger service."""
    company = Company.query.get(account_number)
    if not company:
        return {'error': 'Company not found'}, 404

    assets = Asset.query.filter_by(company_account_number=account_number).all()
    return jsonify([{
        'id': a.id,
        'hostname': a.hostname,
        'hardware_type': a.hardware_type,
        'operating_system': a.operating_system,
        'device_type': a.device_type,
        'last_logged_in_user': a.last_logged_in_user,
        'antivirus_product': a.antivirus_product,
        'ext_ip_address': a.ext_ip_address,
        'int_ip_address': a.int_ip_address,
        'domain': a.domain,
        'online': a.online,
        'last_seen': a.last_seen,
        'backup_usage_tb': a.backup_usage_tb
    } for a in assets])


@app.route('/api/companies/<account_number>/contacts')
@token_required
def api_get_company_contacts(account_number):
    """Get all contacts for a company - used by Ledger service."""
    company = Company.query.get(account_number)
    if not company:
        return {'error': 'Company not found'}, 404

    return jsonify([{
        'id': c.id,
        'name': c.name,
        'email': c.email,
        'title': c.title,
        'employment_type': c.employment_type,
        'active': c.active,
        'mobile_phone_number': c.mobile_phone_number,
        'work_phone_number': c.work_phone_number,
        'secondary_emails': c.secondary_emails
    } for c in company.contacts])


@app.route('/api/companies/<account_number>/locations')
@token_required
def api_get_company_locations(account_number):
    """Get all locations for a company - used by Ledger service."""
    company = Company.query.get(account_number)
    if not company:
        return {'error': 'Company not found'}, 404

    return jsonify([{
        'id': l.id,
        'name': l.name,
        'address': l.address,
        'phone_number': l.phone_number
    } for l in company.locations])
