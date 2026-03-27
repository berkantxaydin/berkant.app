import os
import logging
from flask import Flask
from dotenv import load_dotenv

# Load environment variables from .env file before anything else
load_dotenv()

def create_app():
    import logging
    from logging.handlers import RotatingFileHandler

    # Specify templates directory relative to the app package (root/templates)
    app = Flask(__name__, template_folder='../templates', static_folder='../app/static')
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-unsafe-dev-key')
    
    # Configure robust logging handling for error.log
    log_formatter = logging.Formatter('%(asctime)s [%(levelname)s] in %(module)s: %(message)s')
    file_handler = RotatingFileHandler('error.log', maxBytes=5_000_000, backupCount=5)
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(logging.INFO) # Log info and above
    
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info("Proglem App instance created and logger configured.")

    from app.database import init_db
    
    # Unconditionally initialize schemas (IF NOT EXISTS protects existing data)
    try:
        init_db()
    except Exception as e:
        app.logger.error(f"Failed to initialize database schemas: {e}")

    # Register blueprints (with updated route filenames)
    from app.routes.main_routes import main_bp
    from app.routes.api_routes import api_bp
    from app.routes.ai_routes import ai_bp
    from app.routes.auth_routes import auth_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(auth_bp)

    return app
