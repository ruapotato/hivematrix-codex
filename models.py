from extensions import db
from sqlalchemy import BigInteger

# Association table for contacts and companies
contact_company_link = db.Table('contact_company_link',
    db.Column('contact_id', db.Integer, db.ForeignKey('contacts.id'), primary_key=True),
    db.Column('company_account_number', db.String(50), db.ForeignKey('companies.account_number'), primary_key=True)
)

# Association table for assets and contacts
asset_contact_link = db.Table('asset_contact_link',
    db.Column('asset_id', db.Integer, db.ForeignKey('assets.id'), primary_key=True),
    db.Column('contact_id', db.Integer, db.ForeignKey('contacts.id'), primary_key=True)
)

class Company(db.Model):
    __tablename__ = 'companies'
    account_number = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    freshservice_id = db.Column(BigInteger, unique=True)
    description = db.Column(db.Text)
    plan_selected = db.Column(db.String(100))
    profit_or_non_profit = db.Column(db.String(50))
    company_main_number = db.Column(db.String(50))
    company_start_date = db.Column(db.String(100))
    head_name = db.Column(db.String(150))
    primary_contact_name = db.Column(db.String(150))
    domains = db.Column(db.String(255))
    phone_system = db.Column(db.String(100))
    email_system = db.Column(db.String(100))

    assets = db.relationship('Asset', back_populates='company', lazy=True, cascade="all, delete-orphan")
    contacts = db.relationship('Contact', secondary=contact_company_link, back_populates='companies')
    feature_overrides = db.relationship('CompanyFeatureOverride', back_populates='company', lazy='dynamic', cascade="all, delete-orphan")
    locations = db.relationship('Location', back_populates='company', lazy=True, cascade="all, delete-orphan")
    datto_site_links = db.relationship('DattoSiteLink', back_populates='company', lazy=True, cascade="all, delete-orphan")

class Asset(db.Model):
    __tablename__ = 'assets'
    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column(db.String(150), nullable=False)
    company_account_number = db.Column(db.String(50), db.ForeignKey('companies.account_number'), nullable=False)
    hardware_type = db.Column(db.String(100))
    operating_system = db.Column(db.String(100))
    last_logged_in_user = db.Column(db.String(150))
    datto_site_name = db.Column(db.String(150))
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
    device_type = db.Column(db.String(50))
    portal_url = db.Column(db.String(255))
    web_remote_url = db.Column(db.String(255))

    company = db.relationship('Company', back_populates='assets')
    contacts = db.relationship('Contact', secondary=asset_contact_link, back_populates='assets')

class Contact(db.Model):
    __tablename__ = 'contacts'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    title = db.Column(db.String(150))
    employment_type = db.Column(db.String(100), nullable=False, default='Full Time')
    active = db.Column(db.Boolean, default=True)
    mobile_phone_number = db.Column(db.String(50))
    work_phone_number = db.Column(db.String(50))
    secondary_emails = db.Column(db.String(255))

    companies = db.relationship('Company', secondary=contact_company_link, back_populates='contacts')
    assets = db.relationship('Asset', secondary=asset_contact_link, back_populates='contacts')

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

class DattoSiteLink(db.Model):
    __tablename__ = 'datto_site_links'
    id = db.Column(db.Integer, primary_key=True)
    company_account_number = db.Column(db.String(50), db.ForeignKey('companies.account_number'), nullable=False)
    datto_site_uid = db.Column(db.String(100), unique=True, nullable=False)

    company = db.relationship('Company', back_populates='datto_site_links')

class TicketDetail(db.Model):
    __tablename__ = 'ticket_details'
    ticket_id = db.Column(BigInteger, primary_key=True)
    company_account_number = db.Column(db.String(50), db.ForeignKey('companies.account_number'), nullable=False)
    ticket_number = db.Column(db.String(50))
    subject = db.Column(db.Text)
    description = db.Column(db.Text)  # Initial ticket description
    description_text = db.Column(db.Text)  # Plain text version
    status = db.Column(db.String(50))
    priority = db.Column(db.String(50))
    requester_email = db.Column(db.String(150))
    requester_name = db.Column(db.String(150))
    created_at = db.Column(db.String(50))
    last_updated_at = db.Column(db.String(50))
    closed_at = db.Column(db.String(50))
    total_hours_spent = db.Column(db.Float, default=0.0)

    # Conversation history stored as JSON
    conversations = db.Column(db.Text)  # JSON array of conversation entries
    notes = db.Column(db.Text)  # JSON array of internal notes
