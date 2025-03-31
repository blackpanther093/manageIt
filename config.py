import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'default_secret_key')
    # GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', 'your_google_client_id')
    # GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', 'your_google_client_secret')
    
    # JWT Configuration
    # JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
    # JWT_ACCESS_TOKEN_EXPIRES = int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', 900))  # Default 15 minutes
    # JWT_REFRESH_TOKEN_EXPIRES = int(os.getenv('JWT_REFRESH_TOKEN_EXPIRES', 604800))

class DevelopmentConfig(Config):
    DEBUG = True
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', 'Goy@l123')
    DATABASES = {
        'mess_management': os.getenv('DB_NAME_MAIN', 'mess_management'),
        'mess1': os.getenv('DB_NAME_MESS1', 'mess1'),
        'mess2': os.getenv('DB_NAME_MESS2', 'mess2')
    }

class ProductionConfig(Config):
    DEBUG = False
    DB_HOST = os.getenv('DB_HOST')
    DB_USER = os.getenv('DB_USER')
    DB_PASSWORD = os.getenv('DB_PASSWORD')
    DATABASES = {
        'mess_management': os.getenv('DB_NAME_MAIN', 'mess_management'),
        'mess1': os.getenv('DB_NAME_MESS1', 'mess1'),
        'mess2': os.getenv('DB_NAME_MESS2', 'mess2')
    }
# Choose configuration based on the environment variable
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig
}

current_config = config.get(os.getenv('FLASK_ENV', 'development'))