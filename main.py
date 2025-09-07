# ruapotato/hivematrix-nexus/hivematrix-nexus-main/main.py

import os
import configparser
import jwt
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from datetime import datetime, timedelta, timezone

from extensions import db, scheduler
from models import User, Company, Asset, Contact, SchedulerJob, Location
from routes.companies import companies_bp
from routes.contacts import contacts_bp
from routes.assets import assets_bp
from routes.users import users_bp
from routes.settings import settings_bp
from decorators import admin_required, token_required

app = Flask(__name__, instance_relative_config=True)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_secure_random_secret_key')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(app.instance_path, 'nexus_brainhair.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.debug = True # Set debug mode here

try:
    os.makedirs(app.instance_path)
except OSError:
    pass

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

config = configparser.ConfigParser()
config_path = os.path.join(app.instance_path, 'nexus.conf')
config.read(config_path)
app.config['NEXUS_CONFIG'] = config

app.register_blueprint(companies_bp)
app.register_blueprint(contacts_bp)
app.register_blueprint(assets_bp)
app.register_blueprint(users_bp)
app.register_blueprint(settings_bp)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.route('/')
@login_required
def dashboard():
    companies = Company.query.all()
    return render_template('dashboard.html', companies=companies)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            session['permission_level'] = user.permission_level
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password')

    users = User.query.order_by(User.username).all()
    return render_template('login.html', users=users)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/token', methods=['POST'])
def get_token():
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({"error": "Missing username or password"}), 400

    user = User.query.filter_by(username=data['username']).first()

    if user and user.check_password(data['password']):
        token = jwt.encode({
            'user_id': user.id,
            'permission_level': user.permission_level,
            'company_account_number': user.company_account_number,
            'exp': datetime.now(timezone.utc) + timedelta(hours=24) # Token expires in 24 hours
        }, app.config['SECRET_KEY'], algorithm="HS256")
        return jsonify({'token': token})

    return jsonify({"error": "Invalid credentials"}), 401


@app.route('/api/companies', methods=['GET', 'POST'])
@token_required(permission_level=['admin', 'technician'])
def api_companies(current_user):
    if request.method == 'POST':
        data = request.get_json()
        if not data or 'name' not in data or 'account_number' not in data:
            return jsonify({"error": "Missing name or account_number"}), 400

        existing_company = db.session.get(Company, data.get('account_number'))

        if existing_company:
            return jsonify({'message': 'Company already exists. Use PUT to update.'}), 409
        else:
            new_company = Company(
                name=data['name'],
                account_number=data['account_number'],
                freshservice_id=data.get('freshservice_id'),
                description=data.get('description'),
                plan_selected=data.get('plan_selected'),
                profit_or_non_profit=data.get('profit_or_non_profit'),
                company_main_number=data.get('company_main_number'),
                company_start_date=data.get('company_start_date'),
                head_name=data.get('head_name'),
                primary_contact_name=data.get('primary_contact_name'),
                domains=data.get('domains')
            )
            db.session.add(new_company)
            db.session.commit()
            return jsonify({'message': 'Company created successfully', 'account_number': new_company.account_number}), 201

    query = Company.query
    if 'freshservice_id' in request.args:
        query = query.filter_by(freshservice_id=request.args['freshservice_id'])

    companies = query.all()
    return jsonify([{
        'account_number': c.account_number, 'name': c.name,
        'freshservice_id': c.freshservice_id,
        'description': c.description, 'plan_selected': c.plan_selected,
        'profit_or_non_profit': c.profit_or_non_profit, 'company_main_number': c.company_main_number,
        'company_start_date': c.company_start_date,
        'head_name': c.head_name, 'primary_contact_name': c.primary_contact_name, 'domains': c.domains
    } for c in companies])

@app.route('/api/companies/<string:account_number>', methods=['GET', 'PUT'])
@token_required(permission_level=['admin', 'technician', 'client'])
def api_company_details(current_user, account_number):
    if current_user.permission_level == 'client' and current_user.company_account_number != account_number:
        return jsonify({"error": "Access denied"}), 403

    company = db.session.get(Company, account_number)
    if not company:
        return jsonify({"error": "Company not found"}), 404

    if request.method == 'PUT':
        if current_user.permission_level == 'client':
            return jsonify({"error": "Clients cannot update company details"}), 403
        data = request.get_json()
        if 'name' in data: company.name = data['name']
        if 'freshservice_id' in data: company.freshservice_id = data['freshservice_id']
        if 'description' in data: company.description = data['description']
        if 'plan_selected' in data: company.plan_selected = data['plan_selected']
        if 'profit_or_non_profit' in data: company.profit_or_non_profit = data['profit_or_non_profit']
        if 'company_main_number' in data: company.company_main_number = data['company_main_number']
        if 'company_start_date' in data: company.company_start_date = data['company_start_date']
        if 'head_name' in data: company.head_name = data['head_name']
        if 'primary_contact_name' in data: company.primary_contact_name = data['primary_contact_name']
        if 'domains' in data: company.domains = data['domains']
        db.session.commit()
        return jsonify({'message': 'Company updated successfully'})

    return jsonify({
        'account_number': company.account_number, 'name': company.name,
        'freshservice_id': company.freshservice_id,
        'description': company.description, 'plan_selected': company.plan_selected,
        'profit_or_non_profit': company.profit_or_non_profit, 'company_main_number': company.company_main_number,
        'company_start_date': company.company_start_date,
        'head_name': company.head_name, 'primary_contact_name': company.primary_contact_name, 'domains': company.domains
    })

@app.route('/api/assets', methods=['GET', 'POST'])
@token_required(permission_level=['admin', 'technician'])
def api_assets(current_user):
    if request.method == 'POST':
        data = request.get_json()
        if not data or 'hostname' not in data or 'company_account_number' not in data:
            return jsonify({"error": "Missing hostname or company_account_number"}), 400
        new_asset = Asset(
            hostname=data.get('hostname'),
            company_account_number=data.get('company_account_number'),
            operating_system=data.get('operating_system'),
            last_logged_in_user=data.get('last_logged_in_user'),
            hardware_type=data.get('hardware_type'),
            antivirus_product=data.get('antivirus_product'),
            description=data.get('description'),
            ext_ip_address=data.get('ext_ip_address'),
            int_ip_address=data.get('int_ip_address'),
            domain=data.get('domain'),
            last_audit_date=data.get('last_audit_date'),
            last_reboot=data.get('last_reboot'),
            last_seen=data.get('last_seen'),
            online=data.get('online'),
            patch_status=data.get('patch_status'),
            backup_usage_tb=data.get('backup_usage_tb'),
            enabled_administrators=data.get('enabled_administrators'),
            device_type=data.get('device_type'),
            portal_url=data.get('portal_url'),
            web_remote_url=data.get('web_remote_url')
        )
        db.session.add(new_asset)
        db.session.commit()
        return jsonify({'message': 'Asset created successfully', 'id': new_asset.id}), 201

    query = Asset.query
    if 'company_account_number' in request.args:
        query = query.filter_by(company_account_number=request.args['company_account_number'])
    if 'hostname' in request.args:
        query = query.filter_by(hostname=request.args['hostname'])

    assets = query.all()
    return jsonify([{'id': a.id, 'hostname': a.hostname, 'company_account_number': a.company_account_number} for a in assets])


@app.route('/api/assets/<int:asset_id>', methods=['PUT', 'DELETE'])
@token_required(permission_level=['admin', 'technician'])
def api_asset_details(current_user, asset_id):
    asset = db.session.get(Asset, asset_id)
    if not asset:
        return jsonify({"error": "Asset not found"}), 404

    if request.method == 'DELETE':
        db.session.delete(asset)
        db.session.commit()
        return jsonify({'message': 'Asset deleted successfully'})

    data = request.get_json()
    if 'hostname' in data: asset.hostname = data['hostname']
    if 'company_account_number' in data: asset.company_account_number = data['company_account_number']
    if 'operating_system' in data: asset.operating_system = data['operating_system']
    if 'last_logged_in_user' in data: asset.last_logged_in_user = data['last_logged_in_user']
    if 'hardware_type' in data: asset.hardware_type = data['hardware_type']
    if 'antivirus_product' in data: asset.antivirus_product = data['antivirus_product']
    if 'description' in data: asset.description = data['description']
    if 'ext_ip_address' in data: asset.ext_ip_address = data['ext_ip_address']
    if 'int_ip_address' in data: asset.int_ip_address = data['int_ip_address']
    if 'domain' in data: asset.domain = data['domain']
    if 'last_audit_date' in data: asset.last_audit_date = data['last_audit_date']
    if 'last_reboot' in data: asset.last_reboot = data['last_reboot']
    if 'last_seen' in data: asset.last_seen = data['last_seen']
    if 'online' in data: asset.online = data['online']
    if 'patch_status' in data: asset.patch_status = data['patch_status']
    if 'backup_usage_tb' in data: asset.backup_usage_tb = data['backup_usage_tb']
    if 'enabled_administrators' in data: asset.enabled_administrators = data['enabled_administrators']
    if 'device_type' in data: asset.device_type = data['device_type']
    if 'portal_url' in data: asset.portal_url = data['portal_url']
    if 'web_remote_url' in data: asset.web_remote_url = data['web_remote_url']
    db.session.commit()
    return jsonify({'message': 'Asset updated successfully'})

@app.route('/api/contacts', methods=['GET', 'POST'])
@token_required(permission_level=['admin', 'technician'])
def api_contacts(current_user):
    if request.method == 'POST':
        data = request.get_json()
        if not data or 'name' not in data or 'email' not in data or 'company_account_number' not in data:
            return jsonify({"error": "Missing name, email, or company_account_number"}), 400
        new_contact = Contact(
            name=data['name'],
            email=data['email'],
            company_account_number=data['company_account_number'],
            title=data.get('title'),
            active=data.get('active'),
            mobile_phone_number=data.get('mobile_phone_number'),
            work_phone_number=data.get('work_phone_number'),
            secondary_emails=data.get('secondary_emails')
        )
        db.session.add(new_contact)
        db.session.commit()
        return jsonify({'message': 'Contact created successfully', 'id': new_contact.id}), 201

    query = Contact.query
    if 'company_account_number' in request.args:
        query = query.filter_by(company_account_number=request.args['company_account_number'])
    if 'email' in request.args:
        query = query.filter_by(email=request.args['email'])

    contacts = query.all()
    return jsonify([{'id': c.id, 'name': c.name, 'email': c.email, 'active': c.active} for c in contacts])


@app.route('/api/contacts/<int:contact_id>', methods=['PUT'])
@token_required(permission_level=['admin', 'technician'])
def api_contact_details(current_user, contact_id):
    contact = db.session.get(Contact, contact_id)
    if not contact:
        return jsonify({"error": "Contact not found"}), 404
    data = request.get_json()
    if 'name' in data: contact.name = data['name']
    if 'email' in data: contact.email = data['email']
    if 'company_account_number' in data: contact.company_account_number = data['company_account_number']
    if 'title' in data: contact.title = data['title']
    if 'employment_type' in data: contact.employment_type = data['employment_type']
    if 'active' in data: contact.active = data['active']
    if 'mobile_phone_number' in data: contact.mobile_phone_number = data['mobile_phone_number']
    if 'work_phone_number' in data: contact.work_phone_number = data['work_phone_number']
    if 'secondary_emails' in data: contact.secondary_emails = data['secondary_emails']
    db.session.commit()
    return jsonify({'message': 'Contact updated successfully'})

@app.route('/api/users', methods=['GET'])
@token_required(permission_level=['admin'])
def get_users(current_user):
    users = User.query.all()
    return jsonify([{'id': u.id, 'username': u.username, 'email': u.email, 'company_account_number': u.company_account_number, 'permission_level': u.permission_level} for u in users])

@app.route('/api/users/<int:user_id>', methods=['GET'])
@token_required(permission_level=['admin'])
def get_user(current_user, user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({'id': user.id, 'username': user.username, 'email': user.email, 'company_account_number': user.company_account_number, 'permission_level': user.permission_level})

@app.route('/api/companies/<string:account_number>/users', methods=['GET'])
@token_required(permission_level=['admin', 'technician', 'client'])
def get_users_for_company(current_user, account_number):
    if current_user.permission_level == 'client' and current_user.company_account_number != account_number:
        return jsonify({"error": "Access denied"}), 403
    company = db.session.get(Company, account_number)
    if not company:
        return jsonify({"error": "Company not found"}), 404
    users = company.users
    return jsonify([{'id': u.id, 'username': u.username, 'email': u.email, 'permission_level': u.permission_level} for u in users])


def schedule_jobs():
    from scheduler import run_job
    with app.app_context():
        # Schedule the Freshservice job to run first
        freshservice_job = SchedulerJob.query.filter_by(script_path='pull_freshservice.py', enabled=True).first()
        if freshservice_job:
            scheduler.add_job(
                run_job,
                'interval',
                minutes=freshservice_job.interval_minutes,
                args=[freshservice_job.id, freshservice_job.script_path],
                id=str(freshservice_job.id),
                replace_existing=True,
                next_run_time=datetime.now() + timedelta(seconds=10)
            )

        # Schedule the Datto job to run 5 minutes after the Freshservice job
        datto_job = SchedulerJob.query.filter_by(script_path='pull_datto.py', enabled=True).first()
        if datto_job:
            scheduler.add_job(
                run_job,
                'interval',
                minutes=datto_job.interval_minutes,
                args=[datto_job.id, datto_job.script_path],
                id=str(datto_job.id),
                replace_existing=True,
                next_run_time=datetime.now() + timedelta(minutes=1)
            )

        # Schedule other jobs
        other_jobs = SchedulerJob.query.filter(
            SchedulerJob.script_path != 'pull_freshservice.py',
            SchedulerJob.script_path != 'pull_datto.py',
            SchedulerJob.enabled == True
        ).all()
        for job in other_jobs:
            scheduler.add_job(
                run_job,
                'interval',
                minutes=job.interval_minutes,
                args=[job.id, job.script_path],
                id=str(job.id),
                replace_existing=True,
                next_run_time=datetime.now() + timedelta(seconds=10)
            )

if __name__ == '__main__':
    # The condition `not app.debug` is True in the parent reloader process,
    # but the `WERKZEUG_RUN_MAIN` env var is only 'true' in the child process.
    # This ensures the scheduler only starts once when in debug mode.
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        with app.app_context():
            db.create_all()
            if not SchedulerJob.query.first():
                default_jobs = [
                    SchedulerJob(job_name='Sync Freshservice Data', script_path='pull_freshservice.py', interval_minutes=1440),
                    SchedulerJob(job_name='Sync Datto RMM Assets', script_path='pull_datto.py', interval_minutes=1440),
                    SchedulerJob(job_name='Assign Missing Freshservice Account Numbers', script_path='set_account_numbers.py', interval_minutes=1440, enabled=False),
                    SchedulerJob(job_name='Push Account Numbers to Datto RMM', script_path='push_account_nums_to_datto.py', interval_minutes=1440, enabled=False)
                ]
                db.session.bulk_save_objects(default_jobs)
                db.session.commit()

        schedule_jobs()
        if not scheduler.running:
            scheduler.start()
            print("Scheduler started.")

    # Check for SSL certificates and run with HTTPS for local development
    cert_path = os.path.join('certs', 'cert.pem')
    key_path = os.path.join('certs', 'key.pem')

    if os.path.exists(cert_path) and os.path.exists(key_path):
        print("Starting Flask server with HTTPS on 0.0.0.0:5000...")
        app.run(host='0.0.0.0', ssl_context=(cert_path, key_path))
    else:
        print("\n--- WARNING ---")
        print("SSL certificates not found. The server will run on standard HTTP on 0.0.0.0:5000.")
        print("For a secure local connection, please run 'python gen_certs.py' first.")
        print("---------------\n")
        app.run(host='0.0.0.0')
