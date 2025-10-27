# config.py
import os
from dotenv import load_dotenv
load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = "mysql+pymysql://root:manikanta@localhost/spps_db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Directory for uploaded files
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
