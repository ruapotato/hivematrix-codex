from flask import render_template, g, jsonify
from app import app
from .auth import token_required, admin_required
from models import Company, Contact, Asset
import subprocess
import os

@app.route('/')
@token_required
def index():
    """Main dashboard route."""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403
    
    # Get counts for dashboard
    company_count = Company.query.count()
    contact_count = Contact.query.count()
    asset_count = Asset.query.count()
    
    return render_template('dashboard.html', 
                         user=g.user,
                         company_count=company_count,
                         contact_count=contact_count,
                         asset_count=asset_count)

@app.route('/sync/freshservice', methods=['POST'])
@admin_required
def sync_freshservice():
    """Trigger Freshservice sync script."""
    try:
        script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'pull_freshservice.py')
        result = subprocess.run(
            ['python', script_path],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        return jsonify({
            'success': result.returncode == 0,
            'output': result.stdout,
            'error': result.stderr
        })
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'error': 'Script timed out after 5 minutes'
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/sync/datto', methods=['POST'])
@admin_required
def sync_datto():
    """Trigger Datto RMM sync script."""
    try:
        script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'pull_datto.py')
        result = subprocess.run(
            ['python', script_path],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        return jsonify({
            'success': result.returncode == 0,
            'output': result.stdout,
            'error': result.stderr
        })
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'error': 'Script timed out after 5 minutes'
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
