"""
Background Scheduler for Codex Data Syncs

Automatically runs data sync scripts on a schedule.
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import subprocess
import os
import logging
from flask import current_app

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = None


def run_sync_script(script_name):
    """
    Run a sync script as a background subprocess.

    Args:
        script_name: Name of the script (e.g., 'pull_freshservice.py')
    """
    try:
        script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), script_name)
        python_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'pyenv', 'bin', 'python')

        if not os.path.exists(python_path):
            python_path = 'python3'

        logger.info(f"Running scheduled sync: {script_name}")

        # Run script in background
        subprocess.Popen(
            [python_path, script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.path.dirname(script_path)
        )

        logger.info(f"Started scheduled sync: {script_name}")

    except Exception as e:
        logger.error(f"Error running scheduled sync {script_name}: {e}")


def run_freshservice_sync():
    """
    Run Freshservice sync with account number assignment first.

    This ensures all companies have account numbers before syncing.
    """
    try:
        base_dir = os.path.dirname(os.path.dirname(__file__))
        python_path = os.path.join(base_dir, 'pyenv', 'bin', 'python')

        if not os.path.exists(python_path):
            python_path = 'python3'

        logger.info("Running Freshservice sync workflow")

        # Step 1: Assign account numbers to companies missing them
        logger.info("Step 1: Assigning account numbers to Freshservice companies")
        set_account_script = os.path.join(base_dir, 'set_account_numbers.py')

        result = subprocess.run(
            [python_path, set_account_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=base_dir,
            timeout=300  # 5 minute timeout
        )

        if result.returncode == 0:
            logger.info("Account numbers assigned successfully")
        else:
            logger.warning(f"Account number assignment had issues: {result.stderr.decode()}")

        # Step 2: Pull Freshservice data
        logger.info("Step 2: Pulling Freshservice data")
        run_sync_script('pull_freshservice.py')

    except subprocess.TimeoutExpired:
        logger.error("set_account_numbers.py timed out after 5 minutes")
    except Exception as e:
        logger.error(f"Error in Freshservice sync workflow: {e}")


def init_scheduler(app):
    """
    Initialize and start the background scheduler.

    Args:
        app: Flask application instance
    """
    global scheduler

    if scheduler is not None:
        logger.warning("Scheduler already initialized")
        return scheduler

    scheduler = BackgroundScheduler(daemon=True)

    with app.app_context():
        # Get schedule settings from config
        freshservice_enabled = app.config.get('SYNC_FRESHSERVICE_ENABLED', True)
        datto_enabled = app.config.get('SYNC_DATTO_ENABLED', True)
        tickets_enabled = app.config.get('SYNC_TICKETS_ENABLED', True)

        freshservice_schedule = app.config.get('SYNC_FRESHSERVICE_SCHEDULE', 'daily')
        datto_schedule = app.config.get('SYNC_DATTO_SCHEDULE', 'daily')
        tickets_schedule = app.config.get('SYNC_TICKETS_SCHEDULE', 'hourly')

        # Schedule Freshservice sync (companies & contacts)
        if freshservice_enabled:
            if freshservice_schedule == 'daily':
                scheduler.add_job(
                    func=run_freshservice_sync,
                    trigger=CronTrigger(hour=2, minute=0),  # 2:00 AM daily
                    id='freshservice_sync',
                    name='Sync Freshservice (Companies & Contacts)',
                    replace_existing=True
                )
                logger.info("Scheduled Freshservice sync: Daily at 2:00 AM")
            elif freshservice_schedule == 'hourly':
                scheduler.add_job(
                    func=run_freshservice_sync,
                    trigger=IntervalTrigger(hours=1),
                    id='freshservice_sync',
                    name='Sync Freshservice (Companies & Contacts)',
                    replace_existing=True
                )
                logger.info("Scheduled Freshservice sync: Every hour")

        # Schedule Datto RMM sync (assets & backup)
        if datto_enabled:
            if datto_schedule == 'daily':
                scheduler.add_job(
                    func=lambda: run_sync_script('pull_datto.py'),
                    trigger=CronTrigger(hour=3, minute=0),  # 3:00 AM daily
                    id='datto_sync',
                    name='Sync Datto RMM (Assets & Backup)',
                    replace_existing=True
                )
                logger.info("Scheduled Datto sync: Daily at 3:00 AM")
            elif datto_schedule == 'hourly':
                scheduler.add_job(
                    func=lambda: run_sync_script('pull_datto.py'),
                    trigger=IntervalTrigger(hours=1),
                    id='datto_sync',
                    name='Sync Datto RMM (Assets & Backup)',
                    replace_existing=True
                )
                logger.info("Scheduled Datto sync: Every hour")

        # Schedule Tickets sync
        if tickets_enabled:
            if tickets_schedule == 'hourly':
                scheduler.add_job(
                    func=lambda: run_sync_script('sync_tickets_from_freshservice.py'),
                    trigger=IntervalTrigger(hours=1),
                    id='tickets_sync',
                    name='Sync Tickets',
                    replace_existing=True
                )
                logger.info("Scheduled Tickets sync: Every hour")
            elif tickets_schedule == 'daily':
                scheduler.add_job(
                    func=lambda: run_sync_script('sync_tickets_from_freshservice.py'),
                    trigger=CronTrigger(hour=4, minute=0),  # 4:00 AM daily
                    id='tickets_sync',
                    name='Sync Tickets',
                    replace_existing=True
                )
                logger.info("Scheduled Tickets sync: Daily at 4:00 AM")

        # Run initial sync on startup if enabled
        run_on_startup = app.config.get('SYNC_RUN_ON_STARTUP', False)
        if run_on_startup:
            logger.info("Running initial sync on startup...")
            if freshservice_enabled:
                scheduler.add_job(
                    func=run_freshservice_sync,
                    trigger='date',  # Run once immediately
                    id='freshservice_startup',
                    name='Startup Freshservice Sync',
                    replace_existing=True
                )
            if datto_enabled:
                scheduler.add_job(
                    func=lambda: run_sync_script('pull_datto.py'),
                    trigger='date',  # Run once immediately
                    id='datto_startup',
                    name='Startup Datto Sync',
                    replace_existing=True
                )

        # Start the scheduler
        scheduler.start()
        logger.info("Background scheduler started successfully")

    return scheduler


def get_scheduler():
    """Get the global scheduler instance."""
    return scheduler


def shutdown_scheduler():
    """Shutdown the scheduler gracefully."""
    global scheduler
    if scheduler is not None:
        scheduler.shutdown()
        scheduler = None
        logger.info("Scheduler shut down")
