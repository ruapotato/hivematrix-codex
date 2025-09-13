# ruapotato/hivematrix-nexus/hivematrix-nexus-main/scheduler.py

import os
import sys
import subprocess
import configparser
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# This import is now safe because models.py has no dependencies on main.py
from models import SchedulerJob

def run_job(job_id, script_path):
    """Runs a sync script as a subprocess and logs the result."""
    print(f"[{datetime.now()}] SCHEDULER: Running job '{job_id}': {script_path}")
    log_output, status = "", "Failure"
    try:
        python_executable = sys.executable
        # Pass the instance path to the subprocess so it can find the config
        instance_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
        env = os.environ.copy()
        env['NEXUS_INSTANCE_PATH'] = instance_path

        result = subprocess.run(
            [python_executable, script_path],
            capture_output=True, text=True, check=False, timeout=7200,
            encoding='utf-8', errors='replace', env=env
        )
        log_output = f"--- STDOUT ---\n{result.stdout}\n\n--- STDERR ---\n{result.stderr}"
        if result.returncode == 0:
            status = "Success"
        print(f"[{datetime.now()}] SCHEDULER: Finished job '{job_id}' with status: {status}")
    except Exception as e:
        log_output = f"Scheduler failed to run script: {e}"
        print(f"[{datetime.now()}] SCHEDULER: FATAL ERROR running job '{job_id}': {e}", file=sys.stderr)
    finally:
        session = None
        try:
            instance_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
            config_path = os.path.join(instance_path, 'nexus.conf')
            config = configparser.ConfigParser()
            config.read(config_path)
            connection_string = config.get('database', 'connection_string')

            # --- THIS IS THE FIX ---
            # The 'timeout' parameter is not a valid DSN option for psycopg2
            engine = create_engine(connection_string)
            # --- END OF FIX ---
            Session = sessionmaker(bind=engine)
            session = Session()

            job = session.query(SchedulerJob).get(job_id)
            if job:
                job.last_run = datetime.now().isoformat(timespec='seconds')
                job.last_status = status
                job.last_run_log = log_output
                session.commit()
        except Exception as e:
            print(f"[{datetime.now()}] SCHEDULER: Failed to log job result to DB: {e}", file=sys.stderr)
            if session:
                session.rollback()
        finally:
            if session:
                session.close()
