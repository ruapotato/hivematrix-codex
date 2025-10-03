# HiveMatrix Codex - Central Data Hub

## Overview

**Codex is the central data repository for the HiveMatrix ecosystem.**

All external data syncing happens in Codex. Other services (Ledger, etc.) pull data from Codex via API.

## Architecture

```
Codex = Central Data Hub
    ↓
Syncs FROM:
    - Freshservice (CRM/Ticketing)
    - Datto RMM (Asset Management)
    ↓
Provides data TO:
    - Ledger (Billing Service)
    - Future services...
```

## What Codex Syncs

### 1. Freshservice Sync (`pull_freshservice.py`)
**Syncs:** Companies (Departments) and Contacts (Requesters)

- Fetches all departments (companies) with custom fields
- Maps `account_number` custom field to primary key
- Fetches all requesters (contacts/users)
- Associates contacts with companies
- **Runtime:** ~2-5 minutes

### 2. Datto RMM Sync (`pull_datto.py`)
**Syncs:** Assets and Backup Data

- Fetches all devices from Datto RMM
- Links devices to companies via account number in Datto
- Extracts backup storage data from UDF fields
- Stores hardware info, OS, online status, etc.
- **Runtime:** ~5-15 minutes

### 3. Freshservice Ticket Sync (`sync_tickets_from_freshservice.py`)
**Syncs:** Closed Tickets with Time Entries

- Fetches closed tickets from the past year
- Gets time entries for each ticket
- Associates tickets with companies for billing
- Defaults to 0.25 hours (15 min) if no time entries
- **Runtime:** ~2-4 hours for initial full sync, ~5-10 minutes for incremental

## How to Run Syncs

### Option 1: Via Admin Dashboard (Recommended)

1. Log into Codex as admin
2. Navigate to "Data Sync Center" section
3. Click sync buttons:
   - **📋 Sync Freshservice** - Companies & Contacts
   - **💻 Sync Datto RMM** - Assets & Backup Data
   - **🎫 Sync Tickets** - Billing Hours

### Option 2: Via Command Line

```bash
cd /path/to/hivematrix-codex
source pyenv/bin/activate

# Sync companies and contacts
python pull_freshservice.py

# Sync assets and backup data
python pull_datto.py

# Sync tickets (incremental - only new/updated)
python sync_tickets_from_freshservice.py

# Sync tickets (full sync - past year, clears existing)
python sync_tickets_from_freshservice.py --full-sync
```

### Option 3: Via API (for automation)

```bash
# POST requests to sync endpoints (admin auth required)
curl -X POST http://localhost:5001/codex/sync/freshservice
curl -X POST http://localhost:5001/codex/sync/datto
curl -X POST http://localhost:5001/codex/sync/tickets
```

## Configuration

### Required Config File: `instance/codex.conf`

```ini
[database]
connection_string = postgresql://user:pass@localhost:5432/codex_db

[freshservice]
api_key = your_freshservice_api_key
domain = integotecllc.freshservice.com

[datto]
api_endpoint = https://zinfandel-api.centrastage.net
public_key = YOUR_PUBLIC_KEY
secret_key = YOUR_SECRET_KEY
```

### Environment Variables: `.flaskenv`

```bash
FLASK_APP=run.py
FLASK_ENV=development
CORE_SERVICE_URL='http://localhost:5000'
SERVICE_NAME='codex'
```

## API Endpoints for Other Services

Codex provides these endpoints for services like Ledger:

### Companies
- `GET /api/companies` - All companies
- `GET /api/companies/{account_number}` - Single company
- `GET /api/companies/bulk` - All companies with assets, contacts, locations

### Assets
- `GET /api/companies/{account_number}/assets` - All assets for a company
  - Includes `backup_data_bytes` calculated from `backup_usage_tb`

### Contacts
- `GET /api/companies/{account_number}/contacts` - All contacts for a company

### Tickets
- `GET /api/companies/{account_number}/tickets` - All tickets for a company
- `GET /api/companies/{account_number}/tickets?year=2025` - Filter by year

### Locations
- `GET /api/companies/{account_number}/locations` - All locations for a company

## Database Schema

### Core Tables
- **companies** - CRM data from Freshservice
- **contacts** - Users/employees from Freshservice
- **assets** - Devices from Datto RMM
- **ticket_details** - Closed tickets with hours from Freshservice
- **locations** - Company locations
- **datto_site_links** - Maps Datto sites to companies

### Association Tables
- **contact_company_link** - Many-to-many: contacts ↔ companies
- **asset_contact_link** - Many-to-many: assets ↔ contacts

## Sync Schedule Recommendations

### Daily
- Freshservice sync (companies/contacts change frequently)
- Datto RMM sync (asset status/backup data updates daily)

### Hourly or Real-time
- Ticket sync (for accurate billing hours)

### Setup Cron Jobs

```bash
# Add to crontab
0 2 * * * cd /path/to/codex && source pyenv/bin/activate && python pull_freshservice.py
0 3 * * * cd /path/to/codex && source pyenv/bin/activate && python pull_datto.py
0 */2 * * * cd /path/to/codex && source pyenv/bin/activate && python sync_tickets_from_freshservice.py
```

## Troubleshooting

### Sync fails with "CORE_SERVICE_URL not set"

Ensure `.flaskenv` exists and contains:
```bash
CORE_SERVICE_URL='http://localhost:5000'
SERVICE_NAME='codex'
```

### Freshservice sync returns no companies

1. Check API key is correct in `instance/codex.conf`
2. Verify Freshservice domain is correct
3. Ensure companies have `account_number` custom field set

### Datto sync returns no assets

1. Check Datto API credentials are valid
2. Verify sites are linked to companies (account number must match)
3. Check firewall allows access to Datto API endpoint

### Ticket sync is slow

This is normal! Ticket sync fetches time entries for each ticket individually.
- Initial full sync: ~2-4 hours for 3000+ tickets
- Incremental sync: ~5-10 minutes
- Run full sync only once, then use incremental syncs

### Backup data not showing in Ledger

1. Verify Datto sync completed successfully
2. Check assets have `backup_usage_tb` values in Codex database
3. Codex API automatically converts TB to bytes for Ledger

## Migration Notes

If migrating from old integodash:

1. **Companies:** Import from integodash `companies` table or sync fresh from Freshservice
2. **Assets:** Run Datto sync (don't import from integodash - data may be stale)
3. **Tickets:** Run ticket sync with `--full-sync` to pull past year
4. **Billing Data:** DO NOT import - this stays in Ledger service

## Development

### Create new migration

```bash
source pyenv/bin/activate
flask db migrate -m "Add new field"
flask db upgrade
```

### Reset database (DANGER!)

```bash
source pyenv/bin/activate
python -c "from app import app; from extensions import db; app.app_context().push(); db.drop_all(); db.create_all()"
```

## Support

For issues or questions:
1. Check logs in Codex instance directory
2. Verify all configs are correct
3. Test API endpoints manually with curl
4. Check that external services (Freshservice/Datto) are accessible
