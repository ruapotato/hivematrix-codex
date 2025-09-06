import os
import configparser
import time
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from datetime import datetime, timedelta

# Import db object and models from extensions
from extensions import db, scheduler

# Import models
from models import User, Company, Asset, Contact, SchedulerJob

# Import blueprints
from routes.companies import companies_bp
from routes.contacts import contacts_bp
from routes.assets import assets_bp
from routes.users import users_bp
from routes.settings import settings_bp

# Import decorators
from decorators import admin_required, api_key_required

# --- App Initialization ---
app = Flask(__name__, instance_relative_config=True)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_secure_random_secret_key')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(app.instance_path, 'nexus_brainhair.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Ensure the instance folder exists
try:
    os.makedirs(app.instance_path)
except OSError:
    pass

# Initialize extensions
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- Load Configuration ---
config = configparser.ConfigParser()
config_path = os.path.join(app.instance_path, 'nexus.conf')
config.read(config_path)
app.config['NEXUS_CONFIG'] = config

# Register blueprints
app.register_blueprint(companies_bp)
app.register_blueprint(contacts_bp)
app.register_blueprint(assets_bp)
app.register_blueprint(users_bp)
app.register_blueprint(settings_bp)


# --- User Loader for Flask-Login ---
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# --- Web Interface Routes ---
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

# --- API Routes ---
@app.route('/api/companies', methods=['GET', 'POST'])
@api_key_required(permission_level=['admin', 'user'])
def api_companies():
    if request.method == 'POST':
        data = request.get_json()
        if not data or 'name' not in data or 'account_number' not in data:
            return jsonify({"error": "Missing name or account_number"}), 400

        existing_company = Company.query.filter_by(account_number=data['account_number']).first()
        if existing_company:
            return jsonify({"error": "Company with this account number already exists"}), 409

        new_company = Company(
            name=data['name'],
            account_number=data['account_number'],
            datto_site_uid=data.get('datto_site_uid'),
            freshservice_id=data.get('freshservice_id')
        )
        db.session.add(new_company)
        db.session.commit()
        return jsonify({'message': 'Company created successfully', 'id': new_company.id}), 201

    query = Company.query
    if 'datto_site_uid' in request.args:
        query = query.filter_by(datto_site_uid=request.args['datto_site_uid'])
    if 'freshservice_id' in request.args:
        query = query.filter_by(freshservice_id=request.args['freshservice_id'])
    if 'account_number' in request.args:
        query = query.filter_by(account_number=request.args['account_number'])

    companies = query.all()
    return jsonify([{
        'id': c.id, 'name': c.name, 'location': c.location,
        'primary_contact_name': c.primary_contact_name,
        'primary_contact_email': c.primary_contact_email,
        'primary_contact_phone': c.primary_contact_phone,
        'account_number': c.account_number,
        'freshservice_id': c.freshservice_id,
        'datto_site_uid': c.datto_site_uid
    } for c in companies])

@app.route('/api/companies/<int:company_id>', methods=['GET', 'PUT'])
@api_key_required(permission_level=['admin', 'user'])
def api_company_details(company_id):
    company = db.session.get(Company, company_id)
    if not company:
        return jsonify({"error": "Company not found"}), 404

    if request.method == 'PUT':
        data = request.get_json()
        company.name = data.get('name', company.name)
        company.datto_site_uid = data.get('datto_site_uid', company.datto_site_uid)
        company.freshservice_id = data.get('freshservice_id', company.freshservice_id)
        company.account_number = data.get('account_number', company.account_number)
        db.session.commit()
        return jsonify({'message': 'Company updated successfully'})

    return jsonify({
        'id': company.id, 'name': company.name, 'location': company.location,
        'primary_contact_name': company.primary_contact_name,
        'primary_contact_email': company.primary_contact_email,
        'primary_contact_phone': company.primary_contact_phone,
        'account_number': company.account_number,
        'freshservice_id': company.freshservice_id,
        'datto_site_uid': company.datto_site_uid
    })

@app.route('/api/assets', methods=['GET', 'POST'])
@api_key_required(permission_level=['admin', 'user'])
def api_assets():
    if request.method == 'POST':
        data = request.get_json()
        if not data or 'hostname' not in data or 'company_id' not in data:
            return jsonify({"error": "Missing hostname or company_id"}), 400
        new_asset = Asset(
            hostname=data['hostname'],
            company_id=data['company_id'],
            device_type=data.get('device_type'),
            operating_system=data.get('operating_system'),
            last_logged_in_user=data.get('last_logged_in_user')
        )
        db.session.add(new_asset)
        db.session.commit()
        return jsonify({'message': 'Asset created successfully', 'id': new_asset.id}), 201

    query = Asset.query
    if 'hostname' in request.args and 'company_id' in request.args:
        query = query.filter_by(hostname=request.args['hostname'], company_id=request.args['company_id'])

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
    asset.company_id = data.get('company_id', asset.company_id)
    asset.device_type = data.get('device_type', asset.device_type)
    asset.operating_system = data.get('operating_system', asset.operating_system)
    asset.last_logged_in_user = data.get('last_logged_in_user', asset.last_logged_in_user)
    db.session.commit()
    return jsonify({'message': 'Asset updated successfully'})

@app.route('/api/contacts', methods=['GET', 'POST'])
@api_key_required(permission_level=['admin', 'user'])
def api_contacts():
    if request.method == 'POST':
        data = request.get_json()
        if not data or 'name' not in data or 'email' not in data or 'company_id' not in data:
            return jsonify({"error": "Missing name, email, or company_id"}), 400
        new_contact = Contact(
            name=data['name'],
            email=data['email'],
            company_id=data['company_id']
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
    contact.company_id = data.get('company_id', contact.company_id)
    db.session.commit()
    return jsonify({'message': 'Contact updated successfully'})

@app.route('/api/users', methods=['GET'])
@api_key_required(permission_level=['admin'])
def get_users():
    users = User.query.all()
    return jsonify([{'id': u.id, 'username': u.username, 'email': u.email, 'company_id': u.company_id, 'permission_level': u.permission_level} for u in users])

@app.route('/api/users/<int:user_id>', methods=['GET'])
@api_key_required(permission_level=['admin'])
def get_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({'id': user.id, 'username': user.username, 'email': user.email, 'company_id': user.company_id, 'permission_level': user.permission_level})

@app.route('/api/companies/<int:company_id>/users', methods=['GET'])
@api_key_required(permission_level=['admin', 'user'])
def get_users_for_company(company_id):
    company = db.session.get(Company, company_id)
    if not company:
        return jsonify({"error": "Company not found"}), 404
    users = company.users
    return jsonify([{'id': u.id, 'username': u.username, 'email': u.email, 'permission_level': u.permission_level} for u in users])


# --- Scheduler Initialization ---
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

    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        schedule_jobs()
        if not scheduler.running:
            scheduler.start()
            print("Scheduler started.")

    app.run(debug=True)
