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
    # Ensure the logs directory exists before initializing the file handler
    os.makedirs('logs', exist_ok=True)
    
    log_formatter = logging.Formatter('%(asctime)s [%(levelname)s] in %(module)s: %(message)s')
    file_handler = RotatingFileHandler('logs/error.log', mode='a', maxBytes=5_000_000, backupCount=5, encoding='utf-8')
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
    
    from app.i18n import load_translations, t
    load_translations()
    
    @app.context_processor
    def inject_t():
        from flask import session
        if 'lang' not in session:
            session['lang'] = 'en'
        return dict(t=t, current_lang=session.get('lang', 'en'))
    
    # Register custom Jinja filters
    def yt_embed_filter(url):
        if not url: return ""
        # Handle watch?v= format
        if "youtube.com/watch?v=" in url:
            video_id = url.split("v=")[1].split("&")[0]
            return f"https://www.youtube.com/embed/{video_id}"
        # Handle youtu.be/ format
        if "youtu.be/" in url:
            video_id = url.split("youtu.be/")[1].split("?")[0]
            return f"https://www.youtube.com/embed/{video_id}"
        # Handle existing embed format
        if "youtube.com/embed/" in url:
            return url
        return url # fallback
    
    app.jinja_env.filters['yt_embed'] = yt_embed_filter

    def yt_thumb_filter(url):
        if not url: return ""
        # Handle watch?v= format
        if "youtube.com/watch?v=" in url:
            video_id = url.split("v=")[1].split("&")[0]
        # Handle youtu.be/ format
        elif "youtu.be/" in url:
            video_id = url.split("youtu.be/")[1].split("?")[0]
        # Handle existing embed format
        elif "youtube.com/embed/" in url:
            video_id = url.split("youtube.com/embed/")[1].split("?")[0]
        else:
            return ""
        
        # We always attempt maxresdefault for highest resolution
        return f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"

    app.jinja_env.filters['yt_thumb'] = yt_thumb_filter

    import time
    from flask import request, g
    
    @app.before_request
    def start_timer():
        g.start_time = time.time()

    @app.after_request
    def log_request(response):
        if hasattr(g, 'start_time'):
            duration_ms = int((time.time() - g.start_time) * 1000)
            
            # Log all non-static traffic to provide accurate analytics on the dashboard
            if not request.path.startswith('/static/'):
                from app.database import get_db_connection
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO Analytics_Logs (method, path, ip_address, status_code, duration_ms) VALUES (?, ?, ?, ?, ?)",
                        (request.method, request.path, request.remote_addr, response.status_code, duration_ms)
                    )
                    conn.commit()
                    conn.close()
                except Exception as e:
                    app.logger.error(f"Analytics logging failed: {e}")
                    
        return response

    return app
