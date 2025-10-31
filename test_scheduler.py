#!/usr/bin/env python3
"""
Test the Codex scheduler by manually triggering jobs.
"""

from app import app
from app.scheduler import get_scheduler, run_freshservice_sync
import time
import sys

def test_scheduler_status():
    """Check if scheduler is running and show scheduled jobs."""
    print("=" * 60)
    print("SCHEDULER STATUS TEST")
    print("=" * 60)

    with app.app_context():
        scheduler = get_scheduler()
        if not scheduler:
            print("✗ Scheduler is not running!")
            return False

        print("✓ Scheduler is running\n")
        print("Scheduled Jobs:")
        jobs = scheduler.get_jobs()

        if not jobs:
            print("  (No jobs scheduled)")
            return False

        for job in jobs:
            print(f"\n  Job: {job.name}")
            print(f"    ID: {job.id}")
            print(f"    Next run: {job.next_run_time}")
            print(f"    Trigger: {job.trigger}")

        return True


def test_freshservice_sync():
    """Manually trigger the Freshservice sync workflow."""
    print("\n" + "=" * 60)
    print("FRESHSERVICE SYNC WORKFLOW TEST")
    print("=" * 60)
    print("\nThis will:")
    print("  1. Run set_account_numbers.py")
    print("  2. Run pull_freshservice.py")
    print("\nStarting in 3 seconds...")
    time.sleep(3)

    with app.app_context():
        run_freshservice_sync()

    print("\n✓ Sync workflow triggered successfully")
    print("\nNote: The sync runs in the background.")
    print("Check Codex logs to see progress:")
    print("  cd /home/troy/projects/hivematrix/hivematrix-helm")
    print("  source pyenv/bin/activate")
    print("  python logs_cli.py codex --tail 50")


def test_job_execution():
    """Test if a specific job can be executed."""
    print("\n" + "=" * 60)
    print("JOB EXECUTION TEST")
    print("=" * 60)

    with app.app_context():
        scheduler = get_scheduler()
        if not scheduler:
            print("✗ Scheduler is not running!")
            return False

        # Find the Freshservice sync job
        job = scheduler.get_job('freshservice_sync')
        if not job:
            print("✗ Freshservice sync job not found!")
            return False

        print(f"\n✓ Found job: {job.name}")
        print(f"  Next scheduled run: {job.next_run_time}")
        print("\nManually triggering job now...")

        # Trigger the job manually
        job.modify(next_run_time=None)
        scheduler.add_job(
            func=run_freshservice_sync,
            trigger='date',  # Run once immediately
            id='test_freshservice_sync',
            name='Test Freshservice Sync',
            replace_existing=True
        )

        print("✓ Job triggered successfully")
        print("\nJob will execute in the background.")
        print("Check logs for results.")

        return True


if __name__ == "__main__":
    print("\n🧪 CODEX SCHEDULER TEST SUITE\n")

    # Test 1: Check scheduler status
    if not test_scheduler_status():
        print("\n✗ Scheduler status test failed")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("\nChoose a test:")
    print("  1. Manually trigger Freshservice sync workflow")
    print("  2. Test job execution via scheduler")
    print("  3. Just show status (already done)")
    print()

    try:
        choice = input("Enter choice (1-3, or q to quit): ").strip()

        if choice == '1':
            test_freshservice_sync()
        elif choice == '2':
            test_job_execution()
        elif choice == '3':
            print("\n✓ Status already shown above")
        elif choice.lower() == 'q':
            print("\nExiting...")
        else:
            print("\nInvalid choice")
    except KeyboardInterrupt:
        print("\n\nExiting...")
    except EOFError:
        print("\n\nNo input available, showing status only")

    print("\n✓ Test suite complete\n")
