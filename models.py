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
    permission_level = db.Column(db.String(50), nullable=False, default='user')
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'))
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
    id = db.Column(db.Integer, primary_key=True)
    account_number = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(150), unique=True, nullable=False)
    location = db.Column(db.String(200))
    primary_contact_name = db.Column(db.String(150))
    primary_contact_email = db.Column(db.String(150))
    primary_contact_phone = db.Column(db.String(50))
    freshservice_id = db.Column(db.Integer, unique=True)
    datto_site_uid = db.Column(db.String(100), unique=True)

    users = db.relationship('User', back_populates='company', lazy=True)
    assets = db.relationship('Asset', back_populates='company', lazy=True)
    contacts = db.relationship('Contact', back_populates='company', lazy=True)

# Link table for the many-to-many relationship between Assets and Contacts
asset_contact_link = db.Table('asset_contact_link',
    db.Column('asset_id', db.Integer, db.ForeignKey('assets.id'), primary_key=True),
    db.Column('contact_id', db.Integer, db.ForeignKey('contacts.id'), primary_key=True)
)

class Asset(db.Model):
    __tablename__ = 'assets'
    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column(db.String(150), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    device_type = db.Column(db.String(50))
    operating_system = db.Column(db.String(100))
    last_logged_in_user = db.Column(db.String(150))

    company = db.relationship('Company', back_populates='assets')
    contacts = db.relationship('Contact', secondary='asset_contact_link', back_populates='assets')

class Contact(db.Model):
    __tablename__ = 'contacts'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)

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
