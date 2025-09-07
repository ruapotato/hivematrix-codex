from flask import Blueprint, request, redirect, url_for, flash
from models import db, User
from decorators import admin_required
from flask_login import current_user

users_bp = Blueprint('users', __name__, url_prefix='/users')

@users_bp.route('/add', methods=['POST'])
@admin_required
def add_user():
    """Adds a new internal application user."""
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    permission_level = request.form.get('permission_level')

    if not all([username, email, password, permission_level]):
        flash('All fields are required to add a new user.', 'danger')
        return redirect(url_for('settings.settings_page'))

    if User.query.filter((User.username == username) | (User.email == email)).first():
        flash('A user with that username or email already exists.', 'danger')
    else:
        new_user = User(
            username=username,
            email=email,
            permission_level=permission_level
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash(f"User '{username}' created successfully.", 'success')

    return redirect(url_for('settings.settings_page'))

@users_bp.route('/edit/<int:user_id>', methods=['POST'])
@admin_required
def edit_user(user_id):
    """Edits an existing internal application user's details."""
    user = db.session.get(User, user_id)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('settings.settings_page'))

    # The primary admin (user ID 1) cannot be edited.
    if user.id == 1:
        flash('The primary admin user cannot be modified.', 'danger')
        return redirect(url_for('settings.settings_page'))

    username = request.form.get('username')
    email = request.form.get('email')
    permission_level = request.form.get('permission_level')

    # Check if new username or email is already taken by another user
    if User.query.filter(User.username == username, User.id != user_id).first():
        flash(f"Username '{username}' is already in use.", 'danger')
    elif User.query.filter(User.email == email, User.id != user_id).first():
        flash(f"Email '{email}' is already in use.", 'danger')
    else:
        user.username = username
        user.email = email
        user.permission_level = permission_level
        db.session.commit()
        flash('User updated successfully.', 'success')

    return redirect(url_for('settings.settings_page'))


@users_bp.route('/delete/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    """Deletes an internal application user."""
    if user_id == 1:
        flash('The primary admin user cannot be deleted.', 'danger')
        return redirect(url_for('settings.settings_page'))

    if user_id == current_user.id:
        flash('You cannot delete your own user account.', 'danger')
        return redirect(url_for('settings.settings_page'))

    user = db.session.get(User, user_id)
    if user:
        db.session.delete(user)
        db.session.commit()
        flash('User deleted successfully.', 'success')
    else:
        flash('User not found.', 'danger')

    return redirect(url_for('settings.settings_page'))

@users_bp.route('/generate_api_key/<int:user_id>', methods=['POST'])
@admin_required
def generate_api_key(user_id):
    """Generates a new API key for a user."""
    user = db.session.get(User, user_id)
    if user:
        user.regenerate_api_key()
        db.session.commit()
        flash(f"New API Key for {user.username}: {user.api_key}. Please copy it now, as it will not be shown again.", 'success')
    else:
        flash('User not found.', 'danger')
    return redirect(url_for('settings.settings_page'))
