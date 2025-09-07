# **Nexus - Client Database Service**

Nexus is the central service for managing companies, contacts, assets, and users within the HiveMatrix PSA ecosystem. It provides a web interface for data entry, a scheduler for automated data synchronization, and a set of REST APIs for other microservices to consume.

## **Project Structure**
```
.
├── main.py                     # Main Flask application file
├── init_db.py                  # Database initialization script
├── scheduler.py                # Scheduler script for running background jobs
├── decorators.py               # Custom decorators for authentication and authorization
├── extensions.py               # Flask extension initializations
├── models.py                   # SQLAlchemy database models
├── pull_datto.py               # Script to pull data from Datto RMM
├── pull_freshservice.py        # Script to pull data from Freshservice
├── requirements.txt            # Python dependencies
├── instance/
│   └── nexus.conf              # Configuration file (created on first run)
│   └── nexus_brainhair.db      # SQLite database file (created on first run)
├── routes/
│   ├── assets.py
│   ├── companies.py
│   ├── contacts.py
│   ├── settings.py
│   └── users.py
└── templates/
    ├── base.html
    ├── login.html
    ├── dashboard.html
    ├── settings.html
    ├── assets.html
    ├── asset_details.html
    ├── companies.html
    ├── company_details.html
    ├── contacts.html
    └── contact_details.html
```

## **Setup and Installation**

Follow these steps to get the Nexus service running locally.

### **1. Create a Virtual Environment**

It's recommended to use a virtual environment to manage project dependencies.

```
# For Linux/macOS
python3 -m venv venv
source venv/bin/activate

# For Windows
python -m venv venv
.\venv\Scripts\activate
```

### **2. Install Dependencies**

Install the required Python packages using pip.

```
pip install -r requirements.txt
```

### **3. Initialize the Database**

The first time you run the application, you need to create the database tables, the default admin user, and the configuration file. If you are updating the application after a database model change, you may need to delete the old `nexus_brainhair.db` file before running this command.

```
python init_db.py
```

This command will:

1. Create the `instance` folder if it doesn't exist.
2. Create the `nexus_brainhair.db` SQLite file in the `instance` folder.
3. Create the necessary database tables based on `models.py`.
4. Create a default admin user with the following credentials:
   * **Username:** `admin`
   * **Password:** `admin`
5. Create a `nexus.conf` file in the `instance` folder and populate it with the admin user's API key and placeholder values for Datto RMM and Freshservice API credentials.

### **4. Configure the Application**

Edit the `instance/nexus.conf` file with your Datto RMM and Freshservice API credentials.

### **5. Run the Application**

Start the Flask development server.

```
python main.py
```

The application will be available at `http://127.0.0.1:5000`.

## **Usage**

### **Web Interface**

* Navigate to `http://127.0.0.1:5000` in your browser.
* Log in with the admin credentials (`admin/admin`).
* From the dashboard, you can view and manage companies.
* The "Settings" page allows you to manage users and scheduler jobs.

### **Scheduler**

The application includes a scheduler that runs background jobs to synchronize data from external services. The available jobs are:

* **Sync Freshservice Data**: Pulls companies and contacts from Freshservice.
* **Sync Datto RMM Assets**: Pulls sites and devices from Datto RMM.
* **Assign Missing Freshservice Account Numbers**: A utility to set account numbers in Freshservice (disabled by default).
* **Push Account Numbers to Datto RMM**: A utility to set account numbers in Datto RMM (disabled by default).

You can enable, disable, change the interval, and run these jobs from the "Settings" page in the web interface.

### **API Endpoints**

The following API endpoints are available for other microservices. An API key is required for authentication and must be included in the `X-API-Key` header of your requests.

#### **Companies**

* `GET /api/companies`: Get a list of all companies.
* `POST /api/companies`: Create a new company.
* `GET /api/companies/<account_number>`: Get details for a specific company.
* `PUT /api/companies/<account_number>`: Update a specific company.
* `GET /api/companies/<account_number>/users`: Get all users associated with a specific company.

#### **Assets**

* `GET /api/assets`: Get a list of all assets.
* `POST /api/assets`: Create a new asset.
* `PUT /api/assets/<asset_id>`: Update a specific asset.

#### **Contacts**

* `GET /api/contacts`: Get a list of all contacts.
* `POST /api/contacts`: Create a new contact.
* `PUT /api/contacts/<contact_id>`: Update a specific contact.

#### **Users**

* `GET /api/users`: Get a list of all users (admin only).
* `GET /api/users/<user_id>`: Get details for a specific user (admin only).
