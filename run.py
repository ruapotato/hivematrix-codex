from dotenv import load_dotenv
import os

# Load .flaskenv before importing app
load_dotenv('.flaskenv')

from app import app

if __name__ == "__main__":
    app.run(port=5010)
