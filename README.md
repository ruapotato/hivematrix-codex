
# Nexus - Client Database Service

Nexus is the central service for managing companies and users within the HiveMatrix PSA ecosystem. It provides a web interface for data entry and a set of REST APIs for other microservices to consume.

## Project Structure

```
.
├── nexus.py              # Main Flask application file
├── templates/            # HTML templates
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── add_company.html
│   └── add_user.html
├── requirements.txt      # Python dependencies
└── nexus_brainhair.db    # SQLite database file (will be created)

```

## Setup and Installation

Follow these steps to get the Nexus service running locally.

### 1. Create a Virtual Environment

It's recommended to use a virtual environment to manage project dependencies.

```
# For Linux/macOS
python3 -m venv venv
source venv/bin/activate

# For Windows
python -m venv venv
.\venv\Scripts\activate

```

### 2. Install Dependencies

Install the required Python packages using pip.

```
pip install -r requirements.txt

```

### 3. Initialize the Database

The first time you run the application, you need to create the database tables and the default admin user.

```
flask init-db

```

This command will:

1.  Create the `nexus_brainhair.db` SQLite file.
    
2.  Create the `user` and `company` tables.
    
3.  Create a default admin user with the following credentials:
    
    -   **Username:**  `admin`
        
    -   **Password:**  `admin`
        

### 4. Run the Application

Start the Flask development server.

```
flask run

```

The application will be available at `http://127.0.0.1:5000`.

## Usage

### Web Interface

-   Navigate to `http://127.0.0.1:5000` in your browser.
    
-   Log in with the admin credentials (`admin`/`admin`).
    
-   From the dashboard, you can view, add, and manage companies and users.
    

### API Endpoints

The following API endpoints are available for other microservices:

-   `GET /api/companies`: Get a list of all companies.
    
-   `GET /api/companies/<id>`: Get details for a specific company.
    
-   `GET /api/users`: Get a list of all users.
    
-   `GET /api/users/<id>`: Get details for a specific user.
    
-   `GET /api/companies/<id>/users`: Get all users associated with a specific company.
    

These APIs are read-only for now but can be expanded to include `POST`, `PUT`, and `DELETE` methods as needed.# Nexus - Client Database Service

Nexus is the central service for managing companies and users within the HiveMatrix PSA ecosystem. It provides a web interface for data entry and a set of REST APIs for other microservices to consume.

## Project Structure

```
.
├── nexus.py              # Main Flask application file
├── templates/            # HTML templates
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── add_company.html
│   └── add_user.html
├── requirements.txt      # Python dependencies
└── nexus_brainhair.db    # SQLite database file (will be created)

```

## Setup and Installation

Follow these steps to get the Nexus service running locally.

### 1. Create a Virtual Environment

It's recommended to use a virtual environment to manage project dependencies.

```
# For Linux/macOS
python3 -m venv pyenv
source ./pyenv/bin/activate

# For Windows
python -m venv pyenv
.\pyenv\Scripts\activate

```

### 2. Install Dependencies

Install the required Python packages using pip.

```
pip install -r requirements.txt

```

### 3. Initialize the Database

The first time you run the application, you need to create the database tables and the default admin user.

```
flask init-db

```

This command will:

1.  Create the `nexus_brainhair.db` SQLite file.
    
2.  Create the `user` and `company` tables.
    
3.  Create a default admin user with the following credentials:
    
    -   **Username:**  `admin`
        
    -   **Password:**  `admin`
        

### 4. Run the Application

Start the Flask development server.

```
flask run

```

The application will be available at `http://127.0.0.1:5000`.

## Usage

### Web Interface

-   Navigate to `http://127.0.0.1:5000` in your browser.
    
-   Log in with the admin credentials (`admin`/`admin`).
    
-   From the dashboard, you can view, add, and manage companies and users.
    

### API Endpoints

The following API endpoints are available for other microservices:

-   `GET /api/companies`: Get a list of all companies.
    
-   `GET /api/companies/<id>`: Get details for a specific company.
    
-   `GET /api/users`: Get a list of all users.
    
-   `GET /api/users/<id>`: Get details for a specific user.
    
-   `GET /api/companies/<id>/users`: Get all users associated with a specific company.
    

These APIs are read-only for now but can be expanded to include `POST`, `PUT`, and `DELETE` methods as needed.
