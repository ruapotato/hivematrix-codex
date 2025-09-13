
# HiveMatrix Microservice Architecture Guide

**Author:** David Hamner & Gemini **Last Updated:** September 12, 2025

## 1. Introduction & Core Philosophy

Welcome to the HiveMatrix ecosystem. This document outlines the official microservice architecture for the HiveMatrix PSA, a powerful, multi-tenant Professional Services Automation platform designed for commercial service providers.

**Nexus is the foundational, required component of the entire ecosystem.** It serves as the central "address book" and identity provider. All other applications, referred to as **Modules** (e.g., Treasury, Wiki), are standalone services that connect to Nexus for authentication and basic directory information before executing their specialized functions.

This guide is the blueprint for developing any new module. Adherence to this architecture ensures that the HiveMatrix platform remains scalable, secure, and maintainable as it grows. Because Nexus is the core, this guide and other primary setup documentation will be maintained within the Nexus repository.

## 2. Component Responsibilities

### 2.1. Nexus: The Central User & Directory Hub

Nexus is the **identity and directory service** for the entire HiveMatrix ecosystem. It is not a monolithic data repository. Its primary responsibilities are narrowly focused:

-   **User Directory:** The master database for user accounts, permissions, and basic profile information. **A user in Nexus is a user in all modules.**
    
-   **Central Address Book:** Provides a simple, referenceable directory of core entities like Companies and Contacts. It holds just enough information for other modules to identify these entities.
    
-   **Authentication Service:** Manages user credentials and issues JSON Web Tokens (JWTs) for secure, stateless authentication across the entire suite of applications.
    
-   **Core Directory API:** Exposes the user, company, and contact directories through a secure REST API.
    

Nexus **does not** store module-specific data (e.g., billing configurations, wiki articles, ticket histories). Its purpose is to answer the questions: "Who is this user?" and "What basic entities exist in our PSA?".

### 2.2. Modules: The Specialized Services

A Module is a standalone Flask application that performs a specific business function. Each module is an expert in its own domain.

**Key Principles of a Module:**

-   **Standalone:** It runs as its own process, typically on a different port than Nexus and other modules.
    
-   **Nexus-Authenticated:** It uses Nexus _only_ for user login and retrieving basic directory information. It does not rely on Nexus for its own business logic.
    
-   **Owns Its Data:** Each module **must have its own database** (e.g., `treasury_db`, `wiki_db` in PostgreSQL). This database stores all data and configuration specific to that module's domain.
    
-   **Exposes Its Own API:** A module can, and should, expose its own API endpoints for other modules to consume. This allows for powerful inter-service communication.
    

## 3. The Authentication Flow

Authentication is centralized through Nexus to provide a single sign-on (SSO) experience.

1.  **Login Request:** A user enters credentials into a Module's login form.
    
2.  **Token Generation:** The Module sends the credentials to the Nexus `/api/token` endpoint.
    
3.  **Validation & Issuance:** Nexus validates the credentials and, if successful, generates and returns a signed JWT.
    
4.  **Session Storage:** The Module receives the JWT and stores it in the user's server-side session.
    
5.  **Authenticated API Calls:** For every subsequent API call to Nexus or another module, the calling module attaches the JWT to the `Authorization: Bearer <token>` header.
    

## 4. Deployment Architecture

This architecture is designed for simplicity and robustness, using a consistent set of tools for both production and development.

### 4.1. The Technology Stack

-   **Database: PostgreSQL**
    
    -   **Why:** A powerful, open-source database that handles high-concurrency reads and writes, essential for a multi-user PSA.
        
-   **WSGI Server: Waitress**
    
    -   **Why:** A production-quality, pure-Python WSGI server. Its key advantage is simplicity and cross-platform compatibility, running identically on both Windows and Linux without requiring compilers or complex dependencies. It will be used for both development and production.
        
-   **Reverse Proxy: Caddy**
    
    -   **Why:** A modern, secure web server that is significantly easier to configure than alternatives. Its primary benefit is **automatic HTTPS**, meaning it will automatically obtain and renew SSL certificates.
        

### 4.2. Deployment Models

-   **Production (Linux VPS):** The full stack is used. **Caddy** acts as the public-facing web server, handling HTTPS and proxying requests to the various **Waitress** processes. Each Waitress process runs a module and is bound to a different `localhost` port (e.g., 5000, 5001). This setup is secure, as the application servers are not directly exposed to the internet.
    
-   **Development (Windows/Linux):** For simplicity, developers run **Waitress** directly, bound to `localhost`. This allows for rapid testing without needing to configure a reverse proxy. Caddy is only required for production-like environments or when testing public-facing access.
    

### 4.3. Deployment Steps on a VPS

A typical deployment script for a new client on a fresh Linux VPS would perform these steps:

1.  Install system packages (Caddy, PostgreSQL, Python, etc.).
    
2.  **Create empty PostgreSQL databases and users** for Nexus and each required module.
    
3.  Clone the Git repositories for Nexus and all required modules.
    
4.  Set up Python virtual environments and install dependencies (`pip install -r requirements.txt`).
    
5.  **Run each module's `init_db.py` script.** This script is responsible for connecting to its designated PostgreSQL database and creating the necessary **tables and schema**.
    
6.  Create a simple `Caddyfile` to configure the reverse proxy.
    
7.  Create and enable `systemd` service files to run each **Waitress** process as a background service.
    

### 4.4. Example Caddy Configuration

This `Caddyfile` showcases the simplicity of managing multiple services. Caddy automatically handles acquiring and renewing SSL certificates for each domain.

```
# /etc/caddy/Caddyfile

# Nexus Service (The Core)
nexus.your-client-domain.com {
    # Proxy requests to the Waitress process for Nexus
    reverse_proxy 127.0.0.1:5000
}

# Treasury Module
treasury.your-client-domain.com {
    reverse_proxy 127.0.0.1:5001
}

# Wiki Module
wiki.your-client-domain.com {
    reverse_proxy 127.0.0.1:5003
}

```

## 5. Building a New Module: Code Template

### Step 1: Project Structure

```
/hivematrix-wiki/
├── main.py
├── init_db.py
├── models.py
├── requirements.txt
└── routes/
    ├── __init__.py
    ├── auth.py
    └── wiki.py

```

### Step 2: Dependencies (`requirements.txt`)

```
Flask
requests
PyJWT
cryptography
psycopg2-binary  # For PostgreSQL
waitress         # For development and production

```

### Step 3: Authentication Blueprint (`routes/auth.py`)

```
# /hivematrix-wiki/routes/auth.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import requests
import warnings

# Suppress InsecureRequestWarning for self-signed certs in dev
from requests.packages.urllib3.exceptions import InsecureRequestWarning
warnings.simplefilter('ignore', InsecureRequestWarning)

# This URL should point to the Nexus instance on the same VPS
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

    # You will need to create a simple login.html template for your module
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('auth.login'))

```

### Step 4: Authenticated API Calls (`routes/wiki.py`)

```
# /hivematrix-wiki/routes/wiki.py
from flask import Blueprint, render_template, session, abort, flash
import requests
import warnings

# Suppress InsecureRequestWarning for self-signed certs in dev
from requests.packages.urllib3.exceptions import InsecureRequestWarning
warnings.simplefilter('ignore', InsecureRequestWarning)

# This URL should point to the Nexus instance on the same VPS
NEXUS_API_URL = '[https://127.0.0.1:5000/api](https://127.0.0.1:5000/api)'

wiki_bp = Blueprint('wiki', __name__)

def make_nexus_request(method, endpoint, json_data=None):
    """
    A robust helper function to make authenticated API requests to Nexus.
    Handles GET, POST, PUT, DELETE.
    """
    token = session.get('nexus_token')
    if not token:
        abort(401)  # Unauthorized

    headers = {'Authorization': f'Bearer {token}'}
    url = f"{NEXUS_API_URL}/{endpoint}"
    
    try:
        if method.upper() == 'GET':
            response = requests.get(url, headers=headers, verify=False, timeout=30)
        elif method.upper() == 'POST':
            response = requests.post(url, headers=headers, json=json_data, verify=False, timeout=30)
        # Add PUT, DELETE etc. as needed
        # elif method.upper() == 'PUT':
        #     response = requests.put(url, headers=headers, json=json_data, verify=False, timeout=30)
        
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error making {method} request to Nexus endpoint '{endpoint}': {e}")
        flash(f"Error communicating with Nexus: {e}", "danger")
        return None

@wiki_bp.route('/dashboard')
def dashboard():
    # Use the helper to get data from Nexus
    companies = make_nexus_request('GET', 'companies')
    
    if companies is None:
        # The helper function will have already flashed an error message
        companies = []

    # Example of combining Nexus data with this module's own data
    # (Assuming you have a WikiArticle model and database setup for this module)
    #
    # try:
    #     internal_articles = WikiArticle.query.filter_by(visibility='Internal').all()
    # except Exception as e:
    #     internal_articles = []
    #     flash(f"Error loading local wiki data: {e}", "danger")

    # You will need to create a wiki_dashboard.html template
    return render_template('wiki_dashboard.html', companies=companies)

```

### Step 5: Main Application File (`main.py`)

This file is now updated to show how you would run it with either the Flask dev server or Waitress.

```
# /hivematrix-wiki/main.py
import os
from flask import Flask, session, redirect, url_for, request
from routes.auth import auth_bp
from routes.wiki import wiki_bp

def create_app():
    app = Flask(__name__)
    app.secret_key = os.urandom(24)

    # In production, this would point to your PostgreSQL database
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://user:password@localhost/wiki_db'

    app.register_blueprint(auth_bp)
    app.register_blueprint(wiki_bp)

    @app.before_request
    def check_auth():
        if 'nexus_token' not in session and request.endpoint not in ['auth.login', 'static']:
            return redirect(url_for('auth.login'))

    @app.route('/')
    def index():
        return redirect(url_for('wiki.dashboard'))

    return app

# The main entry point for Waitress
app = create_app()

if __name__ == '__main__':
    # This block is for easy debugging with Flask's built-in server.
    # For development, it's recommended to run with Waitress directly.
    #
    # Development command:
    # waitress-serve --host 127.0.0.1 --port 5003 main:app
    
    print("Starting Flask development server...")
    app.run(host='0.0.0.0', port=5003, debug=True)

```

## 6. Architecture Best Practices

-   **Nexus is the Source of Truth for Identity.** Use Nexus to manage users, permissions, and basic company/contact info. Do not duplicate this data.
    
-   **Modules Own Their Domain Data.** All specialized data and configuration must live in the module's own database. This keeps services decoupled and independently manageable.
    
-   **Communicate via APIs.** Modules should communicate with Nexus and with each other exclusively through REST APIs. Never allow one module to directly access another's database.
    
-   **Design for Bulk Operations.** When adding new endpoints to Nexus or other modules, favor creating summary/bulk endpoints (like `/api/billing_summary`) over endpoints that return single items. This prevents the "N+1 query problem" where a module has to make hundreds of calls to build a single page.
    
-   **Stateless Authentication.** The JWT approach is stateless. Services validate tokens without needing to check back with a central session store, which enhances scalability.
    

## 7. HiveMatrix Module Ecosystem

This section outlines the planned modules for the HiveMatrix PSA and their standard internal port assignments. This structure allows for clear separation of concerns and independent development.

### How Multiple Services Work on One Port (443)

You might wonder how all these services running on different internal ports can be accessed securely through the standard HTTPS port (443). This is the primary job of the **Caddy reverse proxy**.

When a user visits `https://nexus.your-client-domain.com`, Caddy receives the request on port 443, handles the HTTPS encryption, and intelligently forwards (proxies) the request to the Nexus module running internally on port 5000. When they visit `https://treasury.your-client-domain.com`, Caddy does the same, but forwards it to the Treasury module on port 5001.

This setup provides a single, secure entry point for all applications, while allowing each service to run independently inside the server. The Caddy configuration in section 4.4 is the "map" that tells the proxy where to send the traffic.

### Standard Module Ports

-   **HiveMatrix Nexus (Port 5000)**
    
    -   _Description:_ A unified client database aggregating companies, assets, and contacts from RMM and ticketing APIs. The central hub for identity and directory services.
        
-   **HiveMatrix Treasury (Port 5001)**
    
    -   _Description:_ An internal billing engine for MSPs to manage service plans and generate client bill estimates.
        
-   **HiveMatrix Resolve (Port 5002)**
    
    -   _Description:_ An AI-first ticketing system that leverages context from the entire HiveMatrix for faster resolutions.
        
-   **HiveMatrix Archive (Port 5003)**
    
    -   _Description:_ A centralized internal knowledge base for MSP processes and client-specific documentation.
        
-   **HiveMatrix Dispatch (Port 5004)**
    
    -   _Description:_ An internal procurement tool for end-to-end tracking of the hardware and software order lifecycle.
        
-   **HiveMatrix Architect (Port 5005)**
    
    -   _Description:_ An internal project management framework for planning, tracking, and executing client-facing initiatives.
