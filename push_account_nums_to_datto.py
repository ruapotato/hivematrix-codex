import requests
import base64
import json
import os
import sys
import time
import configparser
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from main import Company

# --- Configuration ---
config = configparser.ConfigParser()
config.read('nexus.conf')
# ... (load datto and freshservice configs) ...

def get_db_session():
    engine = create_engine('sqlite:///./nexus_brainhair.db')
    Session = sessionmaker(bind=engine)
    return Session()

# ... (API functions from original push_account_nums_to_datto.py) ...

# --- Main Execution ---
if __name__ == "__main__":
    print(" Datto RMM & Freshservice Account Number Pusher")
    # ... (main logic from original push_account_nums_to_datto.py, adapted for Nexus) ...
