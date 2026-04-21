import os
import logging
from flask import Flask
from dotenv import load_dotenv  # type: ignore

load_dotenv()

def create_app() -> Flask:
    from logging.handlers import RotatingFileHandler

    # Specify absolute paths for high-reliability resolution on Windows
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(base_dir)
    app = Flask(__name__, 
                template_folder=os.path.join(project_root, 'templates'), 
                static_folder=os.path.join(base_dir, 'static'))
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-unsafe-dev-key')
    
    if app.config['SECRET_KEY'] == 'default-unsafe-dev-key':
        app.logger.warning("SECURITY ALERT: Using default SECRET_KEY.")
    
    os.makedirs('logs', exist_ok=True)
    
    log_formatter = logging.Formatter('%(asctime)s [%(levelname)s] in %(module)s: %(message)s')
    file_handler = RotatingFileHandler('logs/error.log', mode='a', maxBytes=5_000_000, backupCount=5, encoding='utf-8')
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(logging.INFO)
    
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info("Proglem App instance created and logger configured.")

    from app.database import init_db
    try:
        init_db()
    except Exception as e:
        app.logger.error(f"Failed to initialize database: {e}")

    from app.routes.main_routes import main_bp
    from app.routes.api_routes import api_bp
    from app.routes.ai_routes import ai_bp
    from app.routes.auth_routes import auth_bp
    
    for bp in [main_bp, api_bp, ai_bp, auth_bp]:
        app.register_blueprint(bp)
    
    from app.i18n import load_translations, t
    load_translations()
    
    @app.context_processor
    def inject_t():
        from flask import session
        return dict(t=t, current_lang=session.get('lang', 'en'))
    
    def yt_embed_filter(url: str) -> str:
        if not url: return ""
        if "youtube.com/watch?v=" in url:
            video_id = url.split("v=")[1].split("&")[0]
        elif "youtu.be/" in url:
            video_id = url.split("youtu.be/")[1].split("?")[0]
        elif "youtube.com/embed/" in url:
            return url
        else:
            return url
        return f"https://www.youtube.com/embed/{video_id}"
    
    app.jinja_env.filters['yt_embed'] = yt_embed_filter

    def yt_thumb_filter(url: str) -> str:
        if not url: return ""
        video_id = None
        if "watch?v=" in url:
            video_id = url.split("v=")[1].split("&")[0]
        elif "youtu.be/" in url:
            video_id = url.split("youtu.be/")[1].split("?")[0]
        elif "embed/" in url:
            video_id = url.split("embed/")[1].split("?")[0]
        
        return f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg" if video_id else ""

    app.jinja_env.filters['yt_thumb'] = yt_thumb_filter

    import time
    import uuid
    from flask import request, g
    
    @app.before_request
    def start_timer():
        g.start_time = time.time()
        g.visitor_id = request.cookies.get('proglem_vid')
        if not g.visitor_id:
            g.visitor_id = str(uuid.uuid4())
            g.new_visitor = True
        else:
            g.new_visitor = False

    @app.after_request
    def log_request(response):
        if hasattr(g, 'start_time'):
            duration_ms = int((time.time() - g.start_time) * 1000)
            
            if not request.path.startswith('/static/'):
                from app.repositories.analytics_repository import AnalyticsRepository
                try:
                    AnalyticsRepository().log_request(
                        method=request.method,
                        path=request.path,
                        visitor_id=g.visitor_id,
                        is_htmx='HX-Request' in request.headers,
                        status_code=response.status_code,
                        duration_ms=duration_ms
                    )
                except Exception as e:
                    app.logger.error(f"Analytics failure: {e}")

            if getattr(g, 'new_visitor', False):
                response.set_cookie('proglem_vid', g.visitor_id, max_age=31536000, httponly=True, samesite='Lax')
                    
        return response

    from app.database import close_db
    app.teardown_appcontext(close_db)


    from flask import request, render_template
    @app.errorhandler(Exception)
    def handle_global_error(e):
        # 1. Log the full stack trace (exc_info=True is the magic keyword)
        app.logger.error(f"Unhandled Exception: {str(e)}", exc_info=True)
        
        # 2. Check if this was a background HTMX request
        if 'HX-Request' in request.headers:
            # Return a safe, localized error component instead of breaking the UI
            from app.i18n import t
            return f'''
            <article style="border-color: var(--pico-del-color); margin-top: 1rem;">
                <header style="color: var(--pico-del-color);">
                    <strong>⚠️ {t("System Error")}</strong>
                </header>
                <p>{t("An unexpected error occurred. The administrators have been notified.")}</p>
                <button class="outline" onclick="window.location.reload()">{t("Refresh Page")}</button>
            </article>
            ''', 500
            
        # 3. Check if it was an API/JSON request
        if request.path.startswith('/api/') and 'HX-Request' not in request.headers:
            from app.i18n import t
            return {"status": "error", "message": t("Internal Server Error")}, 500

        # 4. Otherwise, it's a standard page load crash
        return render_template('500.html'), 500

    return app
