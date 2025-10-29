"""
Agent Management and Keycloak Synchronization Routes
Agents are system users from Keycloak with settings stored in Codex
"""

import requests as http_requests
from datetime import datetime
from flask import request, jsonify, render_template, g
from app import app
from app.auth import token_required, admin_required
from extensions import db
from models import Agent


def get_keycloak_admin_token():
    """Get admin token for Keycloak API calls"""
    keycloak_url = app.config.get('KEYCLOAK_SERVER_URL', 'http://localhost:8080')

    # Use admin credentials from config or environment
    admin_user = app.config.get('KEYCLOAK_ADMIN_USER', 'admin')
    admin_pass = app.config.get('KEYCLOAK_ADMIN_PASS', 'admin')

    token_url = f"{keycloak_url}/realms/master/protocol/openid-connect/token"

    try:
        response = http_requests.post(token_url, data={
            'client_id': 'admin-cli',
            'username': admin_user,
            'password': admin_pass,
            'grant_type': 'password'
        }, timeout=5)

        if response.status_code == 200:
            return response.json().get('access_token')
    except Exception as e:
        app.logger.error(f"Failed to get Keycloak admin token: {e}")

    return None


@app.route('/agents')
@admin_required
def agents_dashboard():
    """Agents management dashboard - admin only"""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    return render_template('agents/list.html', user=g.user)


@app.route('/settings')
@token_required
def user_settings():
    """User settings page - theme preferences, etc."""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    return render_template('settings.html', user=g.user)


# ============================================================
# Agent Synchronization API
# ============================================================

@app.route('/api/agents/sync', methods=['POST'])
@admin_required
def sync_agents_from_keycloak():
    """
    Sync agents from Keycloak into Codex database.
    Creates/updates agents, preserving their Codex-specific settings.
    """
    token = get_keycloak_admin_token()
    if not token:
        return {'error': 'Failed to authenticate with Keycloak'}, 500

    keycloak_url = app.config.get('KEYCLOAK_SERVER_URL', 'http://localhost:8080')
    realm = app.config.get('KEYCLOAK_REALM', 'hivematrix')

    users_url = f"{keycloak_url}/admin/realms/{realm}/users"
    headers = {'Authorization': f'Bearer {token}'}

    try:
        response = http_requests.get(users_url, headers=headers, timeout=10)

        if response.status_code != 200:
            return {'error': 'Failed to fetch users from Keycloak'}, response.status_code

        keycloak_users = response.json()

        synced = 0
        created = 0
        updated = 0
        errors = []

        now = datetime.utcnow().isoformat()

        for kc_user in keycloak_users:
            try:
                # Check if agent exists
                agent = Agent.query.filter_by(keycloak_id=kc_user['id']).first()

                if agent:
                    # Update existing agent (preserve settings like theme_preference)
                    agent.username = kc_user.get('username', agent.username)
                    agent.email = kc_user.get('email', agent.email)
                    agent.first_name = kc_user.get('firstName', '')
                    agent.last_name = kc_user.get('lastName', '')
                    agent.enabled = kc_user.get('enabled', True)
                    agent.updated_at = now
                    agent.last_synced_at = now
                    updated += 1
                else:
                    # Create new agent
                    agent = Agent(
                        keycloak_id=kc_user['id'],
                        username=kc_user.get('username', ''),
                        email=kc_user.get('email', ''),
                        first_name=kc_user.get('firstName', ''),
                        last_name=kc_user.get('lastName', ''),
                        enabled=kc_user.get('enabled', True),
                        theme_preference='light',  # Default theme
                        created_at=now,
                        updated_at=now,
                        last_synced_at=now
                    )
                    db.session.add(agent)
                    created += 1

                synced += 1

            except Exception as e:
                errors.append(f"Error syncing user {kc_user.get('username')}: {str(e)}")
                app.logger.error(f"Error syncing user {kc_user.get('username')}: {e}")

        # Commit all changes
        db.session.commit()

        return jsonify({
            'success': True,
            'synced': synced,
            'created': created,
            'updated': updated,
            'total_keycloak_users': len(keycloak_users),
            'errors': errors if errors else None
        })

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Failed to sync agents: {e}")
        return {'error': f'Failed to sync agents: {str(e)}'}, 500


# ============================================================
# Agent Management API
# ============================================================

@app.route('/api/agents', methods=['GET'])
@admin_required
def list_agents():
    """List all agents in Codex database"""
    agents = Agent.query.all()
    return jsonify({
        'agents': [agent.to_dict() for agent in agents],
        'total': len(agents)
    })


@app.route('/api/agents/<keycloak_id>', methods=['GET'])
@admin_required
def get_agent(keycloak_id):
    """Get a specific agent by Keycloak ID"""
    agent = Agent.query.filter_by(keycloak_id=keycloak_id).first()

    if not agent:
        return {'error': 'Agent not found'}, 404

    return jsonify(agent.to_dict())


@app.route('/api/agents/<keycloak_id>/settings', methods=['PUT'])
@admin_required
def update_agent_settings(keycloak_id):
    """
    Update agent settings (theme, etc.)
    This endpoint is for admins to manage agent settings.
    """
    agent = Agent.query.filter_by(keycloak_id=keycloak_id).first()

    if not agent:
        return {'error': 'Agent not found'}, 404

    data = request.get_json()
    if not data:
        return {'error': 'No data provided'}, 400

    # Update allowed settings
    if 'theme_preference' in data:
        theme = data['theme_preference']
        if theme not in ['light', 'dark']:
            return {'error': 'Invalid theme. Must be "light" or "dark"'}, 400
        agent.theme_preference = theme

    agent.updated_at = datetime.utcnow().isoformat()

    try:
        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'Agent settings updated',
            'agent': agent.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Failed to update agent settings: {e}")
        return {'error': f'Failed to update settings: {str(e)}'}, 500


# ============================================================
# User Settings API (for authenticated users to manage their own settings)
# ============================================================

@app.route('/api/my/settings', methods=['GET'])
@token_required
def get_my_settings():
    """
    Get current user's settings.
    Returns theme preference and other settings for the authenticated user.
    """
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    # Look up agent by email from token
    user_email = g.user.get('email')

    if not user_email:
        return {'error': 'User email not found in token'}, 400

    agent = Agent.query.filter_by(email=user_email).first()

    if not agent:
        # Agent not yet synced, return defaults
        return jsonify({
            'theme_preference': 'light',
            'knowledgetree_view_preference': 'grid',
            'synced': False
        })

    return jsonify({
        'theme_preference': agent.theme_preference,
        'knowledgetree_view_preference': agent.knowledgetree_view_preference,
        'username': agent.username,
        'email': agent.email,
        'synced': True
    })


@app.route('/api/my/settings', methods=['PUT'])
@token_required
def update_my_settings():
    """
    Update current user's settings.
    Allows authenticated users to change their own theme preference.
    """
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    user_email = g.user.get('email')

    if not user_email:
        return {'error': 'User email not found in token'}, 400

    agent = Agent.query.filter_by(email=user_email).first()

    if not agent:
        return {'error': 'Agent not found. Please ask admin to sync agents from Keycloak.'}, 404

    data = request.get_json()
    if not data:
        return {'error': 'No data provided'}, 400

    # Update theme preference
    if 'theme_preference' in data:
        theme = data['theme_preference']
        if theme not in ['light', 'dark']:
            return {'error': 'Invalid theme. Must be "light" or "dark"'}, 400
        agent.theme_preference = theme

    # Update KnowledgeTree view preference
    if 'knowledgetree_view_preference' in data:
        view = data['knowledgetree_view_preference']
        if view not in ['grid', 'tree']:
            return {'error': 'Invalid view preference. Must be "grid" or "tree"'}, 400
        agent.knowledgetree_view_preference = view

    agent.updated_at = datetime.utcnow().isoformat()

    try:
        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'Settings updated successfully',
            'theme_preference': agent.theme_preference,
            'knowledgetree_view_preference': agent.knowledgetree_view_preference
        })
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Failed to update user settings: {e}")
        return {'error': f'Failed to update settings: {str(e)}'}, 500


# ============================================================
# Public Theme API (for Nexus to query)
# ============================================================

@app.route('/api/public/user/theme', methods=['GET'])
@token_required
def get_user_theme():
    """
    Get user's theme preference.
    This endpoint is called by Nexus to determine which theme to inject.
    Requires service token authentication.
    """
    # Get email from query params
    user_email = request.args.get('email')

    if not user_email:
        # Default to light theme if no user email
        return jsonify({'theme': 'light', 'source': 'default'})

    agent = Agent.query.filter_by(email=user_email).first()

    if not agent:
        # Agent not synced yet, return default
        return jsonify({'theme': 'light', 'source': 'default'})

    return jsonify({
        'theme': agent.theme_preference,
        'source': 'codex',
        'email': agent.email
    })
