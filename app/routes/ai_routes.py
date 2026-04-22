import html
import re
from flask import Blueprint, request, g
from app.services import ai_service
from app.i18n import t

ai_bp = Blueprint('ai', __name__, url_prefix='/ai')

def format_ai_message(text):
    """
    Renders basic markdown (bold, italic, lists, headers) to HTML.
    Keeps it simple to stay under the 20KB JS/CSS payload limit.
    """
    import html
    # 1. Escape HTML for security
    text = html.escape(text)

    # 2. Simple Markdown Regex-like rules (Server-side)
    # Headers
    text = re.sub(r'(?m)^### (.*)$', r'<h3>\1</h3>', text)
    text = re.sub(r'(?m)^## (.*)$', r'<h2>\1</h2>', text)
    text = re.sub(r'(?m)^# (.*)$', r'<h1>\1</h1>', text)
    
    # Bold
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__(.*?)__', r'<strong>\1</strong>', text)
    
    # Italic
    text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
    text = re.sub(r'_(.*?)_', r'<em>\1</em>', text)
    
    # Unordered Lists
    text = re.sub(r'(?m)^- (.*)$', r'<li>\1</li>', text)
    text = re.sub(r'(?m)^\* (.*)$', r'<li>\1</li>', text)
    # Links: [text](url) -> <a href="url">text</a>
    # Safeguard: Filter out links with placeholders like {id} or ? or curly braces
    def link_replacer(match):
        label, url = match.groups()
        if '?' in url and 'room_id=' not in url: # Allow chat room queries but block things like /games/?
            if url.endswith('?'): return label
        if '{' in url or '}' in url or 'ID' in url: # Block literals like /games/ID or {id}
            return label
        return f'<a href="{url}" class="accent-link">{label}</a>'

    text = re.sub(r'\[(.*?)\]\((.*?)\)', link_replacer, text)

    # Wrap consecutive list items in <ul>
    text = re.sub(r'(<li>.*</li>(?:[\s\S]*?<li>.*</li>)*)', r'<ul>\1</ul>', text)

    return text

@ai_bp.route('/ask', methods=['POST'])
def ask_ai():
    prompt = request.form.get('prompt')
    if not prompt:
        return f"<strong>{t('Error:')}</strong> {t('Please provide a prompt.')}", 400

    # Use cookie-based visitor ID to survive NAT/CGNAT
    user_id = getattr(g, 'visitor_id', request.remote_addr)
    task_id, is_busy = ai_service.submit_prompt(user_id, prompt)
    
    if not task_id:
        return f'''
        <div id="chat-result">
            <article style="border-color: var(--pico-del-color);">
                <header style="color: var(--pico-del-color);">🛑 {t("Request Blocked")}</header>
                <p>{t("You already have an active AI request in progress. Please wait for the previous one to finish before sending another.")}</p>
            </article>
        </div>
        '''

    # If the engine is completely cold, give immediate feedback
    if not ai_service.is_ai_ready():
        status_msg = t("AI is waking up (Warm-up phase)...")
    else:
        status_msg = t("Adding to queue...") if is_busy else t("Initializing AI...")

    return f'''
    <div id="chat-result" hx-get="/ai/status/{task_id}" hx-trigger="every 1.5s" hx-swap="outerHTML">
        <article class="thinking">
            <header><strong aria-busy="true">{t("AI Assistant")}</strong></header>
            {status_msg} ({t("Task")} {task_id[:8]})
        </article>
    </div>
    '''

@ai_bp.route('/status/<task_id>', methods=['GET'])
def ai_status(task_id):
    result = ai_service.get_result(task_id)
    status = result.get('status')
    
    if status == 'done':
        formatted_answer = format_ai_message(result.get('answer', ''))
        return f'''
        <div id="chat-result" style="animation: slideIn 0.4s ease-out;">
            <style>
                .accent-link {{
                    color: var(--pico-primary);
                    font-weight: bold;
                    text-decoration: underline;
                    transition: opacity 0.2s;
                }}
                .accent-link:hover {{
                    opacity: 0.8;
                    text-decoration: none;
                }}
            </style>
            <article>
                <header><strong>{t("AI Assistant")}</strong></header>
                <div style="white-space: pre-wrap;">{formatted_answer}</div>
            </article>
        </div>
        '''
    elif status == 'generating':
        # Use a faster poll during generation for the "typing" effect
        # We also keep the article stable (no pulse) so text is easy to read
        formatted_answer = format_ai_message(result.get('answer', ''))
        return f'''
        <div id="chat-result" hx-get="/ai/status/{task_id}" hx-trigger="every 0.5s" hx-swap="outerHTML">
            <article style="border-color: var(--pico-primary); box-shadow: 0 0 15px rgba(168, 85, 247, 0.1);">
                <header><strong aria-busy="true">{t("AI is typing...")}</strong></header>
                <div style="white-space: pre-wrap;">{formatted_answer}</div>
            </article>
        </div>
        '''
    elif status == 'waking_up':
        return f'''
        <div id="chat-result" hx-get="/ai/status/{task_id}" hx-trigger="every 2s" hx-swap="outerHTML">
            <article class="thinking" style="border-style: solid;">
                <header><strong aria-busy="true">{t("AI Engine")}</strong></header>
                <div style="text-align: center; padding: 1rem;">
                    <span style="font-size: 2rem;">⚡</span>
                    <p><strong>{t("Waking up from idle...")}</strong></p>
                    <p><small>{t("The model is loading into system RAM. This may take 30-60 seconds.")}</small></p>
                </div>
            </article>
        </div>
        '''
    elif status == 'error':
        safe_error = html.escape(result.get('message', 'Unknown error occurred.'))
        return f'''
        <div id="chat-result">
            <article style="border-color: var(--pico-del-color);">
                <header style="color: var(--pico-del-color);"><strong>{t("Error Processing Request")}</strong></header>
                <p>{safe_error}</p>
                <footer>
                    <button class="outline" onclick="window.location.reload()">{t("Try Again")}</button>
                </footer>
            </article>
        </div>
        '''
    else:
        pos = result.get('queue_pos', 1)
        msg = t("AI is thinking...") if pos == 1 else f"{t('In Queue')}: {t('You are')} #{pos} {t('in line')}..."
        return f'''
        <div id="chat-result" hx-get="/ai/status/{task_id}" hx-trigger="every 1.5s" hx-swap="outerHTML">
            <article class="thinking">
                <header><strong aria-busy="true">{t("AI Assistant")}</strong></header>
                <p style="text-align: center; padding: 1rem; color: var(--pico-primary);">
                    {msg}
                </p>
            </article>
        </div>
        '''