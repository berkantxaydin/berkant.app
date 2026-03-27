import os
import json
from flask import Blueprint, render_template, abort, current_app, send_from_directory, make_response
from app.database import get_db_connection
from app.repositories.game_repository import GameRepository

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def landing_page():
    return render_template('landing.html')

@main_bp.route('/dashboard')
def dashboard():
    return render_template('index.html')

@main_bp.route('/cv')
def cv_pool():
    return render_template('cv_pool.html')

@main_bp.route('/cv/create')
def cv_create():
    return render_template('cv_create.html')

@main_bp.route('/chat')
def chat_room():
    return render_template('chat.html')

@main_bp.route('/cv/<int:cv_id>')
def view_cv(cv_id):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT c.*, u.username FROM CV_Catalog c JOIN Users u ON c.user_id = u.id WHERE c.id = ?", (cv_id,))
        row = cursor.fetchone()
        if not row:
            abort(404)
        
        cv = dict(row)
        cv['cv_data'] = json.loads(cv['cv_data'])
        
        # User id from CV to fetch games
        user_games = []
        all_games = GameRepository.get_all_games()
        for g in all_games:
            # Simplistic relation fetch
            if g.get('username') == cv['username']:
                user_games.append(g)
                
        return render_template('cv_view.html', cv=cv, games=user_games)
    finally:
        conn.close()

@main_bp.route('/upload')
def upload_page():
    from flask import request
    jam_id = request.args.get('jam_id')
    return render_template('upload_game.html', jam_id=jam_id)

@main_bp.route('/jam')
def jam_page():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Game_Jams ORDER BY start_time DESC LIMIT 1")
        jam = cursor.fetchone()
        
        if not jam:
            return render_template('jam.html', jam=None, games=[])
            
        jam = dict(jam)
        cursor.execute("SELECT g.*, u.username FROM Godot_Games g JOIN Users u ON g.user_id = u.id WHERE g.jam_id = ? ORDER BY g.created_at DESC", (jam['id'],))
        games = [dict(r) for r in cursor.fetchall()]
        
        return render_template('jam.html', jam=jam, games=games)
    finally:
        conn.close()

@main_bp.route('/games/<int:game_id>')
def view_game(game_id):
    """Detailed game page with Godot embed and social features."""
    from app.database import get_db_connection
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Fetch game details
        cursor.execute("SELECT g.*, u.username FROM Godot_Games g JOIN Users u ON g.user_id = u.id WHERE g.id = ?", (game_id,))
        row = cursor.fetchone()
        if not row:
            abort(404)
        game = dict(row)

        # Check if current user liked it
        is_liked = False
        uid = session.get('user_id')
        if uid:
            cursor.execute("SELECT 1 FROM Game_Likes WHERE user_id = ? AND game_id = ?", (uid, game_id))
            is_liked = cursor.fetchone() is not None

        # Get counts
        cursor.execute("SELECT COUNT(*) as cnt FROM Game_Likes WHERE game_id = ?", (game_id,))
        like_count = cursor.fetchone()['cnt'] or 0

        # Fetch comments
        cursor.execute("""
            SELECT c.*, u.username 
            FROM Game_Comments c 
            JOIN Users u ON c.user_id = u.id 
            WHERE c.game_id = ? 
            ORDER BY c.created_at DESC
        """, (game_id,))
        comments = [dict(r) for r in cursor.fetchall()]

        from flask import make_response
        response = make_response(render_template('game_view.html', game=game, is_liked=is_liked, like_count=like_count, comments=comments))
        response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
        response.headers['Cross-Origin-Embedder-Policy'] = 'require-corp'
        return response
    finally:
        conn.close()

@main_bp.route('/games')
def games_list():
    """Shows the list of games (randomized for visitors)."""
    import random
    games = GameRepository.get_all_games()
    random.shuffle(games)
    return render_template('game_list.html', games=games)



@main_bp.route('/play_mock/<path:filename>')
def serve_local_mock_upload(filename):
    """Serves user-uploaded WebGL files locally with mandatory isolation headers."""
    response = make_response(send_from_directory(os.path.join(current_app.root_path, 'static', 'mock_s3'), filename))
    response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
    response.headers['Cross-Origin-Embedder-Policy'] = 'require-corp'
    if filename.endswith('.wasm'):
        response.headers['Content-Type'] = 'application/wasm'
    return response

from app.routes.auth_routes import login_required, admin_required
from flask import session

@main_bp.route('/account')
@login_required
def account_dashboard():
    from app.repositories.cv_repository import CVRepository
    
    uid = session['user_id']
    my_cvs = CVRepository.get_cvs_by_user(uid)
    my_games = GameRepository.get_games_by_user(uid)
    return render_template('account.html', my_cvs=my_cvs, my_games=my_games)

@main_bp.route('/admin')
@admin_required
def admin_dashboard():
    from app.repositories.cv_repository import CVRepository
    
    all_cvs = CVRepository.get_all_cvs()
    all_games = GameRepository.get_all_games()
    return render_template('admin.html', all_cvs=all_cvs, all_games=all_games)
