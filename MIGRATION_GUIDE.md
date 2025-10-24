# Codex Database Migration Guide

## Overview

The `init_db.py` script intelligently handles database schema updates for production deployments. It adds new tables and columns WITHOUT dropping existing data.

## Usage Modes

### 1. Initial Setup (New Installation)
```bash
python init_db.py
```
- Prompts for database credentials
- Prompts for Freshservice API config
- Prompts for Datto RMM config
- Creates all tables from scratch
- Saves config to `instance/codex.conf`

### 2. Production Migration (Existing Database)
```bash
python init_db.py --migrate-only
```
- Uses existing `instance/codex.conf`
- Inspects current database schema
- Adds missing tables (if any)
- Adds missing columns (if any)
- **PRESERVES ALL EXISTING DATA**
- Safe to run multiple times (idempotent)

### 3. Force Rebuild (Development Only)
```bash
python init_db.py --force-rebuild
```
- ⚠️ **DANGEROUS**: Drops ALL tables
- Recreates schema from scratch
- **DELETES ALL DATA**
- Requires typing "DELETE ALL DATA" to confirm
- Never use in production!

## Production Deployment Workflow

### Scenario 1: Deploying New Schema Changes

When you update `models.py` with new fields (like we just did):

```bash
# 1. Pull latest code
cd /path/to/hivematrix-codex
git pull

# 2. Activate virtual environment
source pyenv/bin/activate

# 3. Run migration (preserves data)
python init_db.py --migrate-only

# 4. Restart service
sudo systemctl restart codex
```

### Scenario 2: Fresh Production Install

First time setting up Codex on a production server:

```bash
# 1. Clone repo
git clone <repo-url> hivematrix-codex
cd hivematrix-codex

# 2. Set up Python environment
python3 -m venv pyenv
source pyenv/bin/activate
pip install -r requirements.txt

# 3. Run initial setup
python init_db.py
# (Follow interactive prompts)

# 4. Sync data from Freshservice
python pull_freshservice.py

# 5. Start service
python run.py
```

## What the Migration Does

### Inspects Current Schema
- Connects to existing database
- Lists all tables
- Lists all columns in each table

### Compares with Models
- Reads `models.py` to see what SHOULD exist
- Identifies missing tables
- Identifies missing columns

### Adds Missing Items
- Creates new tables (if any)
- Adds new columns to existing tables
- Handles defaults and nullable constraints
- **Never drops or modifies existing data**

### Safety Features
- Detects NOT NULL columns without defaults
- Automatically makes them nullable to avoid failures
- Wraps each change in a transaction
- Reports successes and failures clearly

## Example Migration Output

```
================================================================================
DATABASE SCHEMA MIGRATION
================================================================================

Found 10 existing tables in database

→ Updating table 'companies' - adding 12 columns:
   ✓ Added column: head_user_id (BIGINT)
   ✓ Added column: head_name (VARCHAR(150))
   ✓ Added column: prime_user_id (BIGINT)
   ✓ Added column: prime_user_name (VARCHAR(150))
   ✓ Added column: created_at (VARCHAR(100))
   ✓ Added column: updated_at (VARCHAR(100))
   ✓ Added column: workspace_id (INTEGER)
   ✓ Added column: managed_users (VARCHAR(100))
   ✓ Added column: managed_devices (VARCHAR(100))
   ✓ Added column: managed_network (VARCHAR(100))
   ✓ Added column: contract_term (VARCHAR(50))
   ✓ Added column: address (TEXT)

→ Updating table 'contacts' - adding 18 columns:
   ✓ Added column: first_name (VARCHAR(150))
   ✓ Added column: last_name (VARCHAR(150))
   ✓ Added column: is_agent (BOOLEAN)
   ✓ Added column: vip_user (BOOLEAN)
   ... etc

================================================================================
MIGRATION SUMMARY
================================================================================

✓ Added 30 new column(s):
  - companies.head_user_id
  - companies.head_name
  - companies.prime_user_id
  ... etc
```

## Recent Schema Changes (2025-10-24)

### Companies Table
Added comprehensive Freshservice fields:
- `head_user_id`, `head_name` - Company head person
- `prime_user_id`, `prime_user_name` - Primary contact
- `created_at`, `updated_at` - Timestamps from FS
- `workspace_id` - Freshservice workspace
- `managed_users`, `managed_devices`, `managed_network` - Billing counts
- `contract_term` - Contract length (1-Year, 2-Year, etc.)
- `address` - Full company address

### Contacts Table
Added comprehensive requester/user fields:
- `first_name`, `last_name` - Name components
- `is_agent`, `vip_user`, `has_logged_in` - Status flags
- `job_title`, `department_ids`, `department_names` - Job info
- `reporting_manager_id`, `location_id`, `location_name` - Org structure
- `language`, `time_zone`, `time_format` - User preferences
- `can_see_all_tickets_from_associated_departments` - Permissions
- `created_at`, `updated_at` - Timestamps
- Plus many more...

### Sync Jobs Table (New)
Added for persistent sync tracking:
- `id` - UUID
- `script` - Which sync (freshservice, datto, tickets)
- `status` - running/completed/failed
- `started_at`, `completed_at` - Timestamps
- `output`, `error` - Captured logs
- `success` - Boolean result

## Rollback Strategy

If migration causes issues:

```bash
# Option 1: Restore from backup
pg_restore -U codex_user -d codex_db backup.sql

# Option 2: Drop problematic columns manually
psql -U codex_user -d codex_db
DROP COLUMN IF EXISTS problematic_column;

# Option 3: Full rebuild from backup + re-sync
# (Last resort if corruption occurs)
```

## Best Practices

1. **Always backup before migration**
   ```bash
   pg_dump -U codex_user codex_db > backup_$(date +%Y%m%d).sql
   ```

2. **Test in staging first**
   - Deploy to staging environment
   - Run full sync
   - Verify data integrity
   - Then deploy to production

3. **Run during maintenance window**
   - Minimal traffic
   - Can rollback if needed
   - Monitor for 30+ minutes after

4. **Monitor logs**
   ```bash
   tail -f /var/log/codex/codex.log
   ```

5. **Verify data after migration**
   ```bash
   python - <<EOF
   from app import app
   from models import Company, Contact
   with app.app_context():
       print(f"Companies: {Company.query.count()}")
       print(f"Contacts: {Contact.query.count()}")
   EOF
   ```

## Troubleshooting

### Issue: Column already exists
**Cause**: Migration was partially run before
**Fix**: Migration will skip existing columns automatically

### Issue: Cannot add NOT NULL column
**Cause**: Existing rows have NULL values
**Fix**: Migration automatically makes them nullable

### Issue: Database connection refused
**Cause**: PostgreSQL not running or wrong credentials
**Fix**:
```bash
sudo systemctl status postgresql
# Check instance/codex.conf for correct credentials
```

### Issue: Foreign key constraint violation
**Cause**: Data inconsistency
**Fix**: Check referenced tables exist first, or run full re-sync

## Support

For issues with migrations:
1. Check migration output for specific errors
2. Review `instance/codex.conf` for correct database settings
3. Verify PostgreSQL is running and accessible
4. Check database user has CREATE/ALTER permissions
5. Review ARCHITECTURE.md for system design context
