# Codex Ticket Sync - Full Context Documentation

## Overview

The Codex ticket sync has been enhanced to capture **full ticket context** including:
- Complete conversation history (customer and tech back-and-forth)
- Internal notes (private technician notes)
- Rich metadata (requester, priority, status, etc.)
- Time entries for billing

This provides comprehensive context for:
- **KnowledgeTree** - AI-assisted support with full ticket history
- **Ledger** - Accurate billing with time tracking
- **Future Services** - Complete support history and analytics

## What Gets Synced

### Basic Ticket Information
- **Ticket ID** - Unique identifier
- **Subject** - Ticket title
- **Status** - Open, Pending, Resolved, Closed
- **Priority** - Low, Medium, High, Urgent
- **Created/Updated/Closed dates**
- **Hours spent** - Total billable time

### Requester Information
- **Name** - Customer who opened the ticket
- **Email** - Contact email
- Links to company via department_id

### Description
- **HTML version** - Original formatted description
- **Plain text version** - Stripped HTML for easier processing

### Conversation History
Full back-and-forth communication stored as JSON:
```json
[
  {
    "id": 12345,
    "body": "Plain text message",
    "body_html": "<p>HTML formatted message</p>",
    "from_email": "customer@example.com",
    "to_emails": ["support@integotec.com"],
    "created_at": "2025-01-15T10:30:00Z",
    "updated_at": "2025-01-15T10:30:00Z",
    "incoming": true,
    "private": false,
    "user_id": 789,
    "support_email": "support@integotec.com"
  }
]
```

### Internal Notes
Private technician notes stored as JSON:
```json
[
  {
    "id": 12346,
    "body": "Internal note text",
    "from_email": "tech@integotec.com",
    "created_at": "2025-01-15T11:00:00Z",
    "private": true,
    "user_id": 456
  }
]
```

## Database Schema

### ticket_details Table

| Column | Type | Description |
|--------|------|-------------|
| `ticket_id` | BigInteger | Primary key |
| `company_account_number` | String(50) | FK to companies |
| `ticket_number` | String(50) | Display number |
| `subject` | Text | Ticket title |
| `description` | Text | Original HTML description |
| `description_text` | Text | Plain text description |
| `status` | String(50) | Current status |
| `priority` | String(50) | Priority level |
| `requester_email` | String(150) | Customer email |
| `requester_name` | String(150) | Customer name |
| `created_at` | String(50) | Creation timestamp |
| `last_updated_at` | String(50) | Last update timestamp |
| `closed_at` | String(50) | Closure timestamp |
| `total_hours_spent` | Float | Billable hours |
| `conversations` | Text | JSON array of messages |
| `notes` | Text | JSON array of internal notes |

## Sync Process

### 1. Fetch Closed Tickets
- Query Freshservice for tickets with `status = 5 (Closed)`
- Filter by `updated_at` since last sync (incremental)
- Or fetch all from past year (full sync with `--full-sync`)

### 2. For Each Ticket
1. **Map to company** via `department_id → account_number`
2. **Fetch time entries** from `/api/v2/tickets/{id}/time_entries`
3. **Fetch conversations** from `/api/v2/tickets/{id}/conversations`
4. **Parse and separate**:
   - Public conversations (private=false)
   - Internal notes (private=true)
5. **Strip HTML** from conversation bodies for plain text
6. **Store as JSON** in database

### 3. Error Handling
- Retry on rate limits (429 responses)
- Default to 0.25 hours if no time entries
- Skip tickets without valid company mapping
- Log warnings for API failures

### Runtime Expectations

| Sync Type | Tickets | Estimated Time |
|-----------|---------|----------------|
| Full sync | ~3000 | 4-6 hours |
| Incremental | ~50-100 | 10-15 minutes |
| Single ticket | 1 | ~2-3 seconds |

**Why so long?**
- Each ticket requires 2 API calls (time entries + conversations)
- Rate limiting (1 request/second)
- Conversation parsing and HTML stripping
- Database transactions

## API Endpoints

### Codex Public API

```bash
GET /api/companies/{account_number}/tickets
```

Returns full ticket context:
```json
[
  {
    "ticket_id": 17531,
    "ticket_number": "17531",
    "subject": "Email not working",
    "description": "<div>Can't send emails...</div>",
    "description_text": "Can't send emails...",
    "status": "Closed",
    "priority": "High",
    "requester_email": "user@company.com",
    "requester_name": "John Doe",
    "created_at": "2025-01-10T09:00:00Z",
    "last_updated_at": "2025-01-15T16:30:00Z",
    "closed_at": "2025-01-15T16:30:00Z",
    "total_hours_spent": 1.5,
    "conversations": [...],
    "notes": [...]
  }
]
```

Filter by year:
```bash
GET /api/companies/{account_number}/tickets?year=2025
```

## Usage in KnowledgeTree

KnowledgeTree creates rich markdown documents with full context:

```markdown
# Ticket #17531: Email not working

## Ticket Information
- **Requester:** John Doe (user@company.com)
- **Status:** Closed
- **Priority:** High
- **Created:** 2025-01-10T09:00:00Z
- **Hours Spent:** 1.5 hours

## Description
Can't send emails from Outlook...

## Conversation History

### Message 1 - → Incoming
**From:** user@company.com
**Date:** 2025-01-10T09:00:00Z

Can't send emails from Outlook. Getting error "Cannot connect to server"

---

### Message 2 - ← Outgoing
**From:** tech@integotec.com
**Date:** 2025-01-10T10:30:00Z

I've checked your email settings. Your outgoing server was configured incorrectly...

---

## Internal Notes

### Note 1
**From:** tech@integotec.com
**Date:** 2025-01-10T10:15:00Z

Customer was using wrong SMTP port. Changed from 25 to 587 with TLS.

---
```

## Usage in Ledger

Ledger uses ticket data for billing:
- Calculates billable hours per month/year
- Applies prepaid hour packages
- Generates invoice line items
- Exports to QuickBooks

**Note:** Ledger only needs `total_hours_spent`, but full context is available if needed for dispute resolution.

## Running the Sync

### Via Codex Dashboard (Recommended)
1. Log into Codex as admin
2. Click **"🎫 Sync Tickets (Billing Hours)"**
3. Wait for completion (can take hours for full sync)

### Via Command Line
```bash
cd /path/to/hivematrix-codex
source pyenv/bin/activate

# Incremental sync (recommended for regular use)
python sync_tickets_from_freshservice.py

# Full sync (only for initial setup or data recovery)
python sync_tickets_from_freshservice.py --full-sync
```

### Via API
```bash
curl -X POST http://localhost:5001/codex/sync/tickets \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

## Sync Schedule Recommendations

### Production
```bash
# Every 2 hours during business hours
0 8-18/2 * * * cd /path/to/codex && source pyenv/bin/activate && python sync_tickets_from_freshservice.py
```

### Development
```bash
# Once daily at night (less load)
0 2 * * * cd /path/to/codex && source pyenv/bin/activate && python sync_tickets_from_freshservice.py
```

## Troubleshooting

### Sync is very slow
**Normal behavior** - Each ticket requires 2-3 API calls
- Consider running during off-hours
- Use incremental sync (not full sync) regularly
- Monitor Freshservice API rate limits

### Missing conversation data
1. Check Freshservice API has conversations endpoint access
2. Verify ticket actually has conversations (check in Freshservice UI)
3. Review sync logs for API errors
4. Check database `conversations` column is not NULL

### HTML content appears in plain text
- `description` field contains HTML
- `description_text` field should have stripped HTML
- Check `strip_html()` function is working correctly

### Tickets not appearing in KnowledgeTree
1. Verify Codex has ticket data (`/api/companies/{account}/tickets`)
2. Run KnowledgeTree `sync_tickets.py` after Codex sync
3. Check Neo4j for ticket nodes
4. Verify company structure exists in KnowledgeTree

## Data Privacy & Security

### Sensitive Information
- Conversations may contain customer PII (personally identifiable information)
- Internal notes may contain passwords/credentials
- **Ensure database backups are encrypted**
- **Limit API access to authorized services only**

### GDPR / Data Retention
- Tickets are synced for billing and support purposes
- Consider retention policies (e.g., delete tickets older than 7 years)
- Implement data export/deletion for customer requests

### Access Control
- Codex API requires authentication
- Admin privileges required for sync operations
- KnowledgeTree can show tickets to authorized users only

## Performance Optimization

### Future Improvements
1. **Parallel processing** - Fetch multiple tickets concurrently
2. **Webhook integration** - Real-time updates instead of polling
3. **Caching** - Cache frequently accessed tickets
4. **Incremental conversation sync** - Only fetch new messages
5. **Compression** - Compress JSON data in database

### Current Optimizations
- ✅ Incremental sync (only new/updated tickets)
- ✅ Batch commits (50 tickets at a time)
- ✅ HTML stripping for smaller storage
- ✅ Separate public/private conversations

## Migration from Old System

### If migrating from integodash:
1. Run `--full-sync` once to populate all historical tickets
2. Verify data in Codex database
3. Update KnowledgeTree sync
4. Deprecate old integodash ticket sync
5. Schedule regular incremental syncs

### Data Comparison
```sql
-- Check ticket count
SELECT COUNT(*) FROM ticket_details;

-- Check tickets with conversations
SELECT COUNT(*) FROM ticket_details WHERE conversations IS NOT NULL;

-- Check average hours per ticket
SELECT AVG(total_hours_spent) FROM ticket_details WHERE total_hours_spent > 0;
```

## Support

For issues or questions:
1. Check Codex logs for API errors
2. Verify Freshservice API credentials
3. Test API endpoints manually with curl
4. Review sync script output for warnings
5. Check database for data integrity
