from flask import Blueprint, jsonify, request, current_app, session, redirect, make_response, render_template
from markupsafe import escape
import datetime
import os
import json
import boto3

from app.repositories.cv_repository import CVRepository
from app.repositories.game_repository import GameRepository
from app.repositories.chat_repository import ChatRepository
from app.repositories.jam_repository import JamRepository
from app.repositories.analytics_repository import AnalyticsRepository
from app.routes.auth_routes import login_required, admin_required
from app.i18n import t

# New utilities and services
from app.utils.system_utils import get_system_metrics
from app.utils.response_helpers import json_response, htmx_response
import app.utils.render_helpers as render_helpers
import app.services.translation_service as translation_service

api_bp = Blueprint('api', __name__, url_prefix='/api')

# Instantiate repositories for DAL access
cv_repo = CVRepository()
game_repo = GameRepository()
chat_repo = ChatRepository()
jam_repo = JamRepository()
analytics_repo = AnalyticsRepository()


# --- CV CATALOG ---
@api_bp.route('/cv', methods=['GET'])
@json_response
def get_cvs():
    search = request.args.get('search', '')
    results = cv_repo.get_all_cvs(search)
    if 'HX-Request' in request.headers:
        return render_helpers.render_cv_cards(results)
    return jsonify({"status": "success", "count": len(results), "data": [vars(cv) for cv in results]}), 200

@api_bp.route('/cv/<int:cv_id>/htmx', methods=['GET'])
@htmx_response
def get_cv_htmx(cv_id):
    """Returns the custom interactive HTMX content for a specific CV profile."""
    cv = cv_repo.get_cv_by_id(cv_id)
    if not cv:
        raise ValueError(t('CV not found'))
    # Return the custom HTMX or a fallback if empty
    return cv.custom_htmx or render_helpers.render_empty_state(t('This developer has not added an interactive resume yet.'))

@api_bp.route('/cv/create', methods=['POST'])
@login_required
@json_response
def create_ecom_cv():
    user_id = session['user_id']
    title = request.form.get('title')
    location = request.form.get('location', '')
    summary = request.form.get('summary')
    skills = [s.strip() for s in request.form.get('skills', '').split(',') if s.strip()]
    exp_role = request.form.get('exp_role')
    
    if not title or not summary:
        return jsonify({"error": "Missing required e-commerce fields"}), 400
        
    cv_data = {
        "skills": skills,
        "experience": [{"role": exp_role}]
    }
    
    custom_htmx = None
    file = request.files.get('custom_htmx')
    if file and file.filename != '':
        custom_htmx = file.read().decode('utf-8', errors='ignore')
        
    cv_id = cv_repo.add_cv(user_id, title, location, summary, cv_data, custom_htmx=custom_htmx)
    return redirect(f'/cv/{cv_id}')


# --- GAME JAM / UPLOADS ---
@api_bp.route('/jam/get-upload-url', methods=['GET'])
@api_bp.route('/jam/get_upload_url', methods=['GET'])
@json_response
def get_upload_url():
    """Generates a secure S3/R2 upload URL to bypass local server bandwidth constraints."""
    filename = request.args.get('filename', 'default.bin')
    mime_type = request.args.get('content_type', 'application/octet-stream')
    
    # Smart Mock Detection: If R2 endpoint contains placeholders or common defaults, force Mock Mode
    r2_endpoint = os.environ.get('R2_ENDPOINT_URL', "https://mock-endpoint.com")
    r2_key_id = os.environ.get('R2_ACCESS_KEY_ID', 'test')
    
    placeholders = ["your-r2-id", "your_id", "placeholder", "test", "your-bucket"]
    is_mock_needed = any(p in r2_endpoint.lower() or p in r2_key_id.lower() for p in placeholders)
    
    if is_mock_needed:
        r2_endpoint = "https://mock-endpoint.com"
        current_app.logger.info("R2 Placeholders detected. Falling back to Mock S3 Mode.")

    s3_client = boto3.client(
        's3',
        endpoint_url=r2_endpoint,
        aws_access_key_id=r2_key_id,
        aws_secret_access_key=os.environ.get('R2_SECRET_ACCESS_KEY', 'test'),
        region_name='auto' 
    )

    presigned_data = s3_client.generate_presigned_post(
        Bucket=os.environ.get('R2_BUCKET_NAME', 'jam-uploads'),
        Key=f"submissions/{filename}",
        Fields={"Content-Type": mime_type},
        Conditions=[
            ["content-length-range", 1, 524288000],
            ["eq", "$Content-Type", mime_type]
        ],
        ExpiresIn=3600
    )
    return jsonify(presigned_data)

@api_bp.route('/jam/mock_upload', methods=['POST'])
@json_response
def mock_upload():
    """Local simulation of S3 Post object handling for offline testing"""
    import urllib.parse
    raw_key = request.form.get('key')
    key = urllib.parse.unquote_plus(raw_key) if raw_key else None
    file = request.files.get('file')
    
    if key and file:
        filepath = os.path.join(current_app.root_path, 'static', 'mock_s3', key)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        file.save(filepath)
        return '', 204
    return 'Bad Request', 400

@api_bp.route('/jam/submit', methods=['POST'])
@login_required
@json_response
def submit_game():
    data = request.json
    if not data or not data.get('title') or not data.get('game_url'):
        return jsonify({"error": "Title and Game URL are required"}), 400
        
    from app.services.game_validator import submit_validation_job
    game_id = game_repo.add_game(session['user_id'], data['title'], data.get('description', ''), data['game_url'], data.get('jam_id'))
    
    # Fire and forget our Mutex UUID validation background task
    job_uid = submit_validation_job(game_id, data['game_url'])
    
    return jsonify({"message": "Validating WebGL Sandbox Integrity...", "id": game_id, "job_uid": job_uid}), 201

@api_bp.route('/games/view/<int:game_id>', methods=['POST'])
def increment_view(game_id):
    """Silent view incrementer via htmx load trigger."""
    game_repo.increment_view(game_id)
    return "", 204


# --- ACCOUNT CRUD (HTMX NATIVE PORTALS) ---
from app.routes.auth_routes import login_required
from flask import session

@api_bp.route('/cv/<int:cv_id>', methods=['DELETE'])
@login_required
@htmx_response
def delete_cv_htmx(cv_id):
    success = cv_repo.delete_cv(cv_id, session['user_id'], is_admin=session.get('is_admin'))
    if success: return render_helpers.render_empty_response()
    raise ValueError(t("Error deleting CV. Unauthorized."))

@api_bp.route('/cv/<int:cv_id>/edit', methods=['GET'])
@login_required
@htmx_response
def get_cv_edit_form(cv_id):
    cv = cv_repo.get_cv_by_id(cv_id)
    if not cv or (cv.user_id != session['user_id'] and not session.get('is_admin')):
        raise ValueError(t("Unauthorized"))
    return render_template('partials/cv_edit_form.html', cv=cv)


@api_bp.route('/cv/<int:cv_id>', methods=['PUT'])
@login_required
@htmx_response
def update_cv_htmx(cv_id):
    title = request.form.get('title')
    location = request.form.get('location', '')
    summary = request.form.get('summary')
    success = cv_repo.update_cv(cv_id, session['user_id'], title, location, summary, is_admin=session.get('is_admin'))
    if success:
        return render_template('partials/cv_preview.html', cv_id=cv_id, title=title, location=location, summary=summary)
    raise ValueError(t("Update failed"))

@api_bp.route('/jam/<int:game_id>', methods=['DELETE'])
@login_required
@htmx_response
def delete_game_htmx(game_id):
    success = game_repo.delete_game(game_id, session['user_id'], is_admin=session.get('is_admin'))
    if success: return render_helpers.render_empty_response()
    raise ValueError(t("Unauthorized"))

# --- SOCIAL FEATURES: LIKES & COMMENTS ---

@api_bp.route('/games/like/<int:game_id>', methods=['POST'])
@login_required
@htmx_response
def like_game(game_id):
    """Toggles a like on a game."""
    uid = session['user_id']
    is_liked = game_repo.toggle_like(game_id, uid)
    count = game_repo.get_like_count(game_id)
    return render_template('partials/game_like_button.html', game_id=game_id, count=count, is_liked=is_liked)


@api_bp.route('/games/<int:game_id>/comments', methods=['POST'])
@login_required
@htmx_response
def post_game_comment(game_id):
    """Saves a comment and returns the new comment list snippet for HTMX."""
    uid = session['user_id']
    content = request.form.get('content', '').strip()
    
    if not content:
        raise ValueError(t("Comment cannot be empty"))
        
    game_repo.add_comment(game_id, uid, content)
    comments = game_repo.get_comments(game_id)
    return render_template('partials/comment_list.html', comments=comments, game_id=game_id, current_user_id=uid, is_admin=session.get('is_admin', False))

@api_bp.route('/comments/<int:comment_id>', methods=['DELETE'])
@login_required
@htmx_response
def delete_game_comment(comment_id):
    """Deletes a comment if the user is an admin or the author."""
    game_repo.delete_comment(comment_id, session['user_id'], session.get('is_admin', False))
    return render_helpers.render_empty_response() # HTMX removes the closest article


# --- CHAT ROOMS ---

@api_bp.route('/chat/rooms', methods=['GET'])
def get_chat_rooms():
    """Returns all enabled rooms as an HTMX tab snippet."""
    rooms = chat_repo.get_rooms(admin_view=session.get('is_admin', False))
    html = "".join([
        f'<button hx-get="/api/chat/messages?room_id={r["id"]}" '
        f'hx-target="#chat-messages" class="outline">{r["name"]}</button>' 
        for r in rooms
    ])
    return html


@api_bp.route('/chat/messages', methods=['GET'])
@htmx_response
def get_chat_messages():
    """Returns HTML for HTMX polling — room_id from query string (defaults to 1)."""
    try:
        room_id = int(request.args.get('room_id', 1))
    except (ValueError, TypeError):
        room_id = 1
    
    messages = chat_repo.get_messages(room_id, limit=60)
    messages.reverse() # Newest at bottom
    
    html = render_helpers.render_chat_messages(messages, current_user_id=session.get('user_id'), is_admin=session.get('is_admin', False))
    
    resp = make_response(html)
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return resp


@api_bp.route('/chat/messages', methods=['POST'])
@login_required
@htmx_response
def post_chat_message():
    """Posts a message to a specific room and returns the updated list."""
    uid = session['user_id']
    content = request.form.get('content', '').strip()
    try:
        room_id = int(request.form.get('room_id', 1))
    except (ValueError, TypeError):
        room_id = 1

    if not content:
        raise ValueError(t('Message cannot be empty'))

    room = chat_repo.get_room_by_id(room_id)
    if not room or (not room['is_enabled'] and not session.get('is_admin')):
        raise PermissionError(t('This room is currently disabled.'))
    chat_repo.add_message(uid, room_id, content)

    # Re-render messages for the room
    messages = chat_repo.get_messages(room_id, limit=60)
    messages.reverse()
    html = render_helpers.render_chat_messages(messages, current_user_id=uid, is_admin=session.get('is_admin', False))
    return make_response(html)


@api_bp.route('/chat/messages/<int:msg_id>', methods=['DELETE'])
@login_required
@htmx_response
def delete_chat_message(msg_id):
    """Deletes a chat message if the user is the author or an admin."""
    chat_repo.delete_message(msg_id, user_id=session['user_id'], is_admin=session.get('is_admin', False))
    return render_helpers.render_empty_response()  # HTMX removes the element


# --- CHAT ROOM ADMIN CRUD ---

@api_bp.route('/chat/rooms/admin', methods=['GET'])
@admin_required
@htmx_response
def list_chat_rooms_admin():
    rooms = chat_repo.get_rooms(admin_view=True)
    return render_template('partials/room_admin_table.html', rooms=rooms)


@api_bp.route('/chat/rooms', methods=['POST'])
@admin_required
@htmx_response
def create_chat_room():
    """Creates a new standalone chat room."""
    name = request.form.get('name', '').strip()
    if not name:
        raise ValueError(t('Room name is required.'))
    chat_repo.create_room(name)
    rooms = chat_repo.get_rooms(admin_view=True)
    return render_template('partials/room_admin_table.html', rooms=rooms)


@api_bp.route('/chat/rooms/<int:room_id>/toggle', methods=['PATCH'])
@admin_required
@htmx_response
def toggle_chat_room(room_id):
    """Flips the is_enabled flag on a room."""
    chat_repo.toggle_room(room_id)
    rooms = chat_repo.get_rooms(admin_view=True)
    return render_template('partials/room_admin_table.html', rooms=rooms)


@api_bp.route('/chat/rooms/<int:room_id>', methods=['DELETE'])
@admin_required
@htmx_response
def delete_chat_room(room_id):
    """Deletes a room and all its messages."""
    chat_repo.delete_room(room_id)
    rooms = chat_repo.get_rooms(admin_view=True)
    return render_template('partials/room_admin_table.html', rooms=rooms)

@api_bp.route('/admin/translate_missing', methods=['POST'])
@admin_required
@htmx_response
def translate_missing():
    from app.i18n import translations
    
    missing_keys = [k for k in translations.get('en', {}) if k not in translations.get('tr', {})]
    if not missing_keys:
        return render_helpers.render_alert(t('All keys are already translated!'), type='success')
    
    translation_service.start_translation_job(missing_keys)
    
    return render_template('partials/translation_status.html', state={"message": t("AI Core is initializing..."), "status": "pending", "progress_pct": 0})

@api_bp.route('/admin/translation_status', methods=['GET'])
@admin_required
@htmx_response
def get_translation_status():
    """Returns an HTMX partial with the current translation progress bar."""
    state = translation_service.get_translation_state()
    
    return render_template('partials/translation_status.html', state=state)

@api_bp.route('/metrics/resources', methods=['GET'])
@htmx_response
def get_system_resources():
    m = get_system_metrics()
    return render_template('partials/system_resources.html', metrics=m)

@api_bp.route('/metrics/analytics', methods=['GET'])
@htmx_response
def get_core_analytics():
    stats = analytics_repo.get_summary_stats()
    return render_template('partials/core_analytics.html', stats=stats, is_admin=session.get('is_admin'))

@api_bp.route('/metrics/analytics', methods=['DELETE'])
@admin_required
@htmx_response
def clear_analytics():
    analytics_repo.clear_logs()
    return get_core_analytics()

@api_bp.route('/metrics/logs', methods=['GET'])
@htmx_response
def get_recent_errors():
    log_path = os.path.join(current_app.root_path, '..', 'logs', 'error.log')
    if not os.path.exists(log_path):
        return render_helpers.render_empty_state(t('No error logs recorded.'))
        
    with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
        all_lines = f.readlines()
        
        boot_signature = "Proglem App instance created."
        start_index = 0
        for i in range(len(all_lines) - 1, -1, -1):
            if boot_signature in all_lines[i]:
                start_index = i
                break
        
        session_lines = all_lines[start_index:]
        tail = session_lines[-50:]
        return render_template('partials/error_logs.html', lines=tail)


@api_bp.route('/metrics/ai-logs', methods=['GET'])
@htmx_response
def get_ai_logs():
    """Returns a list of recent AI service events from the database."""
    logs = analytics_repo.get_ai_logs(limit=3)
    return render_template('partials/ai_logs.html', logs=logs)


@api_bp.route('/jams', methods=['GET'])
@admin_required
@htmx_response
def list_jams_admin():
    """Returns the jam management table HTML for the admin panel."""
    jams = jam_repo.get_all_jams()
    now = datetime.datetime.utcnow().isoformat()
    return render_template('partials/jam_admin_table.html', jams=[vars(j) for j in jams], now=now)


@api_bp.route('/jams', methods=['POST'])
@admin_required
@htmx_response
def create_jam():
    """Creates a new Game Jam."""
    title = request.form.get('title', '').strip()
    theme = request.form.get('theme', '').strip()
    start_time = request.form.get('start_time', '').strip()
    end_time = request.form.get('end_time', '').strip()
    youtube_url = request.form.get('youtube_url', '').strip() or None

    if not all([title, theme, start_time, end_time]):
        raise ValueError(t('All fields except YouTube URL are required.'))

    # Normalize datetime-local format to ISO
    start_time = start_time.replace('T', ' ')
    end_time = end_time.replace('T', ' ')

    jam_repo.create_jam(title, theme, start_time, end_time, youtube_url)
    return list_jams_admin()


@api_bp.route('/jams/<int:jam_id>/edit_form', methods=['GET'])
@admin_required
@htmx_response
def get_jam_edit_form(jam_id):
    """Returns an inline edit row for the given jam."""
    jam = jam_repo.get_jam_by_id(jam_id)
    if not jam:
        return t("Not Found"), 404
    return render_template('partials/jam_edit_row.html', jam=vars(jam))


@api_bp.route('/jams/<int:jam_id>', methods=['PUT'])
@admin_required
@htmx_response
def update_jam(jam_id):
    """Updates an existing Game Jam."""
    title = request.form.get('title', '').strip()
    theme = request.form.get('theme', '').strip()
    start_time = request.form.get('start_time', '').strip().replace('T', ' ')
    end_time = request.form.get('end_time', '').strip().replace('T', ' ')
    youtube_url = request.form.get('youtube_url', '').strip() or None

    if not all([title, theme, start_time, end_time]):
        raise ValueError(t('All fields are required.'))

    jam_repo.update_jam(jam_id, title, theme, start_time, end_time, youtube_url)
    return list_jams_admin()


@api_bp.route('/jams/<int:jam_id>', methods=['DELETE'])
@admin_required
@htmx_response
def delete_jam(jam_id):
    """Deletes a jam and nulls out jam_id on associated games (preserves game entries)."""
    jam_repo.delete_jam(jam_id)
    return render_helpers.render_empty_response()  # HTMX removes the row

