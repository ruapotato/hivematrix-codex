"""
Service-to-Service Authentication Helper for Nexus
"""

import requests
from flask import current_app

def call_service(service_name, path, method='GET', **kwargs):
    """
    Makes an authenticated request to another HiveMatrix service.
    This uses Core to mint a service token for authentication.
    """
    services = current_app.config.get('SERVICES', {})
    if service_name not in services:
        raise ValueError(f"Service '{service_name}' not found in configuration")

    service_url = services[service_name]['url']
    core_url = current_app.config.get('CORE_SERVICE_URL')
    calling_service = current_app.config.get('SERVICE_NAME', 'nexus')

    # Get a service token from Core
    token_response = requests.post(
        f"{core_url}/service-token",
        json={
            'calling_service': calling_service,
            'target_service': service_name
        },
        timeout=5
    )

    if token_response.status_code != 200:
        raise Exception(f"Failed to get service token from Core: {token_response.text}")

    token = token_response.json()['token']

    # Make the request with auth header
    url = f"{service_url}{path}"
    headers = kwargs.pop('headers', {})
    headers['Authorization'] = f'Bearer {token}'

    response = requests.request(
        method=method,
        url=url,
        headers=headers,
        **kwargs
    )

    return response
