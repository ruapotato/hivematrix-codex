from datetime import datetime
from flask import render_template, g, jsonify, request
from app import app
from .auth import token_required, admin_required
from models import Company, Contact, Asset, Location, TicketDetail
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
    """Get all companies with their assets, contacts, locations, and tickets in one call - optimized for Ledger."""
    import json

    # Get optional query parameters
    include_tickets = request.args.get('include_tickets', 'false').lower() == 'true'
    year = request.args.get('year', type=int)

    companies = Company.query.all()
    result = []

    for company in companies:
        assets = Asset.query.filter_by(company_account_number=company.account_number).all()

        company_data = {
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
                'backup_usage_tb': a.backup_usage_tb,
                'backup_data_bytes': int(float(a.backup_usage_tb or 0) * 1099511627776) if a.backup_usage_tb else 0
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
        }

        # Optionally include tickets (disabled by default for performance)
        if include_tickets:
            query = TicketDetail.query.filter_by(company_account_number=company.account_number)

            if year:
                tickets = [t for t in query.all() if t.last_updated_at and t.last_updated_at.startswith(str(year))]
            else:
                tickets = query.all()

            company_data['tickets'] = [{
                'ticket_id': t.ticket_id,
                'ticket_number': t.ticket_number,
                'subject': t.subject,
                'description': t.description,
                'description_text': t.description_text,
                'status': t.status,
                'priority': t.priority,
                'requester_email': t.requester_email,
                'requester_name': t.requester_name,
                'created_at': t.created_at,
                'last_updated_at': t.last_updated_at,
                'closed_at': t.closed_at,
                'total_hours_spent': float(t.total_hours_spent or 0),
                'conversations': json.loads(t.conversations) if t.conversations else [],
                'notes': json.loads(t.notes) if t.notes else []
            } for t in tickets]

        result.append(company_data)

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
        'backup_usage_tb': a.backup_usage_tb,
        'backup_data_bytes': int(float(a.backup_usage_tb or 0) * 1099511627776) if a.backup_usage_tb else 0
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


@app.route('/api/companies/<account_number>/users')
@token_required
def api_get_company_users(account_number):
    """Alias for api_get_company_contacts - 'users' is more intuitive for KnowledgeTree."""
    return api_get_company_contacts(account_number)


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


@app.route('/api/companies/<account_number>/tickets')
@token_required
def api_get_company_tickets(account_number):
    """Get all tickets for a company - used by Ledger service."""
    company = Company.query.get(account_number)
    if not company:
        return {'error': 'Company not found'}, 404

    # Get optional year filter
    year = request.args.get('year', type=int)

    query = TicketDetail.query.filter_by(company_account_number=account_number)

    if year:
        # Filter by year using string substring matching (since last_updated_at is stored as string)
        tickets = [t for t in query.all() if t.last_updated_at and t.last_updated_at.startswith(str(year))]
    else:
        tickets = query.all()

    import json
    return jsonify([{
        'ticket_id': t.ticket_id,
        'ticket_number': t.ticket_number,
        'subject': t.subject,
        'description': t.description,
        'description_text': t.description_text,
        'status': t.status,
        'priority': t.priority,
        'requester_email': t.requester_email,
        'requester_name': t.requester_name,
        'created_at': t.created_at,
        'last_updated_at': t.last_updated_at,
        'closed_at': t.closed_at,
        'total_hours_spent': float(t.total_hours_spent or 0),
        'conversations': json.loads(t.conversations) if t.conversations else [],
        'notes': json.loads(t.notes) if t.notes else []
    } for t in tickets])


@app.route('/sync/tickets', methods=['POST'])
@admin_required
def sync_tickets():
    """Trigger Freshservice ticket sync script."""
    try:
        script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'sync_tickets_from_freshservice.py')
        result = subprocess.run(
            ['python', script_path],
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout for ticket sync
        )

        return jsonify({
            'success': result.returncode == 0,
            'output': result.stdout,
            'error': result.stderr
        })
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'error': 'Script timed out after 10 minutes'
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring"""
    return {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat()
    }
