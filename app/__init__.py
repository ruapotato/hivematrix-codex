from flask import Flask
import json
import os
import secrets

app = Flask(__name__, instance_relative_config=True)

# Set secret key for sessions (generate a random one if not set)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or secrets.token_hex(32)

# --- Explicitly load all required configuration from environment variables ---
# Provide sensible defaults for init_db.py, will be overridden by Helm's .flaskenv
app.config['CORE_SERVICE_URL'] = os.environ.get('CORE_SERVICE_URL', 'http://localhost:5000')
app.config['SERVICE_NAME'] = os.environ.get('SERVICE_NAME', 'codex')

# Load database connection from config file
import configparser
try:
    os.makedirs(app.instance_path)
except OSError:
    pass

config_path = os.path.join(app.instance_path, 'codex.conf')
# Use RawConfigParser to avoid interpolation issues with special characters like %
config = configparser.RawConfigParser()
config.read(config_path)
app.config['CODEX_CONFIG'] = config

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = config.get('database', 'connection_string',
    fallback=f"sqlite:///{os.path.join(app.instance_path, 'codex.db')}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Scheduler configuration
app.config['SYNC_FRESHSERVICE_ENABLED'] = config.getboolean('scheduler', 'sync_freshservice_enabled', fallback=True)
app.config['SYNC_DATTO_ENABLED'] = config.getboolean('scheduler', 'sync_datto_enabled', fallback=True)
app.config['SYNC_TICKETS_ENABLED'] = config.getboolean('scheduler', 'sync_tickets_enabled', fallback=False)
app.config['SYNC_FRESHSERVICE_SCHEDULE'] = config.get('scheduler', 'sync_freshservice_schedule', fallback='daily')
app.config['SYNC_DATTO_SCHEDULE'] = config.get('scheduler', 'sync_datto_schedule', fallback='daily')
app.config['SYNC_TICKETS_SCHEDULE'] = config.get('scheduler', 'sync_tickets_schedule', fallback='hourly')
app.config['SYNC_RUN_ON_STARTUP'] = config.getboolean('scheduler', 'sync_run_on_startup', fallback=False)

# Load services configuration for service-to-service calls
try:
    with open('services.json') as f:
        services_config = json.load(f)
        app.config['SERVICES'] = services_config
except FileNotFoundError:
    print("WARNING: services.json not found. Service-to-service calls will not work.")
    app.config['SERVICES'] = {}

from extensions import db
db.init_app(app)

# Apply ProxyFix to handle X-Forwarded headers from Nexus proxy
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=1,      # Trust X-Forwarded-For
    x_proto=1,    # Trust X-Forwarded-Proto (http/https)
    x_host=1,     # Trust X-Forwarded-Host
    x_prefix=1    # Trust X-Forwarded-Prefix (sets SCRIPT_NAME for url_for)
)

# Register blueprints
from routes.companies import companies_bp
from routes.contacts import contacts_bp
from routes.assets import assets_bp
from routes.admin import admin_bp
from routes.billing_plans import billing_plans_bp

app.register_blueprint(companies_bp)
app.register_blueprint(contacts_bp)
app.register_blueprint(assets_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(billing_plans_bp)

# Initialize Helm logger for centralized logging
app.config["SERVICE_NAME"] = os.environ.get("SERVICE_NAME", "codex")
app.config["HELM_SERVICE_URL"] = os.environ.get("HELM_SERVICE_URL", "http://localhost:5004")

from app.helm_logger import init_helm_logger
helm_logger = init_helm_logger(
    app.config["SERVICE_NAME"],
    app.config["HELM_SERVICE_URL"]
)

# Keycloak configuration for agent management
app.config['KEYCLOAK_SERVER_URL'] = os.environ.get('KEYCLOAK_SERVER_URL', 'http://localhost:8080')
app.config['KEYCLOAK_REALM'] = os.environ.get('KEYCLOAK_REALM', 'hivematrix')
app.config['KEYCLOAK_ADMIN_USER'] = os.environ.get('KEYCLOAK_ADMIN_USER', 'admin')
app.config['KEYCLOAK_ADMIN_PASS'] = os.environ.get('KEYCLOAK_ADMIN_PASS', 'admin')

from app import routes
from app import agent_routes  # Agent management and Keycloak sync routes

# Initialize background scheduler for auto-sync (optional)
try:
    from app.scheduler import init_scheduler
    init_scheduler(app)
    helm_logger.info("Background sync scheduler initialized")
except ImportError as e:
    helm_logger.warning(f"Scheduler not available (APScheduler not installed): {e}")
except Exception as e:
    helm_logger.error(f"Failed to initialize scheduler: {e}")

# Log service startup
service_name = app.config['SERVICE_NAME']
helm_logger.info(f"{service_name} service started")
