# HiveMatrix Codex

**The Central Data Platform for HiveMatrix**

Codex is the unified data platform for the HiveMatrix PSA ecosystem. It serves as the single source of truth for all organizational data including companies, contacts, assets, users, tickets, billing plans, and custom data models. Codex provides both web interfaces and REST APIs for data access across all HiveMatrix modules.

## Overview

Codex is a standalone HiveMatrix module that:
- Stores and manages all core data for the HiveMatrix ecosystem
- Syncs data from external systems (Freshservice, Datto RMM)
- Provides REST APIs for other modules to access centralized data
- Offers web UI for viewing and managing all stored information
- Supports extensible data models for custom client requirements
- Manages agent settings and user preferences

**Port:** 5010 (standard)

## Data Models

Codex currently manages these data types:

### Client Data
- **Companies**: Client organizations with billing plans, contracts, and settings
- **Contacts**: People associated with companies (end users, decision makers)
- **Assets**: Hardware devices (workstations, servers, network equipment)
- **Locations**: Physical addresses and sites for companies

### Operations Data
- **Tickets**: Support tickets synced from Freshservice with full conversation history
- **Agents**: Internal users/technicians with preferences and settings
- **Sync Jobs**: Background job tracking for data synchronization

### Billing & Configuration
- **Billing Plans**: Service plans with per-unit pricing (users, devices, backup, etc.)
- **Feature Options**: Available service features (antivirus, email, phone systems)
- **Company Feature Overrides**: Per-company custom pricing and features

### Integration Data
- **Datto Site Links**: Mapping between companies and Datto RMM sites
- **Account Numbers**: Unique identifiers linking systems

## Architecture

Codex follows the HiveMatrix monolithic service pattern:
- **Authentication:** Uses Core service for JWT-based authentication (no local user management)
- **Database:** PostgreSQL (single database for all data models)
- **Styling:** Unstyled HTML using BEM classes, styled by Nexus proxy
- **APIs:** Exposes both HTML views and JSON APIs
- **Extensibility:** New data models can be added to `models.py` as needed

## Project Structure

```
hivematrix-codex/
├── app/
│   ├── __init__.py           # Flask app initialization
│   ├── auth.py               # @token_required decorator
│   ├── routes.py             # Main API routes
│   ├── service_client.py     # Service-to-service helper
│   └── templates/            # HTML templates (BEM styled)
├── routes/
│   ├── admin.py              # Admin settings and sync management
│   ├── agents.py             # Agent/user management routes
│   ├── assets.py             # Asset management routes
│   ├── billing_plans.py      # Billing plan configuration routes
│   ├── companies.py          # Company management routes
│   └── contacts.py           # Contact management routes
├── instance/
│   └── codex.conf            # Configuration (created by init_db.py)
├── extensions.py             # Flask extensions
├── models.py                 # SQLAlchemy models (all data models)
├── init_db.py                # Database initialization script
├── run.py                    # Application entry point
├── pull_datto.py             # Datto RMM sync script
├── pull_freshservice.py      # Freshservice sync script
├── sync_tickets_from_freshservice.py  # Ticket sync script
├── set_account_numbers.py    # Account number management
├── push_account_nums_to_datto.py  # Push account numbers back to Datto
├── init_plans.py             # Initialize billing plans
├── install.sh                # Automated installation script
├── services.json             # Service discovery config
├── requirements.txt          # Python dependencies
└── README.md                 # This file
```

## Setup and Installation

### 1. Prerequisites

- Python 3.8+
- PostgreSQL 12+
- HiveMatrix Core service running on port 5000
- (Optional) Datto RMM and Freshservice accounts for data sync

### 2. Create Virtual Environment

```bash
python3 -m venv pyenv
source pyenv/bin/activate  # On Windows: .\pyenv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set Up PostgreSQL

#### Install PostgreSQL on Ubuntu

```bash
# Update package list
sudo apt update

# Install PostgreSQL and additional components
sudo apt install postgresql postgresql-contrib

# Start and enable PostgreSQL service
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

#### Configure PostgreSQL

```bash
# Switch to postgres user
sudo -i -u postgres

# Access PostgreSQL prompt
psql

# Create database and user
CREATE USER codex_user WITH PASSWORD 'your_secure_password';
CREATE DATABASE codex_db OWNER codex_user;
\q
exit
```

### 5. Initialize Database

Run the interactive database setup:

```bash
python init_db.py
```

This will:
- Prompt for PostgreSQL connection details
- Create all database tables (companies, contacts, assets, tickets, agents, billing plans, etc.)
- Generate a `instance/codex.conf` file with your settings

### 6. Configure External Integrations (Optional)

Edit `instance/codex.conf` and add your API credentials:

```ini
[freshservice]
api_key = YOUR_FRESHSERVICE_API_KEY
domain = your-domain.freshservice.com

[datto]
api_endpoint = https://zinfandel-api.centrastage.net
public_key = YOUR_DATTO_PUBLIC_KEY
secret_key = YOUR_DATTO_SECRET_KEY
```

### 7. Configure Services

Create a `.flaskenv` file:

```
FLASK_APP=run.py
FLASK_ENV=development
CORE_SERVICE_URL='http://localhost:5000'
SERVICE_NAME='codex'
```

Update `services.json` with your service URLs:

```json
{
    "codex": {
        "url": "http://localhost:5010"
    },
    "core": {
        "url": "http://localhost:5000"
    }
}
```

### 8. Run the Service

**Development mode:**
```bash
flask run --port=5010
```

**Production mode (with Waitress):**
```bash
python run.py
```

The service will be available at `http://localhost:5010`.

## Data Synchronization

Codex includes scripts to sync data from external systems:

### Sync from Freshservice

Pulls companies and contacts:

```bash
python pull_freshservice.py
```

This syncs:
- Companies (from Freshservice Departments)
- Contacts (from Freshservice Requesters)
- Company-to-Contact relationships
- Custom fields and metadata

### Sync Tickets from Freshservice

Pulls support tickets with full conversation history:

```bash
python sync_tickets_from_freshservice.py
```

This syncs:
- Ticket details (subject, description, status, priority)
- Full conversation threads
- Time tracking data
- Ticket-to-company relationships

### Sync from Datto RMM

Pulls assets and device information:

```bash
python pull_datto.py
```

This syncs:
- Assets (devices/computers)
- Device details (OS, IP addresses, last seen, online status)
- Links Datto sites to company account numbers
- Hardware inventory

### Account Number Management

Assign account numbers to companies missing them:

```bash
python set_account_numbers.py
```

Push account numbers back to Datto RMM site variables:

```bash
python push_account_nums_to_datto.py
```

### Automation

Set up cron jobs to run sync scripts periodically:

```bash
# Edit crontab
crontab -e

# Add these lines (adjust schedule as needed)
0 2 * * * /path/to/pyenv/bin/python /path/to/hivematrix-codex/pull_freshservice.py
0 3 * * * /path/to/pyenv/bin/python /path/to/hivematrix-codex/pull_datto.py
0 4 * * * /path/to/pyenv/bin/python /path/to/hivematrix-codex/sync_tickets_from_freshservice.py
```

## API Endpoints

All API endpoints require JWT authentication via the `Authorization: Bearer <token>` header.

### Companies

- `GET /api/companies` - List all companies (supports filtering)
- `POST /api/companies` - Create a new company
- `POST /api/companies/bulk` - Bulk create/update companies
- `GET /api/companies/<account_number>` - Get company details
- `PUT /api/companies/<account_number>` - Update company
- `GET /api/companies/<account_number>/assets` - Get company assets
- `GET /api/companies/<account_number>/contacts` - Get company contacts
- `GET /api/companies/<account_number>/users` - Get users for a company
- `GET /api/companies/<account_number>/locations` - Get company locations
- `GET /api/companies/<account_number>/tickets` - Get company tickets

### Contacts

- `GET /api/contacts` - List all contacts
- `POST /api/contacts` - Create a new contact
- `GET /api/contacts/<contact_id>` - Get contact details
- `PUT /api/contacts/<contact_id>` - Update contact
- `DELETE /api/contacts/<contact_id>` - Delete contact

### Assets

- `GET /api/assets` - List all assets (supports filtering)
- `POST /api/assets` - Create a new asset
- `GET /api/assets/<asset_id>` - Get asset details
- `PUT /api/assets/<asset_id>` - Update asset
- `DELETE /api/assets/<asset_id>` - Delete asset

### Tickets

- `GET /api/tickets` - List tickets with filtering (status, company, date range)
- `GET /api/ticket/<ticket_id>` - Get ticket details with full conversation history
- `POST /api/ticket/<ticket_id>/update` - Update ticket information

### Agents

- `GET /api/agents` - List all agents
- `POST /api/agents` - Create agent (requires Keycloak user ID)
- `GET /api/agents/<keycloak_id>` - Get agent details
- `PUT /api/agents/<keycloak_id>` - Update agent settings
- `POST /api/agents/sync` - Sync agents from Keycloak

### Billing Plans

- `GET /api/billing-plans` - List all billing plans
- `POST /api/billing-plans` - Create a new billing plan
- `GET /api/billing-plans/<plan_id>` - Get billing plan details
- `PUT /api/billing-plans/<plan_id>` - Update billing plan

### Feature Options

- `GET /api/feature-options` - List all feature options by category
- `POST /api/feature-options` - Create a new feature option

### Datto Integration

- `GET /api/datto/devices` - List all devices from Datto RMM
- `GET /api/datto/device/<device_id>` - Get device details from Datto RMM

### System

- `GET /health` - Health check endpoint
- `GET /sync/status/<job_id>` - Check status of background sync job
- `GET /sync/last/<script_name>` - Get last successful sync time for a script

## Web Interface

When accessed through the Nexus proxy at `https://your-domain/codex/`, the web interface provides:

- **Dashboard**: Overview with counts for companies, contacts, assets, agents
- **Companies**: Browse, search, and manage company records
- **Contacts**: View and edit contact information
- **Assets**: Device inventory and details
- **Agents**: Manage internal users and their settings
- **Billing Plans**: Configure service plans and pricing
- **Admin Settings**: Sync management, system configuration

## Service-to-Service Communication

Codex can call other HiveMatrix services using the service client:

```python
from app.service_client import call_service

# Call another service's API
response = call_service('brainhair', '/api/knowledge/search?q=example')
data = response.json()
```

The service client automatically:
1. Requests a service token from Core
2. Makes the authenticated request
3. Returns the response

## Extending Codex

### Adding New Data Models

1. Define new model in `models.py`:
```python
class CustomData(db.Model):
    __tablename__ = 'custom_data'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    data = db.Column(db.Text)
```

2. Create routes in new file `routes/custom.py`:
```python
from flask import Blueprint

bp = Blueprint('custom', __name__)

@bp.route('/api/custom')
@token_required
def list_custom():
    # Implementation
    pass
```

3. Register blueprint in `app/__init__.py`

4. Run `python init_db.py` to create tables

### Adding New Sync Integrations

1. Create new sync script (e.g., `pull_system_x.py`)
2. Follow pattern from existing sync scripts
3. Use `SyncJob` model to track progress
4. Add to cron schedule

## Development

### Database Migrations

After modifying `models.py`:

```bash
# Re-run init_db.py and choose to drop/recreate tables
python init_db.py
```

For production, consider using Alembic for migrations.

### Adding New Routes

1. Create a new blueprint in `routes/`
2. Register it in `app/__init__.py`
3. Use `@token_required` decorator for protected routes
4. Use BEM classes for HTML templates (no inline styles)

### Testing API Endpoints

```bash
# Get a token from Core first
curl -X POST http://localhost:5000/api/token \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}'

# Use the token to call Codex APIs
curl -X GET http://localhost:5010/api/companies \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

## Production Deployment

### Using Waitress

The production server uses Waitress (configured in `run.py`):

```bash
python run.py
```

### Using Systemd Service

Create `/etc/systemd/system/codex.service`:

```ini
[Unit]
Description=HiveMatrix Codex Service
After=network.target postgresql.service

[Service]
Type=simple
User=hivematrix
WorkingDirectory=/path/to/hivematrix-codex
Environment="PATH=/path/to/hivematrix-codex/pyenv/bin"
ExecStart=/path/to/hivematrix-codex/pyenv/bin/python run.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable codex
sudo systemctl start codex
```

## Troubleshooting

**Database connection fails:**
- Verify PostgreSQL is running: `sudo systemctl status postgresql`
- Check credentials in `instance/codex.conf`
- Ensure database exists: `psql -l`

**Authentication errors:**
- Ensure Core service is running on port 5000
- Verify `CORE_SERVICE_URL` in `.flaskenv`
- Check that Core's JWKS endpoint is accessible: `curl http://localhost:5000/.well-known/jwks.json`

**Sync scripts fail:**
- Verify API credentials in `instance/codex.conf`
- Check network connectivity to external services
- Review error messages in script output
- Check sync job status: `GET /sync/status/<job_id>`

**Import errors:**
- Ensure virtual environment is activated
- Reinstall dependencies: `pip install -r requirements.txt`

## Related Modules

- **HiveMatrix Core** (Port 5000): Authentication and identity management
- **HiveMatrix Nexus** (Port 443): UI composition and routing proxy
- **HiveMatrix Helm** (Port 5004): Service manager
- **HiveMatrix Brainhair** (Port 5050): AI assistant with access to Codex data
- **HiveMatrix Ledger** (Port 5030): Billing calculations using Codex data

## License

MIT License - See LICENSE file for details

## Contributing

When adding features:
1. Follow the HiveMatrix architecture patterns
2. Use `@token_required` for all protected routes
3. Use BEM classes for all HTML (no CSS in this service)
4. Update this README with new API endpoints
5. Test service-to-service communication
6. Consider data model extensibility for future needs

For questions, refer to `ARCHITECTURE.md` in the main HiveMatrix repository.
