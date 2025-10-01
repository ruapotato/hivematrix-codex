# HiveMatrix Codex

**The Central CRM for the HiveMatrix PSA Ecosystem**

Codex is the customer relationship management service for HiveMatrix. It manages the core directory of Companies, Contacts, and Assets, providing both a web interface and REST APIs for other HiveMatrix modules to consume.

## Overview

Codex is a standalone HiveMatrix module that:
- Maintains the master database for Companies, Contacts, and Assets
- Syncs data from external systems (Freshservice, Datto RMM)
- Provides REST APIs for other modules to query CRM data
- Offers a web UI for viewing and managing customer information
- Manages company service plans and feature assignments

**Port:** 5010 (standard)

## Architecture

Codex follows the HiveMatrix monolithic service pattern:
- **Authentication:** Uses Core service for JWT-based authentication (no local user management)
- **Database:** PostgreSQL (owns `companies`, `contacts`, `assets` tables)
- **Styling:** Unstyled HTML using BEM classes, styled by Nexus proxy
- **APIs:** Exposes both HTML views and JSON APIs

## Project Structure

```
hivematrix-codex/
├── app/
│   ├── __init__.py           # Flask app initialization
│   ├── auth.py               # @token_required decorator
│   ├── routes.py             # Main web routes
│   ├── service_client.py     # Service-to-service helper
│   └── templates/            # HTML templates (BEM styled)
├── routes/
│   ├── assets.py             # Asset management routes
│   ├── companies.py          # Company management routes
│   └── contacts.py           # Contact management routes
├── instance/
│   └── codex.conf            # Configuration (created by init_db.py)
├── extensions.py             # Flask extensions
├── models.py                 # SQLAlchemy models
├── init_db.py                # Database initialization script
├── run.py                    # Application entry point
├── pull_datto.py             # Datto RMM sync script
├── pull_freshservice.py      # Freshservice sync script
├── set_account_numbers.py    # Account number management
├── push_account_nums_to_datto.py  # Push account numbers back to Datto
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

First, install PostgreSQL and its additional components:

bash

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

Switch to the PostgreSQL user and access the PostgreSQL prompt:

```bash
# Switch to postgres user
sudo -i -u postgres

# Access PostgreSQL prompt
psql


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
- Create the database schema (companies, contacts, assets, etc.)
- Generate a `instance/codex.conf` file with your settings

### 6. Configure External Integrations

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
    "template": {
        "url": "http://localhost:5001"
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

Pulls companies and contacts from Freshservice:

```bash
python pull_freshservice.py
```

This syncs:
- Companies (from Freshservice Departments)
- Contacts (from Freshservice Requesters)
- Company-to-Contact relationships

### Sync from Datto RMM

Pulls assets and device information from Datto RMM:

```bash
python pull_datto.py
```

This syncs:
- Assets (devices/computers)
- Device details (OS, IP addresses, last seen, etc.)
- Links Datto sites to company account numbers

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

# Add these lines (sync every 24 hours at 2 AM)
0 2 * * * /path/to/pyenv/bin/python /path/to/hivematrix-codex/pull_freshservice.py
0 3 * * * /path/to/pyenv/bin/python /path/to/hivematrix-codex/pull_datto.py
```

## API Endpoints

All API endpoints require JWT authentication via the `Authorization: Bearer <token>` header.

### Companies

- `GET /api/companies` - List all companies
- `POST /api/companies` - Create a new company
- `GET /api/companies/<account_number>` - Get company details
- `PUT /api/companies/<account_number>` - Update company
- `GET /api/companies/<account_number>/users` - Get users for a company

### Assets

- `GET /api/assets` - List all assets
- `POST /api/assets` - Create a new asset
- `GET /api/assets/<asset_id>` - Get asset details
- `PUT /api/assets/<asset_id>` - Update asset
- `DELETE /api/assets/<asset_id>` - Delete asset

### Contacts

- `GET /api/contacts` - List all contacts
- `POST /api/contacts` - Create a new contact
- `GET /api/contacts/<contact_id>` - Get contact details
- `PUT /api/contacts/<contact_id>` - Update contact

### Billing Summary

- `GET /api/billing_summary` - Get comprehensive data for billing calculations (used by Treasury module)

## Web Interface

When accessed through the Nexus proxy at `http://localhost:8000/codex/`, the web interface provides:

- **Companies**: Browse, search, and manage company records
- **Contacts**: View and edit contact information
- **Assets**: Device inventory and details
- **Company Details**: View plans, features, locations, and associated records

## Service-to-Service Communication

Codex can call other HiveMatrix services using the service client:

```python
from app.service_client import call_service

# Call another service's API
response = call_service('template', '/api/example')
data = response.json()
```

The service client automatically:
1. Requests a service token from Core
2. Makes the authenticated request
3. Returns the response

## Development

### Database Migrations

After modifying `models.py`:

```bash
# Re-run init_db.py and choose to drop/recreate tables
python init_db.py
```

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

### Using Caddy (Recommended)

Add to your Caddyfile:

```
codex.your-domain.com {
    reverse_proxy 127.0.0.1:5010
}
```

Restart Caddy:
```bash
sudo systemctl restart caddy
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

**Import errors:**
- Ensure virtual environment is activated
- Reinstall dependencies: `pip install -r requirements.txt`

## Related Modules

- **HiveMatrix Core** (Port 5000): Authentication and identity management
- **HiveMatrix Nexus** (Port 8000): UI composition and routing proxy
- **HiveMatrix Template** (Port 5001): Service template/example

## License

MIT License - See LICENSE file for details

## Contributing

When adding features:
1. Follow the HiveMatrix architecture patterns
2. Use `@token_required` for all protected routes
3. Use BEM classes for all HTML (no CSS in this service)
4. Update this README with new API endpoints
5. Test service-to-service communication

For questions, refer to `ARCHITECTURE.md` in the main HiveMatrix repository.
