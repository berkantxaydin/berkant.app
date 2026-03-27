import os
import random
import boto3
from botocore.exceptions import ClientError
from flask import Blueprint, jsonify, request, current_app, render_template_string
from app.repositories.cv_repository import CVRepository
from app.repositories.game_repository import GameRepository
from app.routes.auth_routes import login_required, admin_required

api_bp = Blueprint('api', __name__, url_prefix='/api')

# --- CV CATALOG ---
@api_bp.route('/cv', methods=['GET'])
def get_cvs():
    search = request.args.get('search', '')
    try:
        results = CVRepository.get_all_cvs(search_term=search)
        
        # If the request comes from HTMX, return an HTML partial instead of JSON
        if 'HX-Request' in request.headers:
            html = ""
            for cv in results:
                skills = ", ".join(cv['cv_data'].get('skills', []))
                html += f"""
                <article class="cv-card glass-panel" onclick="window.location.href='/cv/{cv['id']}'" style="cursor: pointer; transition: transform 0.2s ease;">
                    <header>
                        <hgroup>
                            <h3 class="accent-text">{cv['title']}</h3>
                            <p>by <strong>{cv['username']}</strong></p>
                        </hgroup>
                    </header>
                    <p>{cv['summary']}</p>
                    <footer>
                        <small>Skills: <em>{skills}</em></small>
                    </footer>
                </article>"""
            if not results:
                html = "<p>No CVs found matching that query.</p>"
            return html
            
        return jsonify({"status": "success", "count": len(results), "data": results}), 200
    except Exception as e:
        current_app.logger.error(f"Error querying CVs: {e}")
        return jsonify({"error": "Internal server error"}), 500

@api_bp.route('/cv/create', methods=['POST'])
def create_ecom_cv():
    user_id = request.form.get('user_id', 1)
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
        from flask import redirect
        cv_id = CVRepository.add_cv(user_id, title, summary, cv_data, custom_htmx=custom_htmx)
        return redirect(f'/cv/{cv_id}')
    except Exception as e:
        current_app.logger.error(f"Database error while saving CV: {e}")
        return jsonify({"error": "Failed to create CV"}), 500

@api_bp.route('/cv/<int:cv_id>/htmx', methods=['GET'])
def get_custom_htmx(cv_id):
    from app.database import get_db_connection
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT custom_htmx FROM CV_Catalog WHERE id = ?", (cv_id,))
        row = cursor.fetchone()
        if row and row['custom_htmx']:
            return row['custom_htmx']
        return "<p><em>No custom HTTP/HTMX interactive resume uploaded by this developer.</em></p>"
    finally:
        conn.close()

# --- GAME JAM / UPLOADS ---
@api_bp.route('/jam/get_upload_url', methods=['GET'])
def get_upload_url():
    """Generates a secure S3/R2 upload URL with explicitly locked MIME assignments to bypass local bandwidth limits."""
    filename = request.args.get('filename', 'default.bin')
    mime_type = request.args.get('content_type', 'application/octet-stream')
    
    s3_client = boto3.client(
        's3',
        endpoint_url=os.environ.get('R2_ENDPOINT_URL', "https://mock-endpoint.com"),
        aws_access_key_id=os.environ.get('R2_ACCESS_KEY_ID', 'test'),
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
        game_id = GameRepository.add_game(session['user_id'], data['title'], data.get('description', ''), data['game_url'], data.get('jam_id'))
        
        # Fire and forget our Mutex UUID validation background task
        job_uid = submit_validation_job(game_id, data['game_url'])
        
        return jsonify({"message": "Validating WebGL Sandbox Integrity...", "id": game_id, "job_uid": job_uid}), 201
    except Exception as e:
        current_app.logger.error(f"Game pipeline failure: {e}")
        return jsonify({"error": "Failed to track game"}), 500


# --- RIMWORLD SERVER INTEGRATION ---
@api_bp.route('/server_status', methods=['GET'])
def get_server_status():
    """RimWorld HTMX Endpoint - Reads from RWTData or mocks output"""
    import os
    
    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'RWTData'))
    players_active = random.randint(3, 15)  # Mock data if RWTData is missing
    server_status = "Online"
    ping = random.randint(22, 54)
    
    # In a real environment, we would parse `RWTData/server_status.json` here.
    
    # We return raw HTML exclusively designed for HTMX
    html = f"""
    <p>Server: <strong><span style="color: var(--pico-ins-color);"> {server_status} </span></strong></p>
    <p>Active Colonists (Players): <strong> {players_active} / 64</strong></p>
    <p>Current Server Ping: <em> {ping} ms</em></p>
    <progress value="{players_active}" max="64"></progress>
    <small>Hosted securely behind local ISP CGNAT via Playit.gg</small>
    """
    
    return html

# --- ACCOUNT CRUD (HTMX NATIVE PORTALS) ---
from app.routes.auth_routes import login_required
from flask import session

@api_bp.route('/cv/<int:cv_id>', methods=['DELETE'])
@login_required
def delete_cv_htmx(cv_id):
    success = CVRepository.delete_cv(cv_id, session['user_id'], is_admin=session.get('is_admin'))
    if success: return "" 
    return "Error deleting CV. Unauthorized.", 403

@api_bp.route('/cv/<int:cv_id>/edit', methods=['GET'])
@login_required
def get_cv_edit_form(cv_id):
    cv = CVRepository.get_cv_by_id(cv_id)
    if not cv or (cv['user_id'] != session['user_id'] and not session.get('is_admin')):
        return "Unauthorized", 403
    return f"""
    <form hx-put="/api/cv/{cv_id}" hx-target="closest article" hx-swap="outerHTML">
        <label>Title
            <input type="text" name="title" value="{cv['title']}" required>
        </label>
        <label>Summary
            <textarea name="summary" required>{cv['summary']}</textarea>
        </label>
        <div class="grid">
            <button type="submit">Save Changes</button>
            <button type="button" class="secondary" onclick="window.location.reload()">Cancel</button>
        </div>
    </form>
    """

@api_bp.route('/cv/<int:cv_id>', methods=['PUT'])
@login_required
def update_cv_htmx(cv_id):
    title = request.form.get('title')
    summary = request.form.get('summary')
    success = CVRepository.update_cv(cv_id, session['user_id'], title, summary, is_admin=session.get('is_admin'))
    if success:
        return f"""
        <article>
            <header>
                <strong>{title}</strong>
                <a href="#" hx-get="/api/cv/{cv_id}/edit" hx-target="closest article" hx-swap="outerHTML" style="float:right;">Edit</a>
                <a href="#" hx-delete="/api/cv/{cv_id}" hx-target="closest article" hx-swap="outerHTML" style="float:right; margin-right: 1rem; color: var(--pico-del-color);">Delete</a>
            </header>
            <p>{summary}</p>
        </article>
        """
    return "Update failed", 400

@api_bp.route('/jam/<int:game_id>', methods=['DELETE'])
@login_required
def delete_game_htmx(game_id):
    success = GameRepository.delete_game(game_id, session['user_id'], is_admin=session.get('is_admin'))
    if success: return ""
    return "Unauthorized", 403

# --- SOCIAL FEATURES: LIKES & COMMENTS ---

@api_bp.route('/games/<int:game_id>/like', methods=['POST'])
@login_required
def toggle_game_like(game_id):
    """Toggles a like for the current user and returns the new count as an HTMX snippet."""
    from app.database import get_db_connection
    uid = session['user_id']
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Check if already liked
        cursor.execute("SELECT id FROM Game_Likes WHERE user_id = ? AND game_id = ?", (uid, game_id))
        existing = cursor.fetchone()
        
        if existing:
            cursor.execute("DELETE FROM Game_Likes WHERE id = ?", (existing['id'],))
        else:
            try:
                cursor.execute("INSERT INTO Game_Likes (user_id, game_id) VALUES (?, ?)", (uid, game_id))
            except:
                # Unique constraint fail - shouldn't happen with the select check but safe and RAM friendly
                pass
        conn.commit()
        
        # Get new count
        cursor.execute("SELECT COUNT(*) as cnt FROM Game_Likes WHERE game_id = ?", (game_id,))
        count = cursor.fetchone()['cnt']
        
        # Determine if current user likes it now
        cursor.execute("SELECT 1 FROM Game_Likes WHERE user_id = ? AND game_id = ?", (uid, game_id))
        is_liked = cursor.fetchone() is not None
        
        # Return mini HTMX snippet for the button
        btn_class = "secondary" if is_liked else "outline"
        return f'<button hx-post="/api/games/{game_id}/like" hx-swap="outerHTML" class="{btn_class}">❤️ {count}</button>'
    finally:
        conn.close()

@api_bp.route('/games/<int:game_id>/comments', methods=['POST'])
@login_required
def post_game_comment(game_id):
    """Saves a comment and returns the new comment list snippet for HTMX."""
    from app.database import get_db_connection
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
    from app.database import get_db_connection
    uid = session['user_id']
    is_admin = session.get('is_admin', False)
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        if not is_admin:
            cursor.execute("SELECT user_id FROM Game_Comments WHERE id = ?", (comment_id,))
            comment = cursor.fetchone()
            if not comment or comment['user_id'] != uid:
                return "Unauthorized", 403
                
        cursor.execute("DELETE FROM Game_Comments WHERE id = ?", (comment_id,))
        conn.commit()
        return "" # HTMX removes the closest article
    finally:
        conn.close()

# --- CHAT ROOMS ---
@api_bp.route('/chat/messages', methods=['GET'])
def get_chat_messages():
    """Returns HTML for HTMX polling of chat messages."""
    from app.database import get_db_connection
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT c.*, u.username, u.is_admin 
            FROM Chat_Messages c 
            JOIN Users u ON c.user_id = u.id 
            ORDER BY c.created_at DESC LIMIT 50
        ''')
        messages = [dict(row) for row in cursor.fetchall()]
        
        if not messages:
            return "<p class='text-center' style='color: grey;'><small>No messages yet. Be the first to say hi!</small></p>"
            
        html = ""
        current_user_id = session.get('user_id')
        is_admin = session.get('is_admin', False)
        
        for msg in messages:
            can_delete = is_admin or msg['user_id'] == current_user_id
            name_color = "var(--pico-primary)" if msg['is_admin'] else "var(--pico-color)"
            badge = "&#x1F468;&#x200D;&#x1F4BB; " if msg['is_admin'] else ""
            
            html += f"""
            <article style=\"padding: 0.5rem 1rem; margin-bottom: 0; background: rgba(0,0,0,0.2); border: 1px solid rgba(255,255,255,0.05); border-radius: 8px;\">
                <div style=\"display: flex; justify-content: space-between; align-items: baseline;\">
                    <div>
                        <strong style=\"color: {name_color};\">{badge}@{msg['username']}</strong>
                        <span style=\"margin-left: 0.5rem; word-break: break-word;\">{msg['content']}</span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 0.5rem; flex-shrink: 0; margin-left: 1rem;">
                        <small style="color: grey; font-size: 0.7rem;"><time datetime="{msg['created_at']}Z" class="chat-time">{msg['created_at'].split(' ')[1][:5]}</time></small>
            """
            
            if can_delete:
                html += f"""
                        <a href=\"#\" hx-delete=\"/api/chat/messages/{msg['id']}\" hx-target=\"closest article\" hx-swap=\"outerHTML\" style=\"color: var(--pico-del-color); cursor: pointer; text-decoration: none; font-weight: bold;\" title=\"Delete Message\">&#x2A2F;</a>
                """
                
            html += """
                    </div>
                </div>
            </article>
            """
        from flask import make_response
        resp = make_response(html)
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        resp.headers['Pragma'] = 'no-cache'
        resp.headers['Expires'] = '0'
        return resp
    finally:
        conn.close()

@api_bp.route('/chat/messages', methods=['POST'])
@login_required
def post_chat_message():
    """Posts a new chat message and returns the updated chat list."""
    from app.database import get_db_connection
    from markupsafe import escape
    uid = session['user_id']
    content = request.form.get('content', '').strip()
    
    if not content:
        return "Message cannot be empty", 400
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO Chat_Messages (user_id, content) VALUES (?, ?)", (uid, escape(content)))
        conn.commit()
    finally:
        conn.close()
        
    return get_chat_messages()

@api_bp.route('/chat/messages/<int:msg_id>', methods=['DELETE'])
@login_required
def delete_chat_message(msg_id):
    """Deletes a chat message if the user is the author or an admin."""
    from app.database import get_db_connection
    uid = session['user_id']
    is_admin = session.get('is_admin', False)
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        if not is_admin:
            cursor.execute("SELECT user_id FROM Chat_Messages WHERE id = ?", (msg_id,))
            msg = cursor.fetchone()
            if not msg or msg['user_id'] != uid:
                return "Unauthorized", 403
                
        cursor.execute("DELETE FROM Chat_Messages WHERE id = ?", (msg_id,))
        conn.commit()
        return "" # HTMX removes the element
    finally:
        conn.close()
