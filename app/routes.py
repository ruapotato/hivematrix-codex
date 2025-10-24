from datetime import datetime
from flask import render_template, g, jsonify, request
from app import app
from .auth import token_required, admin_required
from models import Company, Contact, Asset, Location, TicketDetail, SyncJob
from extensions import db
import subprocess
import os
import uuid
import threading

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

    # Get recent sync jobs for visibility
    recent_jobs = SyncJob.query.order_by(SyncJob.started_at.desc()).limit(10).all()

    return render_template('dashboard.html',
                         user=g.user,
                         company_count=company_count,
                         contact_count=contact_count,
                         asset_count=asset_count,
                         recent_jobs=recent_jobs)

def run_sync_script(job_id, script_path, follow_up_script=None):
    """Run sync script in background and update job status in database."""
    try:
        # Increase timeout for ticket sync (can take 2+ hours)
        timeout = 7200 if 'ticket' in script_path else 600  # 2 hours for tickets, 10 min for others

        result = subprocess.run(
            ['python', script_path],
            capture_output=True,
            text=True,
            timeout=timeout
        )

        # Update job in database
        with app.app_context():
            job = db.session.get(SyncJob, job_id)
            if job:
                job.status = 'completed' if result.returncode == 0 else 'failed'
                job.success = result.returncode == 0
                job.output = result.stdout[-1000:]  # Last 1000 chars
                job.error = result.stderr[-1000:] if result.stderr else None
                job.completed_at = datetime.now().isoformat()
                db.session.commit()

                # Run follow-up script if main script succeeded
                if result.returncode == 0 and follow_up_script:
                    try:
                        follow_result = subprocess.run(
                            ['python', follow_up_script],
                            capture_output=True,
                            text=True,
                            timeout=300  # 5 min timeout for follow-up
                        )
                        # Append follow-up output to job output
                        follow_output = f"\n\n--- Auto-Run Follow-Up ---\n{follow_result.stdout[-500:]}"
                        job.output = (job.output or '') + follow_output
                        db.session.commit()
                    except Exception as e:
                        print(f"Follow-up script failed: {e}")

    except subprocess.TimeoutExpired:
        with app.app_context():
            job = db.session.get(SyncJob, job_id)
            if job:
                job.status = 'failed'
                job.success = False
                job.error = f'Script timed out after {timeout//60} minutes'
                job.completed_at = datetime.now().isoformat()
                db.session.commit()

    except Exception as e:
        with app.app_context():
            job = db.session.get(SyncJob, job_id)
            if job:
                job.status = 'failed'
                job.success = False
                job.error = str(e)
                job.completed_at = datetime.now().isoformat()
                db.session.commit()

@app.route('/sync/freshservice', methods=['POST'])
@admin_required
def sync_freshservice():
    """Trigger Freshservice sync script in background."""
    try:
        job_id = str(uuid.uuid4())
        script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'pull_freshservice.py')
        follow_up_script = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'create_account_numbers.py')

        # Create job entry in database
        job = SyncJob(
            id=job_id,
            script='freshservice',
            status='running',
            started_at=datetime.now().isoformat()
        )
        db.session.add(job)
        db.session.commit()

        # Start background thread with auto-run of account number creation
        thread = threading.Thread(target=run_sync_script, args=(job_id, script_path, follow_up_script))
        thread.daemon = True
        thread.start()

        return jsonify({
            'success': True,
            'job_id': job_id,
            'message': 'Freshservice sync started in background (will auto-create account numbers)'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/sync/datto', methods=['POST'])
@admin_required
def sync_datto():
    """Trigger Datto RMM sync script in background."""
    try:
        job_id = str(uuid.uuid4())
        script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'pull_datto.py')
        follow_up_script = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'push_account_nums_to_datto.py')

        # Create job entry in database
        job = SyncJob(
            id=job_id,
            script='datto',
            status='running',
            started_at=datetime.now().isoformat()
        )
        db.session.add(job)
        db.session.commit()

        # Start background thread with auto-run of push to datto
        thread = threading.Thread(target=run_sync_script, args=(job_id, script_path, follow_up_script))
        thread.daemon = True
        thread.start()

        return jsonify({
            'success': True,
            'job_id': job_id,
            'message': 'Datto RMM sync started in background (will auto-push account numbers)'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/sync/status/<job_id>', methods=['GET'])
@admin_required
def sync_status(job_id):
    """Check status of a background sync job with live progress."""
    job = db.session.get(SyncJob, job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404

    job_data = {
        'id': job.id,
        'script': job.script,
        'status': job.status,
        'started_at': job.started_at,
        'completed_at': job.completed_at,
        'output': job.output,
        'error': job.error,
        'success': job.success
    }

    # Add current ticket count for ticket syncs to show progress
    if job.script == 'tickets' and job.status == 'running':
        job_data['current_tickets'] = TicketDetail.query.count()

    return jsonify(job_data)

@app.route('/sync/create-account-numbers', methods=['POST'])
@admin_required
def sync_create_account_numbers():
    """Create account numbers for companies that don't have them."""
    try:
        job_id = str(uuid.uuid4())
        script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'create_account_numbers.py')

        # Create job entry in database
        job = SyncJob(
            id=job_id,
            script='create-account-numbers',
            status='running',
            started_at=datetime.now().isoformat()
        )
        db.session.add(job)
        db.session.commit()

        # Start background thread
        thread = threading.Thread(target=run_sync_script, args=(job_id, script_path))
        thread.daemon = True
        thread.start()

        return jsonify({
            'success': True,
            'job_id': job_id,
            'message': 'Account number creation started in background'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/sync/push-to-datto', methods=['POST'])
@admin_required
def sync_push_to_datto():
    """Push account numbers to Datto RMM sites."""
    try:
        job_id = str(uuid.uuid4())
        script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'push_account_nums_to_datto.py')

        # Create job entry in database
        job = SyncJob(
            id=job_id,
            script='push-to-datto',
            status='running',
            started_at=datetime.now().isoformat()
        )
        db.session.add(job)
        db.session.commit()

        # Start background thread
        thread = threading.Thread(target=run_sync_script, args=(job_id, script_path))
        thread.daemon = True
        thread.start()

        return jsonify({
            'success': True,
            'job_id': job_id,
            'message': 'Push to Datto started in background'
        })
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
    """Trigger Freshservice ticket sync script in background."""
    try:
        job_id = str(uuid.uuid4())
        script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'sync_tickets_from_freshservice.py')

        # Create job entry in database
        job = SyncJob(
            id=job_id,
            script='tickets',
            status='running',
            started_at=datetime.now().isoformat()
        )
        db.session.add(job)
        db.session.commit()

        # Start background thread
        thread = threading.Thread(target=run_sync_script, args=(job_id, script_path))
        thread.daemon = True
        thread.start()

        return jsonify({
            'success': True,
            'job_id': job_id,
            'message': 'Ticket sync started in background'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/sync/last/<script_name>', methods=['GET'])
@token_required
def get_last_sync(script_name):
    """Get the last sync job for a specific script (persists across page loads)."""
    job = SyncJob.query.filter_by(script=script_name).order_by(SyncJob.started_at.desc()).first()

    if not job:
        return jsonify({'error': 'No sync found for this script'}), 404

    return jsonify({
        'id': job.id,
        'script': job.script,
        'status': job.status,
        'started_at': job.started_at,
        'completed_at': job.completed_at,
        'output': job.output,
        'error': job.error,
        'success': job.success
    })

@app.route('/api/tickets', methods=['GET'])
@token_required
def api_list_tickets():
    """
    List all tickets with optional filtering.

    Query parameters:
        company_id: Filter by company account number
        status: Filter by status
        priority: Filter by priority
        limit: Maximum number of tickets to return (default 50)
        offset: Number of tickets to skip (for pagination)
    """
    import json

    # Get query parameters
    company_id = request.args.get('company_id')
    status = request.args.get('status')
    priority = request.args.get('priority')
    limit = request.args.get('limit', type=int, default=50)
    offset = request.args.get('offset', type=int, default=0)

    # Build query
    query = TicketDetail.query

    if company_id:
        query = query.filter_by(company_account_number=company_id)
    if status:
        query = query.filter_by(status=status)
    if priority:
        query = query.filter_by(priority=priority)

    # Order by last updated (most recent first)
    query = query.order_by(TicketDetail.last_updated_at.desc())

    # Get total count
    total_count = query.count()

    # Apply pagination
    tickets = query.offset(offset).limit(limit).all()

    return jsonify({
        'tickets': [{
            'id': t.ticket_id,
            'ticket_number': t.ticket_number,
            'subject': t.subject,
            'description_text': t.description_text,
            'status': t.status,
            'priority': t.priority,
            'company_id': t.company_account_number,
            'requester_email': t.requester_email,
            'requester_name': t.requester_name,
            'created_at': t.created_at,
            'last_updated_at': t.last_updated_at,
            'closed_at': t.closed_at,
            'total_hours_spent': float(t.total_hours_spent or 0)
        } for t in tickets],
        'count': len(tickets),
        'total': total_count,
        'offset': offset,
        'limit': limit
    })


@app.route('/api/ticket/<int:ticket_id>', methods=['GET'])
@token_required
def api_get_ticket(ticket_id):
    """
    Get detailed information about a specific ticket.

    Includes conversations and notes.
    If ticket is not in local database, fetches from FreshService API.
    """
    import json
    from .freshservice_client import fetch_ticket_from_freshservice

    # First, try to get from local database
    ticket = TicketDetail.query.get(ticket_id)
    if ticket:
        # Get company info
        company = Company.query.get(ticket.company_account_number)

        return jsonify({
            'id': ticket.ticket_id,
            'ticket_number': ticket.ticket_number,
            'subject': ticket.subject,
            'description': ticket.description,
            'description_text': ticket.description_text,
            'status': ticket.status,
            'priority': ticket.priority,
            'company_id': ticket.company_account_number,
            'company_name': company.name if company else None,
            'requester_email': ticket.requester_email,
            'requester_name': ticket.requester_name,
            'created_at': ticket.created_at,
            'last_updated_at': ticket.last_updated_at,
            'closed_at': ticket.closed_at,
            'total_hours_spent': float(ticket.total_hours_spent or 0),
            'conversations': json.loads(ticket.conversations) if ticket.conversations else [],
            'notes': json.loads(ticket.notes) if ticket.notes else []
        })

    # Ticket not in local database - try FreshService
    app.logger.info(f"Ticket {ticket_id} not found locally, fetching from FreshService...")
    freshservice_ticket = fetch_ticket_from_freshservice(ticket_id)

    if not freshservice_ticket:
        return {'error': 'Ticket not found'}, 404

    # Return FreshService data directly
    return jsonify(freshservice_ticket)


@app.route('/api/ticket/<int:ticket_id>/update', methods=['POST'])
@token_required
def api_update_ticket(ticket_id):
    """
    Update a ticket.

    Request body:
        status: New status (optional)
        notes: Note to add (optional)
        assigned_to: Assign to user (optional) - Note: Not stored in current schema
    """
    import json

    ticket = TicketDetail.query.get(ticket_id)
    if not ticket:
        return {'error': 'Ticket not found'}, 404

    data = request.get_json() or {}

    # Update status if provided
    if 'status' in data:
        ticket.status = data['status']
        ticket.last_updated_at = datetime.now().isoformat()

    # Add note if provided
    if 'notes' in data and data['notes']:
        current_notes = json.loads(ticket.notes) if ticket.notes else []
        new_note = {
            'created_at': datetime.now().isoformat(),
            'text': data['notes'],
            'user': g.user.get('preferred_username', 'unknown') if hasattr(g, 'user') and g.user else 'system'
        }
        current_notes.append(new_note)
        ticket.notes = json.dumps(current_notes)
        ticket.last_updated_at = datetime.now().isoformat()

    # Commit changes
    try:
        db.session.commit()
        return jsonify({
            'success': True,
            'ticket_id': ticket_id,
            'message': 'Ticket updated successfully'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/datto/devices', methods=['GET'])
@token_required
def api_list_devices():
    """
    List all devices from Datto RMM (currently uses Asset data).

    Query parameters:
        company_id: Filter by company account number
        status: Filter by status ('online', 'offline')
        limit: Maximum number of devices to return (default 100)
    """
    # Get query parameters
    company_id = request.args.get('company_id')
    status = request.args.get('status')
    limit = request.args.get('limit', type=int, default=100)

    # Build query
    query = Asset.query

    if company_id:
        query = query.filter_by(company_account_number=company_id)

    if status:
        if status.lower() == 'online':
            query = query.filter_by(online=True)
        elif status.lower() == 'offline':
            query = query.filter_by(online=False)

    # Get devices
    assets = query.limit(limit).all()

    return jsonify({
        'devices': [{
            'id': f"device-{a.id}",
            'name': a.hostname,
            'company_id': a.company_account_number,
            'company_name': a.company.name if a.company else None,
            'status': 'online' if a.online else 'offline',
            'os': a.operating_system,
            'device_type': a.device_type or a.hardware_type,
            'ip_address': a.ext_ip_address or a.int_ip_address,
            'last_seen': a.last_seen,
            'last_logged_in_user': a.last_logged_in_user
        } for a in assets],
        'count': len(assets)
    })


@app.route('/api/datto/device/<device_id>', methods=['GET'])
@token_required
def api_get_device(device_id):
    """
    Get detailed information about a specific device.

    Device ID format: "device-{asset_id}"
    """
    # Extract asset ID from device ID
    if not device_id.startswith('device-'):
        return {'error': 'Invalid device ID format'}, 400

    try:
        asset_id = int(device_id.replace('device-', ''))
    except ValueError:
        return {'error': 'Invalid device ID'}, 400

    asset = Asset.query.get(asset_id)
    if not asset:
        return {'error': 'Device not found'}, 404

    # Get company info
    company = asset.company

    # Simulate health metrics (will be replaced with real Datto data)
    import random
    random.seed(asset_id)  # Consistent values for same device

    return jsonify({
        'id': device_id,
        'name': asset.hostname,
        'company_id': asset.company_account_number,
        'company_name': company.name if company else None,
        'status': 'online' if asset.online else 'offline',
        'os': asset.operating_system,
        'os_version': '10.0.19045' if asset.operating_system and 'Windows' in asset.operating_system else 'Unknown',
        'device_type': asset.device_type or asset.hardware_type,
        'ip_address': asset.ext_ip_address or asset.int_ip_address,
        'mac_address': 'XX:XX:XX:XX:XX:XX',  # Masked for PHI
        'last_seen': asset.last_seen,
        'last_logged_in_user': asset.last_logged_in_user,
        'domain': asset.domain,
        'antivirus': asset.antivirus_product,
        'patch_status': asset.patch_status,
        'last_reboot': asset.last_reboot,
        'installed_software': [
            # Simulated - will be replaced with real data
            {'name': 'Microsoft Office', 'version': '16.0'},
            {'name': 'Google Chrome', 'version': '120.0'}
        ],
        'hardware': {
            'cpu': 'Intel Core i7' if asset.device_type != 'Server' else 'Intel Xeon',
            'ram_gb': random.choice([8, 16, 32, 64]),
            'disk_gb': random.choice([256, 512, 1024, 2048])
        },
        'health': {
            'cpu_usage': random.randint(10, 90) if asset.online else 0,
            'ram_usage': random.randint(30, 85) if asset.online else 0,
            'disk_usage': random.randint(40, 95) if asset.online else 0
        }
    })


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring"""
    return {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat()
    }
