from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from app.database import get_db_connection

auth_bp = Blueprint('auth', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            # If HTMX request, we can send a specialized response or client-side redirect
            if 'HX-Request' in request.headers:
                # HTMX redirect
                return "", 200, {'HX-Redirect': '/login'}
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        if not session.get('is_admin', False):
            return "Unauthorized. Admin privileges required.", 403
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, password_hash, is_admin FROM Users WHERE username = ?", (username,))
            user = cursor.fetchone()
            
            if user and check_password_hash(user['password_hash'], password):
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['is_admin'] = bool(user['is_admin'])
                
                if request.form.get('remember'):
                    session.permanent = True
                else:
                    session.permanent = False
                    
                return redirect(url_for('main.landing_page'))
            else:
                return render_template('login.html', error="Invalid username or password.")
        finally:
            conn.close()
            
    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        admin_code = request.form.get('admin_code', '')
        
        if not username or not email or not password:
            return render_template('register.html', error="All fields are required.")
            
        hashed_pw = generate_password_hash(password)
        is_admin = 1 if admin_code == "PROGLEM_ADMIN_SECRET" else 0
        
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO Users (username, email, password_hash, is_admin) VALUES (?, ?, ?, ?)",
                (username, email, hashed_pw, is_admin)
            )
            conn.commit()
            return redirect(url_for('auth.login'))
        except Exception as e:
            current_app.logger.error(f"Registration error: {e}")
            return render_template('register.html', error="Username or email already exists.")
        finally:
            conn.close()

    return render_template('register.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.landing_page'))
