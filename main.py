# ruapotato/hivematrix-nexus/hivematrix-nexus-main/main.py

import os
import configparser
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from datetime import datetime, timedelta

from extensions import db, scheduler
from models import User, Company, Asset, Contact, SchedulerJob
from routes.companies import companies_bp
from routes.contacts import contacts_bp
from routes.assets import assets_bp
from routes.users import users_bp
from routes.settings import settings_bp
from decorators import admin_required, api_key_required

app = Flask(__name__, instance_relative_config=True)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_secure_random_secret_key')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(app.instance_path, 'nexus_brainhair.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/companies', methods=['GET', 'POST'])
@api_key_required(permission_level=['admin', 'user'])
def api_companies():
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
                datto_site_uid=data.get('datto_site_uid'),
                freshservice_id=data.get('freshservice_id')
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
        'datto_site_uid': c.datto_site_uid,
        'description': c.description, 'plan_selected': c.plan_selected,
        'profit_or_non_profit': c.profit_or_non_profit, 'company_main_number': c.company_main_number,
        'address': c.address, 'company_start_date': c.company_start_date,
        'head_name': c.head_name, 'prime_user_name': c.prime_user_name, 'domains': c.domains
    } for c in companies])

@app.route('/api/companies/<string:account_number>', methods=['GET', 'PUT'])
@api_key_required(permission_level=['admin', 'user'])
def api_company_details(account_number):
    company = db.session.get(Company, account_number)
    if not company:
        return jsonify({"error": "Company not found"}), 404

    if request.method == 'PUT':
        data = request.get_json()
        company.name = data.get('name', company.name)
        company.datto_site_uid = data.get('datto_site_uid', company.datto_site_uid)
        company.freshservice_id = data.get('freshservice_id', company.freshservice_id)
        company.description = data.get('description', company.description)
        company.plan_selected = data.get('plan_selected', company.plan_selected)
        company.profit_or_non_profit = data.get('profit_or_non_profit', company.profit_or_non_profit)
        company.company_main_number = data.get('company_main_number', company.company_main_number)
        company.address = data.get('address', company.address)
        company.company_start_date = data.get('company_start_date', company.company_start_date)
        company.head_name = data.get('head_name', company.head_name)
        company.prime_user_name = data.get('prime_user_name', company.prime_user_name)
        company.domains = data.get('domains', company.domains)
        db.session.commit()
        return jsonify({'message': 'Company updated successfully'})

    return jsonify({
        'account_number': company.account_number, 'name': company.name,
        'freshservice_id': company.freshservice_id, 'datto_site_uid': company.datto_site_uid,
        'description': company.description, 'plan_selected': company.plan_selected,
        'profit_or_non_profit': company.profit_or_non_profit, 'company_main_number': company.company_main_number,
        'address': company.address, 'company_start_date': company.company_start_date,
        'head_name': company.head_name, 'prime_user_name': company.prime_user_name, 'domains': company.domains
    })

@app.route('/api/assets', methods=['GET', 'POST'])
@api_key_required(permission_level=['admin', 'user'])
def api_assets():
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
    if 'hostname' in request.args and 'company_account_number' in request.args:
        query = query.filter_by(hostname=request.args['hostname'], company_account_number=request.args['company_account_number'])

    assets = query.all()
    return jsonify([{'id': a.id, 'hostname': a.hostname} for a in assets])


@app.route('/api/assets/<int:asset_id>', methods=['PUT'])
@api_key_required(permission_level=['admin', 'user'])
def api_asset_details(asset_id):
    asset = db.session.get(Asset, asset_id)
    if not asset:
        return jsonify({"error": "Asset not found"}), 404
    data = request.get_json()
    asset.hostname = data.get('hostname', asset.hostname)
    asset.company_account_number = data.get('company_account_number', asset.company_account_number)
    asset.operating_system = data.get('operating_system', asset.operating_system)
    asset.last_logged_in_user = data.get('last_logged_in_user', asset.last_logged_in_user)
    asset.hardware_type = data.get('hardware_type', asset.hardware_type)
    asset.antivirus_product = data.get('antivirus_product', asset.antivirus_product)
    asset.description = data.get('description', asset.description)
    asset.ext_ip_address = data.get('ext_ip_address', asset.ext_ip_address)
    asset.int_ip_address = data.get('int_ip_address', asset.int_ip_address)
    asset.domain = data.get('domain', asset.domain)
    asset.last_audit_date = data.get('last_audit_date', asset.last_audit_date)
    asset.last_reboot = data.get('last_reboot', asset.last_reboot)
    asset.last_seen = data.get('last_seen', asset.last_seen)
    asset.online = data.get('online', asset.online)
    asset.patch_status = data.get('patch_status', asset.patch_status)
    asset.backup_usage_tb = data.get('backup_usage_tb', asset.backup_usage_tb)
    asset.enabled_administrators = data.get('enabled_administrators', asset.enabled_administrators)
    asset.device_type = data.get('device_type', asset.device_type)
    asset.portal_url = data.get('portal_url', asset.portal_url)
    asset.web_remote_url = data.get('web_remote_url', asset.web_remote_url)
    db.session.commit()
    return jsonify({'message': 'Asset updated successfully'})

@app.route('/api/contacts', methods=['GET', 'POST'])
@api_key_required(permission_level=['admin', 'user'])
def api_contacts():
    if request.method == 'POST':
        data = request.get_json()
        if not data or 'name' not in data or 'email' not in data or 'company_account_number' not in data:
            return jsonify({"error": "Missing name, email, or company_account_number"}), 400
        new_contact = Contact(
            name=data['name'],
            email=data['email'],
            company_account_number=data['company_account_number'],
            active=data.get('active'),
            mobile_phone_number=data.get('mobile_phone_number'),
            work_phone_number=data.get('work_phone_number'),
            secondary_emails=','.join(data.get('secondary_emails', []))
        )
        db.session.add(new_contact)
        db.session.commit()
        return jsonify({'message': 'Contact created successfully', 'id': new_contact.id}), 201

    query = Contact.query
    if 'email' in request.args:
        query = query.filter_by(email=request.args['email'])

    contacts = query.all()
    return jsonify([{'id': c.id, 'name': c.name, 'email': c.email} for c in contacts])


@app.route('/api/contacts/<int:contact_id>', methods=['PUT'])
@api_key_required(permission_level=['admin', 'user'])
def api_contact_details(contact_id):
    contact = db.session.get(Contact, contact_id)
    if not contact:
        return jsonify({"error": "Contact not found"}), 404
    data = request.get_json()
    contact.name = data.get('name', contact.name)
    contact.email = data.get('email', contact.email)
    contact.company_account_number = data.get('company_account_number', contact.company_account_number)
    contact.active = data.get('active', contact.active)
    contact.mobile_phone_number = data.get('mobile_phone_number', contact.mobile_phone_number)
    contact.work_phone_number = data.get('work_phone_number', contact.work_phone_number)
    contact.secondary_emails = ','.join(data.get('secondary_emails', []))
    db.session.commit()
    return jsonify({'message': 'Contact updated successfully'})

@app.route('/api/users', methods=['GET'])
@api_key_required(permission_level=['admin'])
def get_users():
    users = User.query.all()
    return jsonify([{'id': u.id, 'username': u.username, 'email': u.email, 'company_account_number': u.company_account_number, 'permission_level': u.permission_level} for u in users])

@app.route('/api/users/<int:user_id>', methods=['GET'])
@api_key_required(permission_level=['admin'])
def get_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({'id': user.id, 'username': user.username, 'email': user.email, 'company_account_number': user.company_account_number, 'permission_level': user.permission_level})

@app.route('/api/companies/<string:account_number>/users', methods=['GET'])
@api_key_required(permission_level=['admin', 'user'])
def get_users_for_company(account_number):
    company = db.session.get(Company, account_number)
    if not company:
        return jsonify({"error": "Company not found"}), 404
    users = company.users
    return jsonify([{'id': u.id, 'username': u.username, 'email': u.email, 'permission_level': u.permission_level} for u in users])


def schedule_jobs():
    from scheduler import run_job
    with app.app_context():
        jobs = SchedulerJob.query.filter_by(enabled=True).all()
        for job in jobs:
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

    app.run(debug=True)

