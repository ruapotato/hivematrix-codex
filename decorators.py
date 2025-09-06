from functools import wraps
from flask import request, jsonify, session, flash, redirect, url_for
from models import User

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if user is logged in and has the 'admin' permission level
        if 'permission_level' not in session or session['permission_level'] != 'admin':
            flash("Admin access is required for this page.", "danger")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def api_key_required(permission_level=None):
    """
    A decorator factory that protects API endpoints.
    It takes a list of allowed permission levels.
    """
    if permission_level is None:
        permission_level = ['admin'] # Default to admin only if not specified

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            api_key = request.headers.get('X-API-Key')
            if not api_key:
                return jsonify({'message': 'API key is missing'}), 401

            user = User.query.filter_by(api_key=api_key).first()

            if not user:
                return jsonify({'message': 'Invalid API key'}), 401

            if user.permission_level not in permission_level:
                return jsonify({'message': 'Insufficient permissions'}), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator

