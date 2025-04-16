from flask import Flask
# from routes import app
import os
from dotenv import load_dotenv
from routes import app
# from flask_jwt_extended import JWTManager

# from auth import google

dotenv_path = os.path.join(os.path.dirname(__file__), 'myenv', '.env')
load_dotenv(dotenv_path=dotenv_path)

DB_PORT = os.getenv('DB_PORT')

# app = Flask(__name__)
# app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
# jwt = JWTManager(app)

app.secret_key = os.getenv('SECRET_KEY', os.urandom(24))
# app.register_blueprint(routes_blueprint)

# Initialize JWT
# jwt = JWTManager(app)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=DB_PORT)
