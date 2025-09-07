# ruapotato/hivematrix-nexus/hivematrix-nexus-main/models.py
from datetime import datetime
from extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import secrets

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    permission_level = db.Column(db.String(50), nullable=False, default='client')
    company_account_number = db.Column(db.String(50), db.ForeignKey('companies.account_number'))
    api_key = db.Column(db.String(64), unique=True, nullable=False, default=lambda: secrets.token_hex(32))

    company = db.relationship('Company', back_populates='users')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def regenerate_api_key(self):
        self.api_key = secrets.token_hex(32)

class Company(db.Model):
    __tablename__ = 'companies'
    account_number = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    freshservice_id = db.Column(db.Integer, unique=True)
    datto_site_uid = db.Column(db.String(100), unique=True)
    description = db.Column(db.Text)
    plan_selected = db.Column(db.String(100))
    profit_or_non_profit = db.Column(db.String(50))
    company_main_number = db.Column(db.String(50))
    company_start_date = db.Column(db.String(100))
    head_name = db.Column(db.String(150))
    primary_contact_name = db.Column(db.String(150))
    domains = db.Column(db.String(255))
    email_system = db.Column(db.String(100), default='No Business Email')
    phone_system = db.Column(db.String(100), default='No Business Phone')


    users = db.relationship('User', back_populates='company', lazy=True)
    assets = db.relationship('Asset', back_populates='company', lazy=True)
    contacts = db.relationship('Contact', back_populates='company', lazy=True)
    feature_overrides = db.relationship('CompanyFeatureOverride', back_populates='company', lazy='dynamic', cascade="all, delete-orphan")
    locations = db.relationship('Location', back_populates='company', lazy=True, cascade="all, delete-orphan")

asset_contact_link = db.Table('asset_contact_link',
    db.Column('asset_id', db.Integer, db.ForeignKey('assets.id'), primary_key=True),
    db.Column('contact_id', db.Integer, db.ForeignKey('contacts.id'), primary_key=True)
)

class Asset(db.Model):
    __tablename__ = 'assets'
    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column(db.String(150), nullable=False)
    company_account_number = db.Column(db.String(50), db.ForeignKey('companies.account_number'), nullable=False)
    hardware_type = db.Column(db.String(100)) # Renamed from device_type
    operating_system = db.Column(db.String(100))
    last_logged_in_user = db.Column(db.String(150))

    # New columns from Datto RMM
    antivirus_product = db.Column(db.String(100))
    description = db.Column(db.Text)
    ext_ip_address = db.Column(db.String(50))
    int_ip_address = db.Column(db.String(50))
    domain = db.Column(db.String(100))
    last_audit_date = db.Column(db.String(50))
    last_reboot = db.Column(db.String(50))
    last_seen = db.Column(db.String(50))
    online = db.Column(db.Boolean)
    patch_status = db.Column(db.String(50))
    backup_usage_tb = db.Column(db.String(50))
    enabled_administrators = db.Column(db.Text)
    device_type = db.Column(db.String(50)) # New field from udf7
    portal_url = db.Column(db.String(255))
    web_remote_url = db.Column(db.String(255))

    company = db.relationship('Company', back_populates='assets')
    contacts = db.relationship('Contact', secondary='asset_contact_link', back_populates='assets')

class Contact(db.Model):
    __tablename__ = 'contacts'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    company_account_number = db.Column(db.String(50), db.ForeignKey('companies.account_number'), nullable=False)
    title = db.Column(db.String(150))
    employment_type = db.Column(db.String(100), nullable=False, default='Full Time')

    # New columns from Freshservice
    active = db.Column(db.Boolean)
    mobile_phone_number = db.Column(db.String(50))
    work_phone_number = db.Column(db.String(50))
    secondary_emails = db.Column(db.String(255))

    company = db.relationship('Company', back_populates='contacts')
    assets = db.relationship('Asset', secondary='asset_contact_link', back_populates='contacts')

class SchedulerJob(db.Model):
    __tablename__ = 'scheduler_jobs'
    id = db.Column(db.Integer, primary_key=True)
    job_name = db.Column(db.String(150), unique=True, nullable=False)
    script_path = db.Column(db.String(255), nullable=False)
    interval_minutes = db.Column(db.Integer, nullable=False)
    enabled = db.Column(db.Boolean, default=True)
    last_run = db.Column(db.String(100))
    last_status = db.Column(db.String(50))
    last_run_log = db.Column(db.Text)

class CompanyFeatureOverride(db.Model):
    __tablename__ = 'company_feature_overrides'
    id = db.Column(db.Integer, primary_key=True)
    company_account_number = db.Column(db.String(50), db.ForeignKey('companies.account_number'), nullable=False)
    feature_key = db.Column(db.String(100), nullable=False)
    value = db.Column(db.String(100), nullable=False)
    override_enabled = db.Column(db.Boolean, nullable=False, default=True)

    company = db.relationship('Company', back_populates='feature_overrides')

class Location(db.Model):
    __tablename__ = 'locations'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    address = db.Column(db.String(255))
    phone_number = db.Column(db.String(50))
    company_account_number = db.Column(db.String(50), db.ForeignKey('companies.account_number'), nullable=False)

    company = db.relationship('Company', back_populates='locations')
