
# HiveMatrix Microservice Architecture Guide

**Author:** David Hamner & Gemini **Last Updated:** September 13, 2025

## 1. Introduction & Core Philosophy

Welcome to the HiveMatrix ecosystem. This document outlines the official microservice architecture for the HiveMatrix PSA, a powerful, multi-tenant Professional Services Automation platform designed for commercial service providers.

**Nexus is the foundational, required component of the entire ecosystem.** It serves as the central "address book" and identity provider. All other applications, referred to as **Modules** (e.g., Treasury, Archive), are standalone services that connect to Nexus for authentication and basic directory information before executing their specialized functions.

This guide is the blueprint for developing any new module. Adherence to this architecture ensures that the HiveMatrix platform remains scalable, secure, and maintainable as it grows. Because Nexus is the core, this guide and other primary setup documentation will be maintained within the Nexus repository.

## 2. Component Responsibilities

### 2.1. Nexus: The Central User & Directory Hub

Nexus is the **identity and directory service** for the entire HiveMatrix ecosystem. It is not a monolithic data repository. Its primary responsibilities are narrowly focused:

-   **User Directory:** The master database for user accounts, permissions, and basic profile information. **A user in Nexus is a user in all modules.**
    
-   **Central Address Book:** Provides a simple, referenceable directory of core entities like Companies and Contacts.
    
-   **Authentication Service:** Manages user credentials and issues JSON Web Tokens (JWTs) for secure, stateless authentication.
    
-   **Core Directory API:** Exposes the user, company, and contact directories through a secure REST API.
    

Nexus **does not** store module-specific data (e.g., billing configurations, wiki articles, ticket histories). Its purpose is to answer the questions: "Who is this user?" and "What basic entities exist in our PSA?".

### 2.2. Modules: The Specialized Services

A Module is a standalone Flask application that performs a specific business function. Each module is an expert in its own domain.

**Key Principles of a Module:**

-   **Standalone:** It runs as its own process, typically on a different port than Nexus and other modules.
    
-   **Nexus-Authenticated:** It uses Nexus for user login and retrieving basic directory information. It does not rely on Nexus for its own business logic.
    
-   **Owns Its Data:** Each module **must have its own PostgreSQL database** (e.g., `treasury_db`, `archive_db`). This database stores all data specific to that module's domain.
    
-   **Standalone Initialization:** Each module must have a standalone `init_db.py` script that handles interactive setup of its database connection and initializes the schema. This script **must not** depend on the Flask app object.
    

## 3. The Authentication Flow

Authentication is centralized through Nexus to provide a single sign-on (SSO) experience.

1.  **Login Request:** A user enters credentials into a Module's login form.
    
2.  **Token Generation:** The Module sends the credentials to the Nexus `/api/token` endpoint.
    
3.  **Validation & Issuance:** Nexus validates the credentials and, if successful, generates and returns a signed JWT.
    
4.  **Session Storage:** The Module receives the JWT and stores it in the user's server-side session. The module decodes the token to read the user's permission level and caches it in the session for local permission checks.
    
5.  **Authenticated API Calls:** For every subsequent API call to Nexus or another module, the calling module attaches the JWT to the `Authorization: Bearer <token>` header.
    

## 4. Deployment Architecture

This architecture is designed for simplicity and robustness, using a consistent set of tools for both production and development.

### 4.1. The Technology Stack

-   **Database: PostgreSQL**
    
    -   **Why:** A powerful, open-source database that handles high-concurrency reads and writes, essential for a multi-user PSA.
        
-   **WSGI Server: Waitress**
    
    -   **Why:** A production-quality, pure-Python WSGI server. Its key advantage is simplicity and cross-platform compatibility, running identically on both Windows and Linux without requiring compilers or complex dependencies.
        
-   **Reverse Proxy: Caddy**
    
    -   **Why:** A modern, secure web server that is significantly easier to configure than alternatives. Its primary benefit is **automatic HTTPS**, meaning it will automatically obtain and renew SSL certificates.
        

### 4.2. Deployment Steps on a VPS

A typical deployment script for a new client on a fresh Linux VPS would perform these steps:

1.  Install system packages (Caddy, PostgreSQL, Python, etc.).
    
2.  **Create empty PostgreSQL databases and users** for Nexus and each required module.
    
3.  Clone the Git repositories for Nexus and all required modules.
    
4.  Set up Python virtual environments and install dependencies for each module (`pip install -r requirements.txt`).
    
5.  **Run each module's `init_db.py` script.** This is an interactive process that will:
    
    -   Prompt for the module's PostgreSQL database credentials.
        
    -   Create a local `instance/<module>.conf` file.
        
    -   Connect to the database and create the necessary **tables and schema**.
        
6.  Create a simple `Caddyfile` to configure the reverse proxy.
    
7.  Create and enable `systemd` service files to run each module's `main.py` with **Waitress** as a background service.
    

### 4.3. Example Caddy Configuration

This `Caddyfile` showcases the simplicity of managing multiple services. Caddy automatically handles acquiring and renewing SSL certificates for each domain.

```
# /etc/caddy/Caddyfile

# Nexus Service (The Core)
nexus.your-client-domain.com {
    reverse_proxy 127.0.0.1:5000
}

# Treasury Module
treasury.your-client-domain.com {
    reverse_proxy 127.0.0.1:5001
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

def test_db_connection(creds):
    # ... (omitted for brevity - same as Treasury's init_db.py) ...

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

## 6. Architecture Best Practices

-   **Nexus is the Source of Truth for Identity.** Use Nexus to manage users, permissions, and basic company/contact info. Do not duplicate this data.
    
-   **Modules Own Their Domain Data.** All specialized data and configuration must live in the module's own PostgreSQL database.
    
-   **Communicate via APIs.** Modules should communicate with Nexus and with each other exclusively through REST APIs. Never allow one module to directly access another's database.
    
-   **Stateless Authentication.** The JWT approach is stateless. Services validate tokens without needing to check back with a central session store, which enhances scalability.
    
-   **Standalone Initialization.** Every module must have its own `init_db.py` that can be run from the command line to prepare its database schema and initial configuration.
