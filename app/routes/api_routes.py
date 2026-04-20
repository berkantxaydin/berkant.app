import os
import json
import boto3
from flask import Blueprint, jsonify, request, current_app, session, redirect

from app.repositories.cv_repository import CVRepository
from app.repositories.game_repository import GameRepository
from app.repositories.chat_repository import ChatRepository
from app.repositories.jam_repository import JamRepository
from app.repositories.analytics_repository import AnalyticsRepository
from app.routes.auth_routes import login_required, admin_required
from app.database import get_db_connection
from app.i18n import t
from markupsafe import escape
from datetime import datetime, timedelta
import logging

api_bp = Blueprint('api', __name__, url_prefix='/api')

# Instantiate repositories for DAL access
cv_repo = CVRepository()
game_repo = GameRepository()
chat_repo = ChatRepository()
jam_repo = JamRepository()
analytics_repo = AnalyticsRepository()


# --- CV CATALOG ---
@api_bp.route('/cv', methods=['GET'])
def get_cvs():
    search = request.args.get('search', '')
    try:
        results = cv_repo.get_all_cvs(search)
        # If HTMX, return grid partial
        if 'HX-Request' in request.headers:
            html = ""
            for cv in results:
                # Truncate and escape summary for card view
                clean_title = escape(cv.title)
                clean_username = escape(cv.username)
                short_summary = escape(cv.summary[:85]) + '...' if len(cv.summary) > 85 else escape(cv.summary)
                html += f"""
                <article class="glass-panel" onclick="window.location.href='/cv/{cv.id}'" 
                         style="cursor: pointer; display: flex; flex-direction: column; padding: 1.5rem 2rem; min-height: 220px; transition: transform 0.2s;">
                    <header style="margin-bottom: 0.8rem; border: 0; padding: 0 0 0 1.2rem; background: transparent;">
                        <h4 class="accent-text" style="margin-bottom:0; font-size: 1.25rem;">{clean_title}</h4>
                        <small style="opacity: 0.6; display: block; margin-top: 0.2rem;">@{clean_username}</small>
                    </header>
                    <p style="font-size:0.95rem; flex-grow: 1; padding-left: 1.2rem; opacity: 0.9; line-height: 1.4;">{short_summary}</p>
                    <footer style="margin-top: 1.2rem; border: 0; padding: 0; background: transparent; text-align: left;">
                        <button class="outline" style="padding: 0.3rem 1rem; font-size: 0.8rem; border-radius: 4px;">{t('View Profile')}</button>
                    </footer>
                </article>"""
            return html
        return jsonify({"status": "success", "count": len(results), "data": [vars(cv) for cv in results]}), 200
    except Exception as e:
        current_app.logger.error(f"Error querying CVs: {e}")
        return jsonify({"error": "Internal server error"}), 500

@api_bp.route('/cv/<int:cv_id>/htmx', methods=['GET'])
def get_cv_htmx(cv_id):
    """Returns the custom interactive HTMX content for a specific CV profile."""
    try:
        cv = cv_repo.get_cv_by_id(cv_id)
        if not cv:
            return f"<p>{t('CV not found')}</p>", 404
        # Return the custom HTMX or a fallback if empty
        return cv.custom_htmx or f"<p>{t('This developer has not added an interactive resume yet.')}</p>"
    except Exception as e:
        current_app.logger.error(f"Error fetching CV HTMX: {e}")
        return f"<p>{t('Internal Server Error')}</p>", 500

@api_bp.route('/cv/create', methods=['POST'])
@login_required
def create_ecom_cv():
    from flask import session
    user_id = session['user_id']  # Always use the authenticated session user
    title = request.form.get('title')
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
        
    try:
        cv_id = cv_repo.add_cv(user_id, title, summary, cv_data, custom_htmx=custom_htmx)
        return redirect(f'/cv/{cv_id}')


    except Exception as e:
        current_app.logger.error(f"Database error while saving CV: {e}")
        return jsonify({"error": "Failed to create CV"}), 500


# --- GAME JAM / UPLOADS ---
@api_bp.route('/jam/get-upload-url', methods=['GET'])
@api_bp.route('/jam/get_upload_url', methods=['GET'])
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

    try:
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
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api_bp.route('/jam/mock_upload', methods=['POST'])
def mock_upload():
    """Local simulation of S3 Post object handling for offline testing"""
    import urllib.parse
    raw_key = request.form.get('key')
    # Web-safe S3 keys generated locally might carry strict URI encoding (e.g. %20 for spaces)
    # We must explicitly decode them so the physical Flask filesystem routing matches identically!
    key = urllib.parse.unquote_plus(raw_key) if raw_key else None
    file = request.files.get('file')
    
    if key and file:
        import os
        filepath = os.path.join(current_app.root_path, 'static', 'mock_s3', key)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        file.save(filepath)
        return '', 204
    return 'Bad Request', 400

@api_bp.route('/jam/submit', methods=['POST'])
@login_required
def submit_game():
    data = request.json
    try:
        from app.services.game_validator import submit_validation_job
        game_id = game_repo.add_game(session['user_id'], data['title'], data.get('description', ''), data['game_url'], data.get('jam_id'))
        
        # Fire and forget our Mutex UUID validation background task
        job_uid = submit_validation_job(game_id, data['game_url'])
        
        return jsonify({"message": "Validating WebGL Sandbox Integrity...", "id": game_id, "job_uid": job_uid}), 201
    except Exception as e:
        current_app.logger.error(f"Game pipeline failure: {e}")
        return jsonify({"error": "Failed to track game"}), 500

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
def delete_cv_htmx(cv_id):
    success = cv_repo.delete_cv(cv_id, session['user_id'], is_admin=session.get('is_admin'))
    if success: return "" 
    return "Error deleting CV. Unauthorized.", 403

@api_bp.route('/cv/<int:cv_id>/edit', methods=['GET'])
@login_required
def get_cv_edit_form(cv_id):
    cv = cv_repo.get_cv_by_id(cv_id)
    if not cv or (cv.user_id != session['user_id'] and not session.get('is_admin')):
        return "Unauthorized", 403
    return f"""
    <form hx-put="/api/cv/{cv_id}" hx-target="closest article" hx-swap="outerHTML">
        <label>{t('Title')}
            <input type="text" name="title" value="{escape(cv.title)}" required>
        </label>
        <label>{t('Summary')}
            <textarea name="summary" required>{escape(cv.summary)}</textarea>
        </label>
        <div class="grid">
            <button type="submit">{t('Save Changes')}</button>
            <button type="button" class="secondary" onclick="window.location.reload()">{t('Cancel')}</button>
        </div>
    </form>
    """


@api_bp.route('/cv/<int:cv_id>', methods=['PUT'])
@login_required
def update_cv_htmx(cv_id):
    title = request.form.get('title')
    summary = request.form.get('summary')
    success = cv_repo.update_cv(cv_id, session['user_id'], title, summary, is_admin=session.get('is_admin'))
    if success:
        return f"""
        <article>
            <header>
                <strong>{escape(title)}</strong>
                <a href="#" hx-get="/api/cv/{cv_id}/edit" hx-target="closest article" hx-swap="outerHTML" style="float:right;">{t('Edit')}</a>
                <a href="#" hx-delete="/api/cv/{cv_id}" hx-target="closest article" hx-swap="outerHTML" style="float:right; margin-right: 1rem; color: var(--pico-del-color);">{t('Delete')}</a>
            </header>
            <p>{escape(summary)}</p>
        </article>
        """
    return t("Update failed"), 400

@api_bp.route('/jam/<int:game_id>', methods=['DELETE'])
@login_required
def delete_game_htmx(game_id):
    success = game_repo.delete_game(game_id, session['user_id'], is_admin=session.get('is_admin'))
    if success: return ""
    return "Unauthorized", 403

# --- SOCIAL FEATURES: LIKES & COMMENTS ---

@api_bp.route('/games/like/<int:game_id>', methods=['POST'])
@login_required
def like_game(game_id):
    """Toggles a like on a game."""
    uid = session['user_id']
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM Game_Likes WHERE user_id = ? AND game_id = ?", (uid, game_id))
        existing = cursor.fetchone()
        
        if existing:
            cursor.execute("DELETE FROM Game_Likes WHERE id = ?", (existing['id'],))
            conn.commit()
            icon = "🤍"
        else:
            cursor.execute("INSERT INTO Game_Likes (user_id, game_id) VALUES (?, ?)", (uid, game_id))
            conn.commit()
            icon = "❤️"
            
        cursor.execute("SELECT COUNT(*) as cnt FROM Game_Likes WHERE game_id = ?", (game_id,))
        count = cursor.fetchone()['cnt']
        is_now_liked = (existing is None)
        btn_class = "secondary" if is_now_liked else "outline"
        return f'<button hx-post="/api/games/like/{game_id}" hx-swap="outerHTML" class="{btn_class}">❤️ {count}</button>'
    finally:
        conn.close()


@api_bp.route('/games/<int:game_id>/comments', methods=['POST'])
@login_required
def post_game_comment(game_id):
    """Saves a comment and returns the new comment list snippet for HTMX."""
    from flask import render_template_string
    uid = session['user_id']
    content = request.form.get('content', '').strip()
    
    if not content:
        return "Comment cannot be empty", 400
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO Game_Comments (user_id, game_id, content) VALUES (?, ?, ?)", (uid, game_id, content))
        conn.commit()
        
        # Fetch all comments to refresh the list via HTMX
        cursor.execute("""
            SELECT c.*, u.username 
            FROM Game_Comments c 
            JOIN Users u ON c.user_id = u.id 
            WHERE c.game_id = ? 
            ORDER BY c.created_at DESC
        """, (game_id,))
        comments = cursor.fetchall()
        
        return render_template_string("""
            {% for comment in comments %}
            <article style="padding: 1rem; margin-bottom: 1rem; background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.1);">
                <header style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; background: transparent; border: 0; padding: 0;">
                    <strong>@{{ comment.username }}</strong>
                    <small>{{ comment.created_at }}</small>
                </header>
                <p style="margin-bottom: 0.5rem;">{{ comment.content }}</p>
                {% if session.get('is_admin') or session.get('user_id') == comment.user_id %}
                <footer style="margin-top: 0.5rem; text-align: right; background: transparent; border: 0; padding: 0;">
                    <a href="#" hx-delete="/api/comments/{{ comment.id }}" hx-target="closest article" hx-swap="outerHTML" class="contrast" style="font-size: 0.8rem;">Delete</a>
                </footer>
                {% endif %}
            </article>
            {% endfor %}
            <form hx-post="/api/games/{{ game_id }}/comments" hx-target="#comment-list" hx-on::after-request="this.reset()" style="margin-top: 1.5rem;">
                <fieldset role="group">
                    <input type="text" name="content" placeholder="Write a comment..." required>
                    <button type="submit" class="outline">Post</button>
                </fieldset>
            </form>
        """, comments=comments, game_id=game_id)
    finally:
        conn.close()

@api_bp.route('/comments/<int:comment_id>', methods=['DELETE'])
@login_required
def delete_game_comment(comment_id):
    """Deletes a comment if the user is an admin or the author."""
    uid = session['user_id']
    is_admin = session.get('is_admin', False)
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        if not is_admin:
            cursor.execute("SELECT user_id FROM Game_Comments WHERE id = ?", (comment_id,))
            comment = cursor.fetchone()
            if not comment or comment['user_id'] != uid:
                return f"{t('Unauthorized')}", 403
                
        cursor.execute("DELETE FROM Game_Comments WHERE id = ?", (comment_id,))
        conn.commit()
        return "" # HTMX removes the closest article
    finally:
        conn.close()

# --- CHAT ROOMS ---

def _render_messages(room_id):
    """Shared helper: renders message list HTML for a given room_id."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        # GET last 60 messages, then reverse them so newest is at the bottom
        c.execute('''
            SELECT c.*, u.username, u.is_admin
            FROM Chat_Messages c
            JOIN Users u ON c.user_id = u.id
            WHERE c.room_id = ?
            ORDER BY c.created_at DESC LIMIT 60
        ''', (room_id,))
        messages = [dict(row) for row in c.fetchall()]
        messages.reverse() # Newest at the bottom
    finally:
        conn.close()

    if not messages:
        return f"<p class='text-center' style='color: grey;'><small>{t('No messages yet. Start the conversation!')}</small></p>"

    html = ""
    current_user_id = session.get('user_id')
    is_admin = session.get('is_admin', False)

    for msg in messages:
        is_self = (msg['user_id'] == current_user_id)
        can_delete = is_admin or is_self
        
        # Define classes for orientation and styling
        align_class = "self" if is_self else ""
        bubble_class = "primary" if is_self else ""
        
        name_color = "var(--pico-primary)" if msg['is_admin'] else "#e2e8f0"
        badge = "&#x1F468;&#x200D;&#x1F4BB; " if msg['is_admin'] else ""
        
        # Format time
        time_str = msg['created_at'].split(' ')[1][:5] if ' ' in msg['created_at'] else msg['created_at'][:5]

        delete_btn = ""
        if can_delete:
            delete_btn = f"""<a href="#" hx-delete="/api/chat/messages/{msg['id']}"
                hx-target="closest .chat-message" hx-swap="outerHTML"
                style="color: var(--pico-del-color); cursor: pointer; text-decoration: none; font-weight: bold; font-size: 1rem;"
                title="{t('Delete')}">&#x2A2F;</a>"""

        html += f"""
        <div id="chat-msg-{msg['id']}" class="chat-message {align_class}" style="margin-bottom: 0.3rem; animation: slideIn 0.3s ease-out forwards;">
            <div class="chat-bubble {bubble_class}" style="padding: 0.5rem 0.8rem; border-radius: 0.8rem; max-width: 85%; position: relative; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
                <header style="margin-bottom: 0.2rem; display: flex; justify-content: space-between; align-items: center; gap: 1rem; background: transparent; border: 0; padding: 0;">
                    <strong style="font-size: 0.8rem; color: {name_color};">{badge}{escape(msg['username'])}</strong>
                </header>
                <div class="chat-content" style="font-size: 0.9rem; line-height: 1.4; color: #f1f5f9; word-wrap: break-word;">
                    {escape(msg['content'])}
                </div>
                <div style="display:flex; justify-content:flex-end; align-items:center; margin-top: 0.2rem; gap: 0.4rem;">
                    <small style="color: #94a3b8; font-size: 0.65rem;">
                        <time datetime="{msg['created_at']}Z" class="chat-time">{time_str}</time>
                    </small>
                    {delete_btn}
                </div>
            </div>
        </div>"""

    from flask import make_response
    resp = make_response(html)
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return resp


@api_bp.route('/chat/rooms', methods=['GET'])
def get_chat_rooms():
    """Returns all enabled rooms as an HTMX tab snippet."""
    rooms = chat_repo.get_rooms(admin_view=session.get('is_admin', False))
    return jsonify(rooms)



@api_bp.route('/chat/messages', methods=['GET'])
def get_chat_messages():
    """Returns HTML for HTMX polling — room_id from query string (defaults to 1)."""
    try:
        room_id = int(request.args.get('room_id', 1))
    except (ValueError, TypeError):
        room_id = 1
    return _render_messages(room_id)


@api_bp.route('/chat/messages', methods=['POST'])
@login_required
def post_chat_message():
    """Posts a message to a specific room and returns the updated list."""
    uid = session['user_id']
    content = request.form.get('content', '').strip()
    try:
        room_id = int(request.form.get('room_id', 1))
    except (ValueError, TypeError):
        room_id = 1

    if not content:
        return f"{t('Message cannot be empty')}", 400

    # Verify room exists and is enabled
    try:
        if not chat_repo.get_room_by_id(room_id).get('is_enabled') and not session.get('is_admin'):
            return f"{t('This room is currently disabled.')}", 403
        chat_repo.add_message(uid, room_id, str(escape(content)))
    except Exception as e:
        current_app.logger.error(f"Chat error: {e}")
        return f"{t('Failed to send message')}", 500


    return _render_messages(room_id)


@api_bp.route('/chat/messages/<int:msg_id>', methods=['DELETE'])
@login_required
def delete_chat_message(msg_id):
    """Deletes a chat message if the user is the author or an admin."""
    uid = session['user_id']
    is_admin = session.get('is_admin', False)
    chat_repo.delete_message(msg_id, user_id=uid, is_admin=is_admin)
    return ""  # HTMX removes the element



# --- CHAT ROOM ADMIN CRUD ---

def _render_room_admin_table():
    """Renders the room management table for the admin panel."""
    rooms = chat_repo.get_rooms(admin_view=True)


    rows = ""
    for r in rooms:
        jam_label = f"Jam: {r['jam_title']}" if r['jam_title'] else "—"
        enabled_badge = '<span class="badge badge-active">On</span>' if r['is_enabled'] else '<span class="badge badge-ended">Off</span>'
        toggle_label = "Disable" if r['is_enabled'] else "Enable"
        toggle_class = "outline contrast" if r['is_enabled'] else "outline"
        # Prevent deletion of General room
        delete_btn = "" if r['name'] == '💬 General' else f"""
            <button class="outline contrast" style="padding:0.3rem 0.7rem; font-size:0.8rem;"
                hx-delete="/api/chat/rooms/{r['id']}"
                hx-target="#chat-room-admin-table"
                hx-swap="outerHTML"
                hx-confirm="{t('Delete room')} '{r['name']}'? {t('All messages will be lost.')}">{t('Delete')}</button>"""

        rows += f"""
        <tr id="chat-room-row-{r['id']}">
            <td>{escape(r['name'])}</td>
            <td>{escape(jam_label)}</td>
            <td>{enabled_badge}</td>
            <td style="display:flex; gap:0.4rem; flex-wrap:wrap;">
                <button class="{toggle_class}" style="padding:0.3rem 0.7rem; font-size:0.8rem;"
                    hx-patch="/api/chat/rooms/{r['id']}/toggle"
                    hx-target="#chat-room-admin-table"
                    hx-swap="outerHTML">{toggle_label}</button>
                {delete_btn}
            </td>
        </tr>"""

    if not rows:
        rows = f"<tr><td colspan='4' style='text-align:center; color:grey;'>{t('No rooms.')}</td></tr>"

    return f"""<table id="chat-room-admin-table">
        <thead><tr><th>{t('Room Name')}</th><th>{t('Linked Jam')}</th><th>{t('Status')}</th><th>{t('Actions')}</th></tr></thead>
        <tbody>{rows}</tbody>
    </table>"""


@api_bp.route('/chat/rooms/admin', methods=['GET'])
@admin_required
def list_chat_rooms_admin():
    return _render_room_admin_table()


@api_bp.route('/chat/rooms', methods=['POST'])
@admin_required
def create_chat_room():
    """Creates a new standalone chat room."""
    name = request.form.get('name', '').strip()
    if not name:
        return f"<p style='color:var(--pico-del-color);'>{t('Room name is required.')}</p>", 400
    chat_repo.create_room(name)
    return _render_room_admin_table()



@api_bp.route('/chat/rooms/<int:room_id>/toggle', methods=['PATCH'])
@admin_required
def toggle_chat_room(room_id):
    """Flips the is_enabled flag on a room."""
    chat_repo.toggle_room(room_id)
    return _render_room_admin_table()


@api_bp.route('/chat/rooms/<int:room_id>', methods=['DELETE'])
@admin_required
def delete_chat_room(room_id):
    """Deletes a room and all its messages."""
    chat_repo.delete_room(room_id)
    return _render_room_admin_table()

@api_bp.route('/admin/translate_missing', methods=['POST'])
@admin_required
def translate_missing():
    from app.i18n import translations
    
    missing_keys = [k for k in translations.get('en', {}) if k not in translations.get('tr', {})]
    if not missing_keys:
        return f"<p style='color:var(--pico-primary);'>{t('All keys are already translated!')}</p>"
    
    def background_translation_job(all_keys):
        import urllib.request
        import json
        import time
        from app.i18n import save_translations
        import app.i18n

        # Break into chunks of 15 to avoid model context/timeout limits
        chunk_size = 15
        chunks = [all_keys[i:i + chunk_size] for i in range(0, len(all_keys), chunk_size)]
        
        print(f"Starting background translation for {len(all_keys)} keys in {len(chunks)} batches.")

        for idx, keys_chunk in enumerate(chunks):
            print(f"Processing batch {idx+1}/{len(chunks)} ({len(keys_chunk)} keys)...")
            
            prompt = "Translate the following UI English strings exactly to Turkish. Respond ONLY with a valid JSON object mapping the English key to the Turkish translation. No code blocks, no markdown, just RAW JSON.\nKeys:\n" + json.dumps(keys_chunk)
            
            payload = {
                "model": "local-model",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 2048,
                "temperature": 0.2
            }
            
            try:
                req = urllib.request.Request(f"http://127.0.0.1:8082/v1/chat/completions",
                    data=json.dumps(payload).encode('utf-8'),
                    headers={"Content-Type": "application/json", "Authorization": "Bearer admin"})
                
                # Higher timeout (300s) for slow local generation
                with urllib.request.urlopen(req, timeout=300) as response: # nosec B310
                    result = json.loads(response.read().decode('utf-8'))
                    raw_content = result['choices'][0]['message']['content']
                    
                    # Clean up model garbage if present
                    if "```json" in raw_content:
                        raw_content = raw_content.split("```json")[-1].split("```")[0]
                    elif "```" in raw_content:
                        raw_content = raw_content.split("```")[-1].split("```")[0]
                    
                    new_translations = json.loads(raw_content.strip())
                    
                    if 'tr' not in translations: translations['tr'] = {}
                    for k, v in new_translations.items():
                        if k in keys_chunk:
                            translations['tr'][k] = v
                    
                    # Save after each successful chunk
                    app.i18n._dirty = True
                    save_translations()
                    print(f"Batch {idx+1} saved successfully.")
                    
            except Exception as e:
                print(f"Error in batch {idx+1}: {e}")
                # Brief sleep before retry or next batch
                time.sleep(2)
                
        print("Background translation job complete.")
            
    import threading
    threading.Thread(target=background_translation_job, args=(missing_keys,), daemon=True).start()
    
    return f"<p style='color:var(--pico-primary);'><i>{t('Translation job sent to AI Core in background. Progress will be saved incrementally. Refresh later!')}</i></p>"

# --- SYSTEM METRICS (DASHBOARD) ---
@api_bp.route('/metrics/resources', methods=['GET'])
def get_system_resources():
    import psutil
    import time as _time
    _t0 = _time.monotonic()
    
    # 1. Global Metrics — interval=0.5 blocks briefly but gives a real non-zero reading
    cpu_usage = psutil.cpu_percent(interval=0.5)
    sys_ram = psutil.virtual_memory()
    
    # 2. AI Specific Metrics
    ai_ram_mb = 0
    try:
        from app.services.ai_service import ai_processes
        proc = ai_processes.get('chat')
        if proc and proc.poll() is None:
            p = psutil.Process(proc.pid)
            ai_ram_mb = p.memory_info().rss / (1024 * 1024)
    except Exception:
        pass
    
    # User has 16GB RAM budget
    budget_mb = 16384
    global_ram_percent = sys_ram.percent
    ai_ram_percent = min((ai_ram_mb / budget_mb) * 100, 100)
    
    return f"""
    <style>
        @keyframes pulse-dot {{
            0% {{ transform: scale(0.95); opacity: 0.5; }}
            50% {{ transform: scale(1.1); opacity: 1; }}
            100% {{ transform: scale(0.95); opacity: 0.5; }}
        }}
        @keyframes stripe-move {{
            0% {{ background-position: 0 0; }}
            100% {{ background-position: 30px 30px; }}
        }}
        .live-dot {{
            height: 8px;
            width: 8px;
            background-color: #22c55e;
            border-radius: 50%;
            display: inline-block;
            margin-right: 8px;
            animation: pulse-dot 2s infinite ease-in-out;
        }}
        .metric-bar-container {{
            width: 100%;
            height: 12px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 6px;
            overflow: hidden;
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: inset 0 1px 3px rgba(0,0,0,0.3);
        }}
        .metric-bar-fill {{
            height: 100%;
            border-radius: 6px;
            transition: width 1s cubic-bezier(0.4, 0, 0.2, 1);
            background-image: linear-gradient(
                45deg, 
                rgba(255, 255, 255, 0.15) 25%, 
                transparent 25%, 
                transparent 50%, 
                rgba(255, 255, 255, 0.15) 50%, 
                rgba(255, 255, 255, 0.15) 75%, 
                transparent 75%, 
                transparent
            );
            background-size: 1rem 1rem;
            animation: stripe-move 1s linear infinite;
        }}
        .cpu-bar {{ background-color: {'var(--pico-del-color)' if cpu_usage > 90 else 'var(--pico-primary)'}; box-shadow: 0 0 10px {'var(--pico-del-color)' if cpu_usage > 90 else 'var(--pico-primary)'}; }}
        .ram-bar {{ background-color: {'var(--pico-del-color)' if global_ram_percent > 85 else 'var(--pico-primary)'}; box-shadow: 0 0 10px {'var(--pico-del-color)' if global_ram_percent > 85 else 'var(--pico-primary)'}; }}
        .ai-bar {{ background-color: #3b82f6; box-shadow: 0 0 10px rgba(59, 130, 246, 0.6); }}
        
        .metric-label-group {{
            display: flex; justify-content: space-between; align-items: center; font-size: 0.9rem; margin-bottom: 0.4rem;
        }}
        .mono-val {{ font-family: monospace; font-size: 1rem; font-weight: 600; text-shadow: 0 0 5px rgba(255,255,255,0.2); }}
    </style>
    <div style="display: flex; flex-direction: column; gap: 1.2rem; padding-top: 0.5rem;">
        <!-- CPU USAGE -->
        <div>
            <div class="metric-label-group">
                <strong style="display:flex; align-items:center;"><span class="live-dot"></span>{t("Global CPU Usage")}</strong>
                <span class="accent-text mono-val">{cpu_usage:.1f}%</span>
            </div>
            <div class="metric-bar-container">
                <div class="metric-bar-fill cpu-bar" style="width: {cpu_usage}%;"></div>
            </div>
        </div>

        <!-- TOTAL RAM -->
        <div>
            <div class="metric-label-group">
                <strong style="display:flex; align-items:center;"><span class="live-dot" style="background-color: #eab308; animation-delay: 0.5s;"></span>{t("Global RAM & AI (16GB)")}</strong>
                <span class="accent-text mono-val">{sys_ram.used / (1024**3):.1f} / 16 GB</span>
            </div>
            <div class="metric-bar-container" style="display: flex;">
                <div class="metric-bar-fill ai-bar" style="width: {ai_ram_percent}%; border-radius: 0;"></div>
                <div class="metric-bar-fill ram-bar" style="width: {max(0, sys_ram.percent - ai_ram_percent)}%; border-radius: 0;"></div>
            </div>
            <div style="display:flex; justify-content: space-between; font-size: 0.75rem; margin-top: 0.4rem; color: #94a3b8; font-weight: 500;">
                <span>{t("System")}: {max(0, (sys_ram.used/1024**3) - (ai_ram_mb/1024)):.1f} GB</span>
                <span style="color: #60a5fa;">{t("AI Core")}: {ai_ram_mb:.0f} MB</span>
            </div>
        </div>
        
        <small style="font-size: 0.75rem; opacity: 0.6; text-align: center; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 0.8rem; margin-top: 0.2rem; display: block;">
            {t("Live Telemetry")} &bull; {t("Response")}: {int((_time.monotonic() - _t0) * 1000)}ms &bull; Qwen 2.5 7B {t("Active")}
        </small>
    </div>
    """

@api_bp.route('/metrics/analytics', methods=['GET'])
def get_core_analytics():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Refined query: Unique Devices (cookies), Total Views (non-HTMX GETs), and All Traffic
        cursor.execute("""
            SELECT 
                COUNT(*) as total_traffic,
                COUNT(*) FILTER (WHERE is_htmx = 0 AND method = 'GET' AND path NOT LIKE '/api/%' AND path != '/health') as page_views,
                COUNT(*) FILTER (WHERE status_code >= 400) as errors,
                COUNT(DISTINCT visitor_id) as unique_devices,
                AVG(duration_ms) as avg_ms 
            FROM Analytics_Logs
        """)
        row = cursor.fetchone()
        
        total_traffic = row['total_traffic'] or 0
        page_views = row['page_views'] or 0
        errors = row['errors'] or 0
        unique_devices = row['unique_devices'] or 0
        avg_ms = int(row['avg_ms'] or 0)
        
        error_rate = 0
        if total_traffic > 0:
            error_rate = (errors / total_traffic) * 100
        
        admin_controls = ""
        if session.get('is_admin'):
            admin_controls = f"""
            <footer style="margin-top: 1rem; border:0; background: transparent;">
                <button class="outline contrast" 
                        hx-delete="/api/metrics/analytics" 
                        hx-target="#aspire-analytics" 
                        hx-confirm="{t('Clear all traffic analytics?')}">
                    {t("Clear Traffic Logs")}
                </button>
            </footer>
            """
        
        return f"""
        <div style="text-align: center;">
            <div class="grid">
                <article style="padding: 1rem;">
                    <h2 style="margin-bottom: 0; color: var(--pico-primary); font-family: var(--font-mono);">{page_views}</h2>
                    <small>{t("Page Views")}</small>
                </article>
                <article style="padding: 1rem;">
                    <h2 style="margin-bottom: 0; color: var(--pico-primary); font-family: var(--font-mono);">{unique_devices}</h2>
                    <small>{t("Unique Devices")}</small>
                </article>
                <article style="padding: 1rem;">
                    <h2 style="margin-bottom: 0; color: {'var(--pico-del-color)' if error_rate > 5 else 'var(--pico-primary)'}; font-family: var(--font-mono);">{error_rate:.1f}%</h2>
                    <small>{t("Error Rate")}</small>
                </article>
            </div>
            <p style="margin-top: 0.5rem;"><small>{t("Overall Traffic")}: <strong>{total_traffic}</strong> &bull; {t("Avg Latency")}: <strong style="font-family: var(--font-mono);">{avg_ms}ms</strong></small></p>
            {admin_controls}
        </div>
        """
    finally:
        conn.close()

@api_bp.route('/metrics/analytics', methods=['DELETE'])
@admin_required
def clear_analytics():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Analytics_Logs")
        conn.commit()
        return get_core_analytics() # Refresh the view
    finally:
        conn.close()

@api_bp.route('/metrics/logs', methods=['GET'])
def get_recent_errors():
    import os
    from flask import current_app
    log_path = os.path.join(current_app.root_path, '..', 'logs', 'error.log')
    if not os.path.exists(log_path):
        return f"<p><em>{t('No error logs recorded.')}</em></p>"
        
    try:
        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            all_lines = f.readlines()
            
            # Find the start of the current session
            boot_signature = "Proglem App instance created and logger configured."
            start_index = 0
            for i in range(len(all_lines) - 1, -1, -1):
                if boot_signature in all_lines[i]:
                    start_index = i
                    break
            
            # Slice from the last boot and take up to 50 latest lines
            session_lines = all_lines[start_index:]
            tail = session_lines[-50:]
            
            if not tail:
                return f"<p><em>{t('Session log empty.')}</em></p>"
            
            html = "<div style='font-family: var(--font-mono); font-size: 0.75rem; overflow-x: auto; white-space: pre;'>"
            for line in reversed(tail):
                # Strip year (assuming 20XX-MM-DD format)
                clean_line = line.strip()
                if clean_line.startswith("20") and "-" in clean_line[:5]:
                    clean_line = clean_line[5:] # Strip "2026-"
                
                color = "var(--pico-del-color)" if "ERROR" in clean_line or "CRITICAL" in clean_line else "var(--pico-color)"
                html += f"<div style='color: {color}; border-bottom: 1px solid rgba(255,255,255,0.05); padding: 0.2rem 0;'>{clean_line}</div>"
            html += "</div>"
            return html
    except Exception as e:
        return f"<p>{t('Error reading logs')}: {e}</p>"


@api_bp.route('/metrics/ai-logs', methods=['GET'])
def get_ai_logs():
    """Returns a list of recent AI service events from the database."""
    from app.database import get_db_connection
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Fetch latest 3 system logs
        cursor.execute("SELECT * FROM AI_System_Logs ORDER BY id DESC LIMIT 3")
        logs = cursor.fetchall()
        
        if not logs:
            return f"<p style='color: grey; text-align: center; margin-top: 1rem;'><em>{t('No AI lifecycle events recorded yet.')}</em></p>"
        
        # Build clean HTML without 'white-space: pre' to avoid indentation gaps
        html_lines = []
        for log in reversed(logs):
            status_color = "var(--pico-del-color)" if log['status'] == 'ERROR' else ("#eab308" if log['status'] == 'WARNING' else "var(--pico-primary)")
            # Strip date for brevity
            ts = log['created_at'].split(' ')[1][:8] if ' ' in log['created_at'] else log['created_at']
            
            line = (
                f'<div style="border-bottom: 1px solid rgba(255,255,255,0.05); padding: 0.3rem 0; line-height: 1.2;">'
                f'<span style="color: #64748b; font-family: var(--font-mono); margin-right: 8px;">[{ts}]</span>'
                f'<strong style="color: {status_color}; font-family: var(--font-mono); margin-right: 8px;">[{log["event_type"]}]</strong>'
                f'<span style="color: #cbd5e1;">{escape(log["message"])}</span>'
                f'</div>'
            )
            html_lines.append(line)
        
        return f"""
        <div style="display: flex; flex-direction: column;">
            <div style="font-size: 0.75rem; overflow-x: auto;">
                {"".join(html_lines)}
            </div>
        </div>
        """
    except Exception as e:
        return f"<p>{t('Error reading AI logs')}: {e}</p>"
    finally:
        conn.close()


# --- GAME JAM ADMIN CRUD ---

def _render_jam_admin_table():
    """Helper: renders the full jam management table as an HTMX snippet."""
    from app.database import get_db_connection
    import datetime
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Game_Jams ORDER BY start_time DESC")
        jams = [dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()

    now = datetime.datetime.utcnow().isoformat()
    rows = ""
    for j in jams:
        # Determine status label
        if j['start_time'] > now:
            status = f'<span class="badge badge-upcoming">{t("Upcoming")}</span>'
        elif j['end_time'] < now:
            status = f'<span class="badge badge-ended">{t("Ended")}</span>'
        else:
            status = f'<span class="badge badge-active">{t("Active")}</span>'

        rows += f"""
        <tr id="jam-row-{j['id']}">
            <td>{j['title']}</td>
            <td>{j['theme']}</td>
            <td>{j['start_time'][:16].replace('T',' ')}</td>
            <td>{j['end_time'][:16].replace('T',' ')}</td>
            <td>{status}</td>
            <td style="display:flex; gap:0.5rem; flex-wrap:wrap;">
                <button class="outline" style="padding:0.3rem 0.8rem; font-size:0.85rem;"
                    hx-get="/api/jams/{j['id']}/edit_form"
                    hx-target="#jam-row-{j['id']}"
                    hx-swap="outerHTML">{t("Edit")}</button>
                <button class="outline contrast" style="padding:0.3rem 0.8rem; font-size:0.85rem;"
                    hx-delete="/api/jams/{j['id']}"
                    hx-target="#jam-row-{j['id']}"
                    hx-swap="outerHTML"
                    hx-confirm="{t('Delete')} '{j['title']}'? {t('This removes all its submissions too.')}">{t("Delete")}</button>
            </td>
        </tr>"""

    if not rows:
        rows = f"<tr><td colspan='6' style='text-align:center; color:grey;'>{t('No jams yet. Create one below.')}</td></tr>"

    return f"""
    <table id="jam-admin-table">
        <thead><tr>
            <th>{t("Title")}</th><th>{t("Theme")}</th><th>{t("Start (UTC)")}</th><th>{t("End (UTC)")}</th><th>{t("Status")}</th><th>{t("Actions")}</th>
        </tr></thead>
        <tbody>{rows}</tbody>
    </table>"""


@api_bp.route('/jams', methods=['GET'])
@admin_required
def list_jams_admin():
    """Returns the jam management table HTML for the admin panel."""
    return _render_jam_admin_table()


@api_bp.route('/jams', methods=['POST'])
@admin_required
def create_jam():
    """Creates a new Game Jam."""
    from app.database import get_db_connection
    title = request.form.get('title', '').strip()
    theme = request.form.get('theme', '').strip()
    start_time = request.form.get('start_time', '').strip()
    end_time = request.form.get('end_time', '').strip()
    youtube_url = request.form.get('youtube_url', '').strip() or None

    if not all([title, theme, start_time, end_time]):
        return f"<p style='color:var(--pico-del-color);'>{t('All fields except YouTube URL are required.')}</p>", 400

    # Normalize datetime-local format to ISO (replace T with space)
    start_time = start_time.replace('T', ' ')
    end_time = end_time.replace('T', ' ')

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO Game_Jams (title, theme, start_time, end_time, youtube_url) VALUES (?, ?, ?, ?, ?)",
            (title, theme, start_time, end_time, youtube_url)
        )
        jam_id = cursor.lastrowid
        # Auto-create a linked chat room for this jam
        cursor.execute(
            "INSERT INTO Chat_Rooms (name, jam_id, is_enabled) VALUES (?, ?, 1)",
            (f"🎮 {title}", jam_id)
        )
        conn.commit()
    finally:
        conn.close()

    return _render_jam_admin_table()


@api_bp.route('/jams/<int:jam_id>/edit_form', methods=['GET'])
@admin_required
def get_jam_edit_form(jam_id):
    """Returns an inline edit row for the given jam."""
    from app.database import get_db_connection
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Game_Jams WHERE id = ?", (jam_id,))
        row = cursor.fetchone()
    finally:
        conn.close()

    if not row:
        return t("Not Found"), 404

    j = dict(row)
    # Convert stored " " back to "T" for datetime-local input
    start_val = j['start_time'][:16].replace(' ', 'T')
    end_val   = j['end_time'][:16].replace(' ', 'T')
    yt_val    = j['youtube_url'] or ''

    return f"""
    <tr id="jam-row-{j['id']}">
        <form hx-put="/api/jams/{j['id']}" hx-target="#jam-admin-table" hx-swap="outerHTML" style="display:contents;">
            <td><input name="title"       value="{j['title']}"  required style="margin:0;" /></td>
            <td><input name="theme"       value="{j['theme']}"  required style="margin:0;" /></td>
            <td><input name="start_time"  type="datetime-local" value="{start_val}" required style="margin:0;" /></td>
            <td><input name="end_time"    type="datetime-local" value="{end_val}"   required style="margin:0;" /></td>
            <td><input name="youtube_url" value="{yt_val}" placeholder="YouTube embed URL" style="margin:0;" /></td>
            <td style="display:flex; gap:0.5rem;">
                <button type="submit" style="padding:0.3rem 0.8rem; font-size:0.85rem;">{t("Save")}</button>
                <button type="button" class="outline secondary" style="padding:0.3rem 0.8rem; font-size:0.85rem;"
                    hx-get="/api/jams"
                    hx-target="#jam-admin-table"
                    hx-swap="outerHTML">{t("Cancel")}</button>
            </td>
        </form>
    </tr>"""


@api_bp.route('/jams/<int:jam_id>', methods=['PUT'])
@admin_required
def update_jam(jam_id):
    """Updates an existing Game Jam."""
    from app.database import get_db_connection
    title = request.form.get('title', '').strip()
    theme = request.form.get('theme', '').strip()
    start_time = request.form.get('start_time', '').strip().replace('T', ' ')
    end_time = request.form.get('end_time', '').strip().replace('T', ' ')
    youtube_url = request.form.get('youtube_url', '').strip() or None

    if not all([title, theme, start_time, end_time]):
        return f"<p style='color:var(--pico-del-color);'>{t('All fields are required.')}</p>", 400

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE Game_Jams SET title=?, theme=?, start_time=?, end_time=?, youtube_url=? WHERE id=?",
            (title, theme, start_time, end_time, youtube_url, jam_id)
        )
        conn.commit()
    finally:
        conn.close()

    return _render_jam_admin_table()


@api_bp.route('/jams/<int:jam_id>', methods=['DELETE'])
@admin_required
def delete_jam(jam_id):
    """Deletes a jam and nulls out jam_id on associated games (preserves game entries)."""
    from app.database import get_db_connection
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Detach games from this jam rather than deleting them
        cursor.execute("UPDATE Godot_Games SET jam_id = NULL WHERE jam_id = ?", (jam_id,))
        cursor.execute("DELETE FROM Game_Jams WHERE id = ?", (jam_id,))
        conn.commit()
    finally:
        conn.close()

    return ""  # HTMX removes the row

