import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent

class Config:
    # Database configuration
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{BASE_DIR / "instance" / "database.db"}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Secret key for sessions (change in production)
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Telegram Bot API settings
    TELEGRAM_API_URL = 'https://api.telegram.org/bot'

