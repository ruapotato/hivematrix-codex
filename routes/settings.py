from flask import Blueprint, render_template, request, flash, redirect, url_for, session, jsonify, current_app
from models import db, SchedulerJob, User
from decorators import admin_required
from extensions import scheduler
import time
import configparser
import os

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')

def get_feature_key(feature_name):
    """Converts a feature name like 'Email Security' to 'email_security' for config keys."""
    return feature_name.lower().replace(' ', '_')

def load_plans_from_config(config):
    """Reads plan names and features from the config parser object."""
    plan_names_str = config.get('plans', 'plan_names', fallback='Default Plan')
    plan_names = [p.strip() for p in plan_names_str.split(',')]

    features = {}
    if config.has_section('features'):
        for key, value in config.items('features'):
            feature_name = key.replace('_', ' ').title()
            if 'Sat' in feature_name:
                feature_name = feature_name.replace('Sat', 'SAT')
            if 'Soc' in feature_name:
                feature_name = feature_name.replace('Soc', 'SOC')
            options = [opt.strip() for opt in value.split(',')]
            features[feature_name] = options
    else:
        # Fallback if [features] section is somehow missing
        features = {"Default Feature": ["Option 1", "Not Included"]}

    return plan_names, features

@settings_bp.route('/')
@admin_required
def settings_page():
    jobs = SchedulerJob.query.all()
    users = User.query.all()

    config = current_app.config.get('NEXUS_CONFIG', configparser.ConfigParser())
    plan_names, features = load_plans_from_config(config)

    plans_config = {}
    for plan_name in plan_names:
        section_name = f"plan_{plan_name.replace(' ', '_')}"
        plans_config[plan_name] = {}
        for feature_name in features.keys():
            feature_key = get_feature_key(feature_name)
            plans_config[plan_name][feature_name] = config.get(section_name, feature_key, fallback="Not Included")

    return render_template('settings.html',
                           jobs=jobs,
                           users=users,
                           plans=plans_config,
                           plan_names=plan_names,
                           features=features)

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

@settings_bp.route('/update_plans', methods=['POST'])
@admin_required
def update_plans():
    config_path = os.path.join(current_app.instance_path, 'nexus.conf')
    config = configparser.ConfigParser()
    config.read(config_path)

    plan_names, features = load_plans_from_config(config)

    for plan_name in plan_names:
        section_name = f"plan_{plan_name.replace(' ', '_')}"
        if not config.has_section(section_name):
            config.add_section(section_name)

        for feature_name in features.keys():
            feature_key = get_feature_key(feature_name)
            form_field_name = f"{section_name}-{feature_key}"
            value = request.form.get(form_field_name)
            if value:
                config.set(section_name, feature_key, value)

    with open(config_path, 'w') as configfile:
        config.write(configfile)

    # Update the app's config in memory so changes are reflected immediately
    current_app.config['NEXUS_CONFIG'] = config
    flash('Plan settings have been updated successfully.', 'success')
    return redirect(url_for('settings.settings_page'))
