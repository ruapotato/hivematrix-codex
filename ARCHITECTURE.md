
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
    

## 4. Production Deployment & Scalability

To transition from the Flask development server (`app.run()`) to a commercial-grade platform capable of supporting 50+ concurrent technicians, the following production stack is required for each client's VPS.

### 4.1. The Production Stack

-   **Database: PostgreSQL**
    
    -   **Why:** SQLite is not suitable for concurrent multi-user write operations. PostgreSQL is a robust, open-source database that handles high concurrency with ease and is the industry standard for scalable web applications.
        
    -   **Action:** Each module that requires a database (including Nexus) should connect to its own PostgreSQL database instance.
        
-   **WSGI Server: Gunicorn**
    
    -   **Why:** The Flask development server is single-threaded. Gunicorn is a production-ready WSGI server that runs multiple Python processes ("workers") to handle simultaneous user requests efficiently.
        
    -   **Action:** Launch each Flask application using a Gunicorn command, e.g., `gunicorn --workers 4 --bind 127.0.0.1:5000 main:app`.
        
-   **Reverse Proxy: Nginx**
    
    -   **Why:** Exposing Gunicorn directly to the internet is inefficient and insecure. Nginx sits in front of all Gunicorn processes, handling incoming web traffic, managing SSL encryption, serving static files directly, and proxying application requests to the appropriate Gunicorn worker.
        
    -   **Action:** Configure Nginx with `server` blocks for Nexus and each module, proxying requests to their respective Gunicorn instances running on different local ports.
        

### 4.2. Deployment on a VPS

A typical deployment script for a new client on a fresh VPS (e.g., Ubuntu) would perform these steps:

1.  Install system packages (Nginx, PostgreSQL, Python, etc.).
    
2.  Create PostgreSQL databases and users for Nexus and each module.
    
3.  Clone the Git repositories for Nexus and all required modules.
    
4.  Set up Python virtual environments and install dependencies (`pip install -r requirements.txt`).
    
5.  Run the `init_db.py` script for each service to create schemas and default data.
    
6.  Configure Nginx to act as a reverse proxy for all services.
    
7.  Create and enable `systemd` service files to run each Gunicorn process as a background service and ensure they start on boot.
    

## 5. Building a New Module: Code Template

This section provides the boilerplate code to create a new module, using the **Wiki** service as an example.

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
gunicorn         # For production deployment

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
            # Call Nexus to get a JWT with the user's credentials
            response = requests.post(
                f"{NEXUS_API_URL}/token", 
                json={'username': username, 'password': password}, 
                timeout=10, 
                verify=False # Set to True in production with a real SSL cert
            )
            
            # If authentication with Nexus is successful, create a local session
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

### Step 4: Authenticated API Calls

A robust helper function is the best way to manage API calls to Nexus or other modules. This centralizes error handling and authentication logic.

Here is a complete example for a `routes/wiki.py` file demonstrating this pattern.

```
# /hivematrix-wiki/routes/wiki.py
from flask import Blueprint, render_template, session, abort, flash, request, redirect, url_for
import requests
import sys

# Assume models.py defines a 'WikiArticle' model for this module's database
# from .. import db
# from ..models import WikiArticle

# This URL should point to the Nexus instance on the same VPS
NEXUS_API_URL = '[https://127.0.0.1:5000/api](https://127.0.0.1:5000/api)'
wiki_bp = Blueprint('wiki', __name__, url_prefix='/wiki')

def nexus_api_request(method, endpoint, json_data=None):
    """
    A centralized helper function for making authenticated API calls to Nexus.
    
    :param method: HTTP method (GET, POST, PUT, DELETE)
    :param endpoint: The API endpoint path (e.g., 'companies')
    :param json_data: A dictionary for the JSON payload for POST/PUT requests
    :return: The JSON response as a dictionary, or None if an error occurs.
    """
    token = session.get('nexus_token')
    if not token:
        # If the token is missing, force the user to log in again.
        flash("Your session has expired. Please log in again.", "danger")
        abort(redirect(url_for('auth.login')))

    headers = {'Authorization': f'Bearer {token}'}
    try:
        response = requests.request(
            method,
            f"{NEXUS_API_URL}/{endpoint}",
            headers=headers,
            json=json_data,
            verify=False,  # Set to True in production with a real SSL cert
            timeout=30
        )
        response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)
        
        # Handle cases where the response might be empty (e.g., a 204 No Content)
        if response.status_code == 204:
            return None
        
        return response.json()

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401: # Unauthorized
            session.clear()
            flash("Your session token is invalid or has expired. Please log in again.", "danger")
            abort(redirect(url_for('auth.login')))
        else:
            print(f"HTTP Error calling Nexus endpoint '{endpoint}': {e}", file=sys.stderr)
            flash(f"An error occurred while communicating with Nexus ({e.response.status_code}).", "danger")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error calling Nexus endpoint '{endpoint}': {e}", file=sys.stderr)
        flash("A critical error occurred: Could not connect to the Nexus service.", "danger")
        return None

@wiki_bp.route('/dashboard')
def dashboard():
    """Example of a GET request to fetch a list of all companies."""
    companies = nexus_api_request('GET', 'companies')
    if companies is None:
        # The helper function flashes an error, so we just need to handle the None case.
        companies = []
    
    # You would also fetch articles from the Wiki's own database here.
    # recent_articles = WikiArticle.query.order_by(WikiArticle.updated_at.desc()).limit(10).all()
    
    return render_template('wiki_dashboard.html', companies=companies)

@wiki_bp.route('/company/<account_number>')
def company_wiki(account_number):
    """Example of a GET request for a specific item, combined with local data."""
    company = nexus_api_request('GET', f'companies/{account_number}')
    if company is None:
        return redirect(url_for('wiki.dashboard'))

    # Fetch articles from this module's database that are linked to the company
    # company_articles = WikiArticle.query.filter_by(company_account_number=account_number).all()

    return render_template('company_wiki.html', company=company)

@wiki_bp.route('/article/new', methods=['POST'])
def create_article():
    """Example of a POST request to send data (hypothetically)."""
    form_data = request.form
    company_account_number = form_data.get('company_account_number')

    # First, verify the company exists in Nexus before saving to our local DB
    company = nexus_api_request('GET', f'companies/{company_account_number}')
    if company:
        # Logic to save the new wiki article to the Wiki's PostgreSQL database
        # new_article = WikiArticle(title=form_data.get('title'), content=form_data.get('content'), company_account_number=company_account_number)
        # db.session.add(new_article)
        # db.session.commit()
        flash("Article created successfully!", "success")
    else:
        # The helper function will have already flashed an error if the API call failed
        flash("Could not create article because the selected company was not found.", "warning")

    return redirect(url_for('wiki.company_wiki', account_number=company_account_number))

```

### Step 5: Main Application File (`main.py`)

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

# The main entry point for Gunicorn
app = create_app()

if __name__ == '__main__':
    # This block is for development only
    app.run(host='0.0.0.0', port=5003, debug=True)

```

## 6. Architecture Best Practices

-   **Nexus is the Source of Truth for Identity.** Use Nexus to manage users, permissions, and basic company/contact info. Do not duplicate this data.
    
-   **Modules Own Their Domain Data.** All specialized data and configuration must live in the module's own database. This keeps services decoupled and independently manageable.
    
-   **Communicate via APIs.** Modules should communicate with Nexus and with each other exclusively through REST APIs. Never allow one module to directly access another's database.
    
-   **Design for Bulk Operations.** When adding new endpoints to Nexus or other modules, favor creating summary/bulk endpoints (like `/api/billing_summary`) over endpoints that return single items. This prevents the "N+1 query problem" where a module has to make hundreds of calls to build a single page.
    
-   **Stateless Authentication.** The JWT approach is stateless. Services validate tokens without needing to check back with a central session store, which enhances scalability.
    

By following this guide, we can ensure that the HiveMatrix ecosystem remains robust, scalable, and easy to develop for years to come.
