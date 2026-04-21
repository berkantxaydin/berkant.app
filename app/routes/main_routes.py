from flask import Blueprint, render_template, abort, current_app, send_from_directory, make_response, session, request, redirect
import os
from app.repositories.game_repository import GameRepository
from app.repositories.cv_repository import CVRepository
from app.repositories.chat_repository import ChatRepository
from app.repositories.jam_repository import JamRepository
from app.i18n import t

main_bp = Blueprint('main', __name__)

# Instantiate repositories for use in routes
game_repo = GameRepository()
cv_repo = CVRepository()
chat_repo = ChatRepository()
jam_repo = JamRepository()


@main_bp.route('/')
def landing_page():
    return render_template('landing.html')

@main_bp.route('/robots.txt')
def robots_txt():
    return send_from_directory(current_app.static_folder, 'robots.txt')

@main_bp.route('/favicon.ico')
def favicon_ico():
    return send_from_directory(current_app.static_folder, 'favicon.ico')

@main_bp.route('/health')
def health_check():
    """Real healthcheck for CI/CD and deployment monitoring."""
    try:
        from app.database import get_db_connection
        conn = get_db_connection()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        return "OK", 200
    except Exception as e:
        return f"{t('Database Error')}: {str(e)}", 503

@main_bp.route('/set-lang/<lang>')
def set_lang(lang):
    if lang in ['en', 'tr']:
        session['lang'] = lang
    return redirect(request.referrer or '/')

@main_bp.route('/dashboard')
def dashboard():
    return render_template('index.html')

@main_bp.route('/cv')
def cv_pool():
    search_term = request.args.get('search')
    cvs = cv_repo.get_all_cvs(search_term)
    return render_template('cv_pool.html', cvs=cvs)

@main_bp.route('/cv/create')
def cv_create():
    return render_template('cv_create.html')

@main_bp.route('/chat')
def chat_room():
    rooms = chat_repo.get_rooms(admin_view=session.get('is_admin', False))
    return render_template('chat.html', rooms=rooms)

@main_bp.route('/cv/<int:cv_id>')
def view_cv(cv_id):
    cv = cv_repo.get_cv_by_id(cv_id)
    if not cv:
        abort(404)
    
    # User id from CV to fetch games
    user_games = game_repo.get_games_by_user(cv.user_id)
            
    return render_template('cv_view.html', cv=cv, games=user_games)

@main_bp.route('/upload')
def upload_page():
    jam_id = request.args.get('jam_id')
    return render_template('upload_game.html', jam_id=jam_id)

@main_bp.route('/jam')
def jam_page():
    # Use repo to fetch jams with games
    jams = jam_repo.get_jams_with_games()
    return render_template('jam.html', jams=jams)

@main_bp.route('/games/<int:game_id>')
def view_game(game_id):
    """Detailed game page with Godot embed and social features."""
    game = game_repo.get_game_by_id(game_id)
    if not game:
        abort(404)

    uid = session.get('user_id')
    is_liked = game_repo.is_liked_by_user(game_id, uid) if uid else False
    like_count = game_repo.get_like_count(game_id)
    comments = game_repo.get_comments(game_id)

    response = make_response(render_template('game_view.html', 
                                          game=game, 
                                          is_liked=is_liked, 
                                          like_count=like_count, 
                                          comments=comments))
    response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
    response.headers['Cross-Origin-Embedder-Policy'] = 'require-corp'
    return response

@main_bp.route('/games')
def games_list():
    """Shows the list of games (randomized for visitors)."""
    import random
    games = game_repo.get_all_games()
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

@main_bp.route('/account')
@login_required
def account_dashboard():
    uid = session['user_id']
    my_cvs = cv_repo.get_cvs_by_user(uid)
    my_games = game_repo.get_games_by_user(uid)
    return render_template('account.html', my_cvs=my_cvs, my_games=my_games)


@main_bp.route('/u/<username>')
def user_profile(username):
    """Public profile page for any registered user."""
    from app.repositories.user_repository import UserRepository
    user_repo = UserRepository()
    user = user_repo.get_by_username(username)
    if not user:
        abort(404)

    user_cvs = cv_repo.get_cvs_by_user(user.id)
    user_games = game_repo.get_games_by_user(user.id)
    return render_template('profile.html', profile_user=user, user_cvs=user_cvs, user_games=user_games)


@main_bp.route('/admin')
@admin_required
def admin_dashboard():
    all_cvs = cv_repo.get_all_cvs()
    all_games = game_repo.get_all_games()
    return render_template('admin.html', all_cvs=all_cvs, all_games=all_games)
