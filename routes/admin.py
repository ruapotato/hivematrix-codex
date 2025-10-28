from flask import Blueprint, render_template, g, request, redirect, url_for, flash, current_app
from app.auth import admin_required
from models import db, Company, Contact, Asset, Location, DattoSiteLink, CompanyFeatureOverride, TicketDetail, SyncJob, Agent, contact_company_link, asset_contact_link
import configparser
import os

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/')
@admin_required
def settings():
    """Admin settings page."""
    # Load current configuration
    config = current_app.config['CODEX_CONFIG']

    # Get database stats
    stats = {
        'companies': Company.query.count(),
        'contacts': Contact.query.count(),
        'assets': Asset.query.count(),
        'tickets': TicketDetail.query.count(),
        'agents': Agent.query.count(),
        'active_contacts': Contact.query.filter_by(active=True).count(),
        'online_assets': Asset.query.filter_by(online=True).count(),
        'enabled_agents': Agent.query.filter_by(enabled=True).count(),
    }

    # Get configuration values
    fs_config = {
        'domain': config.get('freshservice', 'domain', fallback='Not configured'),
        'api_key_set': bool(config.get('freshservice', 'api_key', fallback='') and
                           config.get('freshservice', 'api_key') not in ['', 'YOUR_FRESHSERVICE_API_KEY'])
    }

    datto_config = {
        'api_endpoint': config.get('datto', 'api_endpoint', fallback='Not configured'),
        'public_key_set': bool(config.get('datto', 'public_key', fallback='') and
                              config.get('datto', 'public_key') not in ['', 'YOUR_DATTO_PUBLIC_KEY']),
        'secret_key_set': bool(config.get('datto', 'secret_key', fallback='') and
                              config.get('datto', 'secret_key') not in ['', 'YOUR_DATTO_SECRET_KEY'])
    }

    db_config = {
        'host': config.get('database_credentials', 'db_host', fallback='Unknown'),
        'port': config.get('database_credentials', 'db_port', fallback='Unknown'),
        'dbname': config.get('database_credentials', 'db_dbname', fallback='Unknown'),
        'user': config.get('database_credentials', 'db_user', fallback='Unknown'),
    }

    # Get scheduler configuration
    scheduler_config = {
        'freshservice_enabled': current_app.config.get('SYNC_FRESHSERVICE_ENABLED', True),
        'datto_enabled': current_app.config.get('SYNC_DATTO_ENABLED', True),
        'tickets_enabled': current_app.config.get('SYNC_TICKETS_ENABLED', False),
        'freshservice_schedule': current_app.config.get('SYNC_FRESHSERVICE_SCHEDULE', 'daily'),
        'datto_schedule': current_app.config.get('SYNC_DATTO_SCHEDULE', 'daily'),
        'tickets_schedule': current_app.config.get('SYNC_TICKETS_SCHEDULE', 'hourly'),
        'run_on_startup': current_app.config.get('SYNC_RUN_ON_STARTUP', False),
    }

    # Get scheduler status
    from app.scheduler import get_scheduler
    scheduler = get_scheduler()
    scheduler_jobs = []
    if scheduler:
        for job in scheduler.get_jobs():
            scheduler_jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run': job.next_run_time.strftime('%Y-%m-%d %H:%M:%S') if job.next_run_time else 'N/A'
            })

    # Get recent sync jobs (last 10)
    recent_jobs = SyncJob.query.order_by(SyncJob.started_at.desc()).limit(10).all()

    return render_template('admin/settings.html',
                         user=g.user,
                         stats=stats,
                         fs_config=fs_config,
                         datto_config=datto_config,
                         db_config=db_config,
                         scheduler_config=scheduler_config,
                         scheduler_jobs=scheduler_jobs,
                         recent_jobs=recent_jobs)

@admin_bp.route('/update-freshservice', methods=['POST'])
@admin_required
def update_freshservice():
    """Update Freshservice configuration."""
    config_path = os.path.join(current_app.instance_path, 'codex.conf')
    config = configparser.RawConfigParser()
    config.read(config_path)
    
    domain = request.form.get('fs_domain')
    api_key = request.form.get('fs_api_key')
    
    if domain:
        config.set('freshservice', 'domain', domain)
    if api_key:
        config.set('freshservice', 'api_key', api_key)
    
    with open(config_path, 'w') as f:
        config.write(f)
    
    # Reload config in app
    current_app.config['CODEX_CONFIG'] = config
    
    return redirect(url_for('admin.settings'))

@admin_bp.route('/update-datto', methods=['POST'])
@admin_required
def update_datto():
    """Update Datto RMM configuration."""
    config_path = os.path.join(current_app.instance_path, 'codex.conf')
    config = configparser.RawConfigParser()
    config.read(config_path)
    
    api_endpoint = request.form.get('datto_endpoint')
    public_key = request.form.get('datto_public_key')
    secret_key = request.form.get('datto_secret_key')
    
    if api_endpoint:
        config.set('datto', 'api_endpoint', api_endpoint)
    if public_key:
        config.set('datto', 'public_key', public_key)
    if secret_key:
        config.set('datto', 'secret_key', secret_key)
    
    with open(config_path, 'w') as f:
        config.write(f)
    
    # Reload config in app
    current_app.config['CODEX_CONFIG'] = config
    
    return redirect(url_for('admin.settings'))

@admin_bp.route('/clear-data', methods=['POST'])
@admin_required
def clear_data():
    """Clear all CRM data (dangerous operation)."""
    data_type = request.form.get('data_type')

    try:
        if data_type == 'companies':
            deleted_count = Company.query.count()
            # Clear association tables first
            db.session.execute(contact_company_link.delete())
            # Delete related tables in order (foreign keys)
            TicketDetail.query.delete()
            DattoSiteLink.query.delete()
            Location.query.delete()
            CompanyFeatureOverride.query.delete()
            Asset.query.delete()
            # Now delete companies
            Company.query.delete()
            db.session.commit()
            flash(f'✓ Deleted {deleted_count} companies and all related data', 'success')

        elif data_type == 'contacts':
            deleted_count = Contact.query.count()
            # Clear association tables first
            db.session.execute(contact_company_link.delete())
            db.session.execute(asset_contact_link.delete())
            # Now safe to delete contacts
            Contact.query.delete()
            db.session.commit()
            flash(f'✓ Deleted {deleted_count} contacts', 'success')

        elif data_type == 'assets':
            deleted_count = Asset.query.count()
            # Clear association tables first
            db.session.execute(asset_contact_link.delete())
            # Now safe to delete assets
            Asset.query.delete()
            db.session.commit()
            flash(f'✓ Deleted {deleted_count} assets', 'success')

        elif data_type == 'agents':
            deleted_count = Agent.query.count()
            # Agents have no foreign key dependencies
            Agent.query.delete()
            db.session.commit()
            flash(f'✓ Deleted {deleted_count} agents', 'success')

        elif data_type == 'all':
            asset_count = Asset.query.count()
            contact_count = Contact.query.count()
            company_count = Company.query.count()
            agent_count = Agent.query.count()

            # Delete association tables first
            db.session.execute(asset_contact_link.delete())
            db.session.execute(contact_company_link.delete())

            # Delete in proper order (respecting all foreign keys)
            TicketDetail.query.delete()
            DattoSiteLink.query.delete()
            Location.query.delete()
            CompanyFeatureOverride.query.delete()
            Asset.query.delete()
            Contact.query.delete()
            Company.query.delete()
            Agent.query.delete()

            db.session.commit()
            flash(f'✓ Deleted ALL data: {company_count} companies, {contact_count} contacts, {asset_count} assets, {agent_count} agents', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'✗ Error deleting data: {str(e)}', 'error')

    return redirect(url_for('admin.settings'))
