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

    # Primary key
    account_number = db.Column(db.String(50), primary_key=True)

    # Core Freshservice fields (from top-level)
    freshservice_id = db.Column(BigInteger, unique=True, nullable=False)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.String(100))
    updated_at = db.Column(db.String(100))

    # Company head/prime user (from top-level)
    head_user_id = db.Column(BigInteger)
    head_name = db.Column(db.String(150))
    prime_user_id = db.Column(BigInteger)
    prime_user_name = db.Column(db.String(150))

    # Domains (JSON array stored as string)
    domains = db.Column(db.Text)  # JSON array like ["domain1.com", "domain2.com"]

    # Workspace
    workspace_id = db.Column(db.Integer)

    # Custom fields from Freshservice
    plan_selected = db.Column(db.String(100))
    managed_users = db.Column(db.String(100))
    managed_devices = db.Column(db.String(100))
    managed_network = db.Column(db.String(100))
    contract_term = db.Column(db.String(50))  # Contract term length
    contract_start_date = db.Column(db.String(100))
    profit_or_non_profit = db.Column(db.String(50))
    company_main_number = db.Column(db.String(50))
    address = db.Column(db.Text)  # Full address
    company_start_date = db.Column(db.String(100))

    # Additional fields for compatibility
    billing_plan = db.Column(db.String(100))  # Alias for plan_selected
    contract_term_length = db.Column(db.String(50))  # Alias for contract_term
    support_level = db.Column(db.String(100))  # Support tier
    phone_system = db.Column(db.String(100))
    email_system = db.Column(db.String(100))
    datto_portal_url = db.Column(db.String(255))

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

    # Primary key
    id = db.Column(db.Integer, primary_key=True)  # Freshservice requester ID

    # Core Freshservice fields
    freshservice_id = db.Column(BigInteger, unique=True, nullable=False)
    first_name = db.Column(db.String(150))
    last_name = db.Column(db.String(150))
    name = db.Column(db.String(150), nullable=False)  # Computed: first_name + last_name
    primary_email = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)  # Alias for primary_email

    # Status fields
    active = db.Column(db.Boolean, default=True)
    is_agent = db.Column(db.Boolean, default=False)
    vip_user = db.Column(db.Boolean, default=False)
    has_logged_in = db.Column(db.Boolean, default=False)

    # Contact information
    mobile_phone_number = db.Column(db.String(50))
    work_phone_number = db.Column(db.String(50))
    address = db.Column(db.Text)
    secondary_emails = db.Column(db.Text)  # JSON array

    # Job/role information
    job_title = db.Column(db.String(150))
    title = db.Column(db.String(150))  # Alias for job_title
    employment_type = db.Column(db.String(100), default='Full Time')  # Not from FS, local field
    department_ids = db.Column(db.Text)  # JSON array of department IDs
    department_names = db.Column(db.Text)  # Comma-separated department names

    # Manager and location
    reporting_manager_id = db.Column(BigInteger)
    location_id = db.Column(BigInteger)
    location_name = db.Column(db.String(150))

    # Preferences
    language = db.Column(db.String(10), default='en')
    time_zone = db.Column(db.String(100))
    time_format = db.Column(db.String(10))  # '12h' or '24h'

    # Permissions
    can_see_all_tickets_from_associated_departments = db.Column(db.Boolean, default=False)
    can_see_all_changes_from_associated_departments = db.Column(db.Boolean, default=False)

    # Metadata
    created_at = db.Column(db.String(100))
    updated_at = db.Column(db.String(100))
    external_id = db.Column(db.String(100))
    background_information = db.Column(db.Text)
    work_schedule_id = db.Column(BigInteger)

    # Custom fields
    user_number = db.Column(db.String(50))

    # Relationships
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

class SyncJob(db.Model):
    __tablename__ = 'sync_jobs'
    id = db.Column(db.String(50), primary_key=True)  # UUID
    script = db.Column(db.String(50), nullable=False)  # 'freshservice', 'datto', 'tickets'
    status = db.Column(db.String(20), nullable=False)  # 'running', 'completed', 'failed'
    started_at = db.Column(db.String(50), nullable=False)  # ISO timestamp
    completed_at = db.Column(db.String(50))  # ISO timestamp
    output = db.Column(db.Text)  # Last 1000 chars of stdout
    error = db.Column(db.Text)  # Error message if failed
    success = db.Column(db.Boolean)

class BillingPlan(db.Model):
    __tablename__ = 'billing_plans'
    id = db.Column(db.Integer, primary_key=True)
    plan_name = db.Column(db.String(100), nullable=False)
    term_length = db.Column(db.String(50), nullable=False)  # 'Month to Month', '1-Year', '2-Year', '3-Year'
    per_user_cost = db.Column(db.Numeric(10, 2), default=0.0)
    per_workstation_cost = db.Column(db.Numeric(10, 2), default=0.0)
    per_server_cost = db.Column(db.Numeric(10, 2), default=0.0)
    per_vm_cost = db.Column(db.Numeric(10, 2), default=0.0)
    per_switch_cost = db.Column(db.Numeric(10, 2), default=0.0)
    per_firewall_cost = db.Column(db.Numeric(10, 2), default=0.0)
    per_hour_ticket_cost = db.Column(db.Numeric(10, 2), default=0.0)
    backup_base_fee_workstation = db.Column(db.Numeric(10, 2), default=0.0)
    backup_base_fee_server = db.Column(db.Numeric(10, 2), default=0.0)
    backup_cost_per_gb_workstation = db.Column(db.Numeric(10, 4), default=0.0)
    backup_cost_per_gb_server = db.Column(db.Numeric(10, 4), default=0.0)
    support_level = db.Column(db.String(100), default='Billed Hourly')  # 'Unlimited', 'Billed Hourly', etc.
    antivirus = db.Column(db.String(100), default='Not Included')
    soc = db.Column(db.String(100), default='Not Included')
    password_manager = db.Column(db.String(100), default='Not Included')
    sat = db.Column(db.String(100), default='Not Included')
    email_security = db.Column(db.String(100), default='Not Included')
    network_management = db.Column(db.String(100), default='Not Included')

    __table_args__ = (db.UniqueConstraint('plan_name', 'term_length', name='unique_plan_term'),)

class FeatureOption(db.Model):
    __tablename__ = 'feature_options'
    id = db.Column(db.Integer, primary_key=True)
    feature_category = db.Column(db.String(100), nullable=False)  # 'Antivirus', 'Email', 'Phone', etc.
    option_value = db.Column(db.String(100), nullable=False)  # 'SentinelOne', 'Microsoft 365', etc.

    __table_args__ = (db.UniqueConstraint('feature_category', 'option_value', name='unique_feature_option'),)

class Agent(db.Model):
    """
    Agents are system users from Keycloak with additional settings.
    These are internal users (technicians, admins, etc.) not Freshservice contacts.
    """
    __tablename__ = 'agents'

    # Primary key - Keycloak user ID
    keycloak_id = db.Column(db.String(100), primary_key=True)

    # User info from Keycloak
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    first_name = db.Column(db.String(150))
    last_name = db.Column(db.String(150))

    # Status
    enabled = db.Column(db.Boolean, default=True)

    # User settings - stored in Codex, not Keycloak
    theme_preference = db.Column(db.String(20), default='light')  # 'light' or 'dark'

    # Metadata
    created_at = db.Column(db.String(100))  # ISO timestamp
    updated_at = db.Column(db.String(100))  # ISO timestamp
    last_synced_at = db.Column(db.String(100))  # Last time synced from Keycloak

    def to_dict(self):
        """Convert agent to dictionary for API responses"""
        return {
            'keycloak_id': self.keycloak_id,
            'username': self.username,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'enabled': self.enabled,
            'theme_preference': self.theme_preference,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'last_synced_at': self.last_synced_at
        }
