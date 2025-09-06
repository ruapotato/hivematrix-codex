from flask import Blueprint, render_template, request, flash, redirect, url_for, session, jsonify
from models import db, SchedulerJob, User
from decorators import admin_required
from extensions import scheduler
import time

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')

@settings_bp.route('/')
@admin_required
def settings_page():
    jobs = SchedulerJob.query.all()
    users = User.query.all()
    return render_template('settings.html', jobs=jobs, users=users)

@settings_bp.route('/update_job/<int:job_id>', methods=['POST'])
@admin_required
def update_job(job_id):
    job = SchedulerJob.query.get_or_404(job_id)
    job.interval_minutes = int(request.form.get('interval', 1440))
    job.enabled = 'enabled' in request.form
    db.session.commit()
    flash(f'Job "{job.job_name}" has been updated. Please restart the application for changes to take effect.', 'success')
    return redirect(url_for('settings.settings_page'))


@settings_bp.route('/run_now/<int:job_id>', methods=['POST'])
@admin_required
def run_job_now(job_id):
    from scheduler import run_job
    job = SchedulerJob.query.get_or_404(job_id)
    if job and scheduler.running:
        # Run the job immediately in a new thread
        scheduler.add_job(
            run_job,
            args=[job.id, job.script_path],
            id=f"manual_run_{job.id}_{time.time()}", # Unique ID for this run
            misfire_grace_time=None,
            coalesce=False
        )
        flash(f"Job '{job.job_name}' has been triggered to run now.", 'success')
    else:
        flash("Scheduler is not running or job not found.", 'error')
    return redirect(url_for('settings.settings_page'))


@settings_bp.route('/log/<int:job_id>')
@admin_required
def get_log(job_id):
    job = SchedulerJob.query.get_or_404(job_id)
    return jsonify({'log': job.last_run_log or 'No log available.'})

