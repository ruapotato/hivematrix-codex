
# HiveMatrix Microservice Architecture Guide

**Author:** David Hamner & Gemini **Last Updated:** September 13, 2025

## 1. Introduction & Core Philosophy

Welcome to the HiveMatrix ecosystem. This document outlines the official microservice architecture for the HiveMatrix PSA, a powerful, multi-tenant Professional Services Automation platform designed for commercial service providers.

**Nexus is the foundational, required component of the entire ecosystem.** It serves as the central "address book" and identity provider. All other applications, referred to as **Modules** (e.g., Resolve, Archive), are standalone services that connect to Nexus for authentication and basic directory information before executing their specialized functions.

This guide is the blueprint for developing any new module. Adherence to this architecture ensures that the HiveMatrix platform remains scalable, secure, and maintainable as it grows.

## 2. Component Responsibilities

### 2.1. Nexus: The Central User & Directory Hub

Nexus is the **identity and directory service** for the entire HiveMatrix ecosystem. Its primary responsibilities are narrowly focused:

-   **User Directory:** The master database for user accounts, permissions, and basic profile information. **A user in Nexus is a user in all modules.** This includes both human users who log into the web interfaces and non-human "service accounts" used for server-to-server communication.
    
-   **Central Address Book:** Provides a simple, referenceable directory of core entities like Companies, Contacts, and Assets.
    
-   **Authentication Service:** Manages user credentials (passwords for humans, API keys for services) and issues JSON Web Tokens (JWTs) for secure, stateless authentication for web sessions.
    
-   **Core Directory API:** Exposes the user, company, and contact directories through a secure REST API that accepts both JWTs and service account API keys.
    

Nexus **does not** store module-specific data (e.g., ticket histories, wiki articles). Its purpose is to answer the questions: "Who is this user/service?" and "What basic entities exist in our PSA?".

### 2.2. Modules: The Specialized Services

A Module is a standalone Flask application that performs a specific business function.

-   **Standalone:** It runs as its own process on a different port.
    
-   **Nexus-Authenticated:** It uses Nexus for all authentication and directory lookups.
    
-   **Owns Its Data:** Each module has its own PostgreSQL database (e.g., `resolve_db`).
    
-   **Standalone Initialization:** Each module must have an `init_db.py` script for interactive setup of its database connection and schema.
    

## 3. The Authentication Flow

Authentication is centralized through Nexus to provide a single source of truth for identity. There are two primary authentication flows.

### 3.1. User Authentication (Web UI)

This flow is used when a human user logs into any module's web interface.

1.  **Login Request:** A user enters their username and password into a Module's login form.
    
2.  **Token Generation:** The Module sends these credentials to the Nexus `/api/token` endpoint.
    
3.  **Validation & Issuance:** Nexus validates the credentials against its user database and, if successful, generates and returns a signed, short-lived JWT.
    
4.  **Session Storage:** The Module receives the JWT and stores it in the user's server-side session. It decodes the token to cache the user's role for local permission checks.
    
5.  **Subsequent Requests:** For the duration of the web session, the Module uses the stored user information. If it needs to make an API call to another module on the user's behalf, it would pass the JWT in the `Authorization` header.
    

### 3.2. Service-to-Service Authentication (Background Tasks)

This flow is used when a background process (like an email watcher) needs to communicate with an API securely without a human user present.

1.  **Service Account:** A special user account (e.g., `service_account`) is created in Nexus. This account has a long-lived, randomly generated **API Key** instead of a password.
    
2.  **Secure Configuration:** A Module (e.g., Resolve) stores this API key in its local `instance/resolve.conf` file.
    
3.  **API Request:** When the Module's background task needs to access Nexus data (e.g., to look up a contact by email), it makes a request to the Nexus API.
    
4.  **API Key Authentication:** Instead of a JWT, the Module includes the API key in a custom request header: `X-API-Key: <your_nexus_service_api_key>`.
    
5.  **Validation:** The Nexus API decorator first checks for this `X-API-Key` header. If present and valid, it grants the request the permissions of the associated service account. This method is prioritized over JWTs for API calls.
    

This model is more secure and robust because it eliminates the need to store passwords in configuration files and decouples background services from user login sessions.

## 4. Deployment Architecture

This architecture uses a consistent, simple, and robust set of tools.

-   **Database:** PostgreSQL
    
-   **WSGI Server:** Waitress (Pure-Python, cross-platform)
    
-   **Reverse Proxy:** Caddy (Modern, simple, with automatic HTTPS)
    

### 4.1. Example Caddy Configuration

This `Caddyfile` demonstrates how Caddy can manage multiple services on a single server, routing traffic based on the domain name and handling all SSL certificate management automatically.

```
# /etc/caddy/Caddyfile

# Nexus Service (The Core)
nexus.your-client-domain.com {
    reverse_proxy 127.0.0.1:5000
}

# Resolve Module (Ticketing)
resolve.your-client-domain.com {
    reverse_proxy 127.0.0.1:5002
}

# Archive Module (Wiki)
archive.your-client-domain.com {
    reverse_proxy 127.0.0.1:5003
}

```

## 5. Building a New Module: Code Template

This section provides the boilerplate code for a new module, `hivematrix-archive`.

### Step 1: Project Structure

```
/hivematrix-archive/
├── main.py
├── init_db.py
├── models.py
├── extensions.py
├── decorators.py
├── utils.py
├── requirements.txt
├── instance/
│   └── (empty, created by init_db.py)
├── routes/
│   ├── __init__.py
│   ├── auth.py
│   └── articles.py
└── templates/
    ├── base.html
    ├── login.html
    └── dashboard.html


```

### Step 2: Dependencies (`requirements.txt`)

```
Flask
Flask-SQLAlchemy
requests
PyJWT
cryptography
psycopg2-binary
waitress


```

### Step 3: Standalone Database Initializer (`init_db.py`)

This script is run once during setup. It is completely independent of the Flask app object.

```
# /hivematrix-archive/init_db.py
import os
import sys
import configparser
from getpass import getpass
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError

# Add current dir to path to allow imports from app modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from extensions import db
# Import your models here, e.g., from models import Article, Category

def get_db_credentials(config):
    # ... (omitted for brevity - same as Treasury's init_db.py) ...
    pass

def test_db_connection(creds):
    # ... (omitted for brevity - same as Treasury's init_db.py) ...
    pass

def init_db():
    instance_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
    if not os.path.exists(instance_path):
        os.makedirs(instance_path)

    config_path = os.path.join(instance_path, 'archive.conf')
    config = configparser.ConfigParser()

    if os.path.exists(config_path):
        config.read(config_path)

    # --- Get and save DB credentials ---
    # ... (omitted for brevity - same as Treasury's init_db.py) ...
    conn_string = "" # Placeholder for the actual connection string logic

    # --- Connect directly to the database to create tables ---
    engine = create_engine(conn_string)
    
    print("Initializing the database schema...")
    db.metadata.create_all(bind=engine)
    print("Database schema initialized.")

    # --- Add any default data needed for the module ---
    Session = sessionmaker(bind=engine)
    session = Session()
    # Example: if not session.query(Category).first():
    #     default_cat = Category(name='General')
    #     session.add(default_cat)
    #     session.commit()
    #     print("Created default category.")
    session.close()

    print("\n`archive.conf` has been successfully configured.")

if __name__ == '__main__':
    init_db()


```

### Step 4: Main Application File (`main.py`)

This file defines the app factory and the entry point for running the server with Waitress.

```
# /hivematrix-archive/main.py
import os
import sys
import configparser
from flask import Flask
from waitress import serve
import logging

# Import your module's components
from extensions import db
from routes.auth import auth_bp
from routes.articles import articles_bp # Your module's main blueprint

def create_app(config_path=None):
    """Create and configure the Flask application."""
    app = Flask(__name__, instance_relative_config=True)
    # ... (app configuration, db init, blueprint registration) ...
    return app

if __name__ == '__main__':
    instance_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
    config_path = os.path.join(instance_path, 'archive.conf')

    if not os.path.exists(config_path):
        print("ERROR: Configuration file 'archive.conf' not found.", file=sys.stderr)
        print("Please run 'python init_db.py' first.", file=sys.stderr)
        sys.exit(1)
    
    app = create_app(config_path=config_path)
    
    is_dev_mode = '--dev' in sys.argv
    if is_dev_mode:
        print("Starting Flask development server for Archive...")
        app.run(host='0.0.0.0', port=5003, debug=True)
    else:
        print("Starting Waitress production server for Archive...")
        serve(app, host='0.0.0.0', port=5003)


```

## 6. HiveMatrix Module Ecosystem

This section outlines the planned modules for the HiveMatrix PSA and their standard internal port assignments.

-   **HiveMatrix Nexus (Port 5000):** Central identity and directory service.
    
-   **HiveMatrix Treasury (Port 5001):** Internal billing engine.
    
-   **HiveMatrix Resolve (Port 5002):** AI-first ticketing system.
    
-   **HiveMatrix Archive (Port 5003):** Centralized internal knowledge base.
    
-   **HiveMatrix Dispatch (Port 5004):** Internal procurement and order tracking.
    
-   **HiveMatrix Architect (Port 5005):** Internal project management framework.
