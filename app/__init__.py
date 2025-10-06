from flask import Flask
import json
import os

app = Flask(__name__, instance_relative_config=True)

# --- Explicitly load all required configuration from environment variables ---
app.config['CORE_SERVICE_URL'] = os.environ.get('CORE_SERVICE_URL')
app.config['SERVICE_NAME'] = os.environ.get('SERVICE_NAME', 'codex')

if not app.config['CORE_SERVICE_URL']:
    raise ValueError("CORE_SERVICE_URL must be set in the .flaskenv file.")

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

# Apply middleware to handle URL prefix when behind Nexus proxy
from app.middleware import PrefixMiddleware
app.wsgi_app = PrefixMiddleware(app.wsgi_app, prefix=f'/{app.config["SERVICE_NAME"]}')

# Register blueprints
from routes.companies import companies_bp
from routes.contacts import contacts_bp
from routes.assets import assets_bp
from routes.admin import admin_bp

app.register_blueprint(companies_bp)
app.register_blueprint(contacts_bp)
app.register_blueprint(assets_bp)
app.register_blueprint(admin_bp)

# Initialize Helm logger for centralized logging
app.config["SERVICE_NAME"] = os.environ.get("SERVICE_NAME", "codex")
app.config["HELM_SERVICE_URL"] = os.environ.get("HELM_SERVICE_URL", "http://localhost:5004")

from app.helm_logger import init_helm_logger
helm_logger = init_helm_logger(
    app.config["SERVICE_NAME"],
    app.config["HELM_SERVICE_URL"]
)

from app import routes

# Log service startup
helm_logger.info(f"{app.config["SERVICE_NAME"]} service started")
