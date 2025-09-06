from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from apscheduler.schedulers.background import BackgroundScheduler

# Instantiate extensions
db = SQLAlchemy()
login_manager = LoginManager()
scheduler = BackgroundScheduler()
