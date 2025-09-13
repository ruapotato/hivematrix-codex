
# HiveMatrix Microservice Architecture Guide

**Author:** David Hamner & Gemini **Last Updated:** September 12, 2025

## 1. Introduction

Welcome to the HiveMatrix ecosystem. This document outlines the microservice architecture for the HiveMatrix suite of tools, which will be developed under an open-core model for Professional Services Automation (PSA). The goal of this architecture is to create a suite of specialized, maintainable, and scalable applications that work together seamlessly.

The core of this ecosystem is **Nexus**, which acts as the central hub for user identity and authentication. All other applications, referred to as **Modules** (e.g., Treasury, Wiki), are standalone services that connect to Nexus to authenticate users and then perform their specialized functions, managing their own data and logic.

This guide serves as the foundational blueprint for developing any new module within the HiveMatrix ecosystem.

## 2. Core Concepts

### 2.1. Nexus: The Central User & Authentication Hub

Nexus is the **identity and directory service** for the entire HiveMatrix ecosystem. It is not a monolithic data repository. Its primary responsibilities are narrowly focused:

-   **User Directory:** To be the master database for user accounts, permissions, and basic profile information. **A user in Nexus is a user in all modules.**
    
-   **Central Address Book:** To provide a simple, referenceable directory of core entities like Companies and Contacts. It holds just enough information for other modules to identify these entities.
    
-   **Authentication Service:** To manage user credentials and issue JSON Web Tokens (JWTs) for secure, stateless authentication across the entire suite of applications.
    
-   **Core Directory API:** To expose the user, company, and contact directories through a secure REST API.
    

Nexus **does not** store module-specific data (e.g., billing configurations, wiki articles, ticket histories). Its purpose is to answer the questions: "Who is this user?" and "What basic entities exist in our MSP?".

### 2.2. Modules: The Specialized Services

A Module is a standalone Flask application that performs a specific business function. Each module is an expert in its own domain.

**Key Principles of a Module:**

-   **Standalone:** It runs as its own process, typically on a different port than Nexus and other modules.
    
-   **Nexus-Authenticated:** It uses Nexus _only_ for user login and retrieving basic directory information. It does not rely on Nexus for its own business logic.
    
-   **Owns Its Data:** Each module **must have its own database** (e.g., `treasury.db`, `wiki.db`). This database stores all data and configuration specific to that module's domain. For example, Treasury's database contains billing plans, while the Wiki's database will contain context articles.
    
-   **Exposes Its Own API:** A module can, and should, expose its own API endpoints for other modules to consume. This allows for powerful inter-service communication. For example, the Wiki module will expose an API for a future Ticketing module to retrieve AI context automatically.
    

## 3. The Architecture Diagram

The relationship is not a simple hub-and-spoke. While Nexus is central to authentication, modules are peers that can communicate with Nexus and with each other.


## 4. The Authentication Flow

Authentication remains centralized through Nexus to provide a single sign-on (SSO) experience.

1.  **Login Request:** A user enters their credentials into a Module's login form (e.g., Wiki's login page).
    
2.  **Token Generation:** The Module sends these credentials to the Nexus `/api/token` endpoint.
    
3.  **Validation:** Nexus validates the credentials against its user database.
    
4.  **Token Issuance:** If valid, Nexus generates a signed JWT containing the user's ID and permission level and sends it back to the Module.
    
5.  **Session Storage:** The Module receives the JWT and stores it securely in the user's server-side session.
    
6.  **Authenticated API Calls:** For every subsequent request that requires data from Nexus (or another module), the Module attaches the JWT to the `Authorization: Bearer <token>` header of its API call. The receiving service validates this token to authorize the request.
    

## 5. Building a New Module: A Step-by-Step Guide

This section provides the boilerplate and steps to create a new module, using the **Wiki** service as an example.

### Step 1: Project Structure

Create a new directory for your module and set up a basic Flask project structure.

```
/hivematrix-wiki/
├── main.py                 # Main Flask application file
├── init_db.py              # For creating the local wiki.db
├── models.py               # (Optional) SQLAlchemy models for wiki.db
├── requirements.txt
├── routes/
│   ├── __init__.py
│   ├── auth.py             # Handles login/logout against Nexus
│   └── wiki.py             # Your module's specific routes
└── templates/
    ├── layout.html
    ├── login.html
    └── wiki_dashboard.html

```

### Step 2: Dependencies (`requirements.txt`)

Your new module will need a few key libraries.

```
Flask
requests
PyJWT
cryptography
# Add any other libraries your module needs, e.g., Flask-SQLAlchemy

```

### Step 3: Authentication (`routes/auth.py`)

This is the standard authentication blueprint that every module should use. It handles communication with the Nexus `/api/token` endpoint.

```
# /hivematrix-wiki/routes/auth.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import requests
import warnings

# Suppress InsecureRequestWarning for self-signed certs in dev
from requests.packages.urllib3.exceptions import InsecureRequestWarning
warnings.simplefilter('ignore', InsecureRequestWarning)

# IMPORTANT: Point this to your running Nexus instance
NEXUS_API_URL = '[https://127.0.0.1:5000/api](https://127.0.0.1:5000/api)'

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'nexus_token' in session:
        return redirect(url_for('wiki.dashboard')) # Redirect to your module's main page
        
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        try:
            response = requests.post(
                f"{NEXUS_API_URL}/token", 
                json={'username': username, 'password': password}, 
                timeout=10, 
                verify=False # Set to True in production with a real SSL cert
            )
            
            if response.status_code == 200:
                session['nexus_token'] = response.json().get('token')
                session['username'] = username
                flash('Login successful!', 'success')
                return redirect(url_for('wiki.dashboard')) # Redirect to your module's main page
            else:
                flash('Invalid username or password.', 'danger')

        except requests.exceptions.RequestException as e:
            flash(f"Error connecting to Nexus authentication service: {e}", 'danger')
            
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('auth.login'))

```

### Step 4: Making Authenticated API Calls

Create a helper function to easily make authenticated requests to the Nexus API from anywhere in your module.

```
# Example within /hivematrix-wiki/routes/wiki.py
from flask import Blueprint, render_template, session, abort
import requests

NEXUS_API_URL = '[https://127.0.0.1:5000/api](https://127.0.0.1:5000/api)'
wiki_bp = Blueprint('wiki', __name__)

def get_nexus_data(endpoint):
    """Helper to fetch data from Nexus using the stored token."""
    token = session.get('nexus_token')
    if not token:
        abort(401) # Unauthorized

    headers = {'Authorization': f'Bearer {token}'}
    try:
        response = requests.get(f"{NEXUS_API_URL}/{endpoint}", headers=headers, verify=False, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching from Nexus endpoint '{endpoint}': {e}")
        return None

@wiki_bp.route('/dashboard')
def dashboard():
    # Use the helper to get data
    companies = get_nexus_data('companies')
    if companies is None:
        companies = [] # Handle API error gracefully
    
    return render_template('wiki_dashboard.html', companies=companies)

```

### Step 5: Main Application File (`main.py`)

Tie everything together in your module's `main.py`.

```
# /hivematrix-wiki/main.py
import os
from flask import Flask, session, redirect, url_for, request

from routes.auth import auth_bp
from routes.wiki import wiki_bp

def create_app():
    app = Flask(__name__)
    app.secret_key = os.urandom(24)

    app.register_blueprint(auth_bp)
    app.register_blueprint(wiki_bp)

    @app.before_request
    def check_auth():
        # Protect all routes except for the login page and static files
        if 'nexus_token' not in session and request.endpoint not in ['auth.login', 'static']:
            return redirect(url_for('auth.login'))

    @app.route('/')
    def index():
        return redirect(url_for('wiki.dashboard'))

    return app

if __name__ == '__main__':
    app = create_app()
    # Run on a different port than Nexus!
    app.run(host='0.0.0.0', port=5003, debug=True)

```

## 6. Architecture Best Practices

-   **Nexus is the Source of Truth for Identity.** Use Nexus to manage users, permissions, and basic company/contact info. Do not duplicate this data.
    
-   **Modules Own Their Domain Data.** All specialized data and configuration must live in the module's own database. This keeps services decoupled and independently manageable.
    
-   **Communicate via APIs.** Modules should communicate with Nexus and with each other exclusively through REST APIs. Never allow one module to directly access another's database.
    
-   **Design for Bulk Operations.** When adding new endpoints to Nexus or other modules, favor creating summary/bulk endpoints (like `/api/billing_summary`) over endpoints that return single items. This prevents the "N+1 query problem" where a module has to make hundreds of calls to build a single page.
    
-   **Stateless Authentication.** The JWT approach is stateless. Services validate tokens without needing to check back with a central session store, which enhances scalability.
    

By following this guide, we can ensure that the HiveMatrix ecosystem remains robust, scalable, and easy to develop for years to come.
