from functools import wraps
from flask import request, jsonify, session, flash, redirect, url_for, current_app
from models import User
import jwt

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'permission_level' not in session or session['permission_level'] != 'admin':
            flash("Admin access is required for this page.", "danger")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def token_required(permission_level=None):
    """
    A decorator factory that protects API endpoints using JWT or an API Key.
    It takes a list of allowed permission levels.
    """
    if permission_level is None:
        permission_level = ['admin']

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            current_user = None
            
            # 1. Check for Service Account API Key first
            api_key = request.headers.get('X-API-Key')
            if api_key:
                user_by_key = User.query.filter_by(api_key=api_key).first()
                if user_by_key:
                    current_user = user_by_key
                else:
                    return jsonify({'message': 'Invalid API Key'}), 401
            
            # 2. If no valid API Key, check for JWT (user token)
            else:
                token = None
                if 'Authorization' in request.headers and request.headers['Authorization'].startswith('Bearer '):
                    token = request.headers['Authorization'].split(" ")[1]

                if not token:
                    return jsonify({'message': 'Token is missing'}), 401

                try:
                    data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
                    user_by_jwt = User.query.get(data['user_id'])
                    if not user_by_jwt:
                        return jsonify({'message': 'User not found'}), 401
                    current_user = user_by_jwt

                except jwt.ExpiredSignatureError:
                    return jsonify({'message': 'Token has expired'}), 401
                except jwt.InvalidTokenError:
                    return jsonify({'message': 'Token is invalid'}), 401
            
            # 3. Check permissions
            if current_user and current_user.permission_level not in permission_level:
                return jsonify({'message': 'Insufficient permissions'}), 403

            # Pass the authenticated user object to the decorated function
            return f(current_user, *args, **kwargs)
        return decorated_function
    return decorator

