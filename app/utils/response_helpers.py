from functools import wraps
from flask import jsonify, current_app, request
from app.i18n import t

def json_response(f):
    """Decorator to return JSON responses with error handling."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            current_app.logger.error(f"API Error in {f.__name__}: {e}", exc_info=True)
            return jsonify({"error": "Internal server error", "details": str(e)}), 500
    return decorated_function

def htmx_response(f):
    """Decorator for HTMX fragment responses with error handling."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            current_app.logger.error(f"HTMX Error in {f.__name__}: {e}", exc_info=True)
            # Return a user-friendly error message in HTML
            return f'<p style="color:var(--pico-del-color);">❌ {t("An error occurred")}: {str(e)}</p>', 500
    return decorated_function
