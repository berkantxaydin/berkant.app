import html
import re
from flask import Blueprint, request
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
    # Wrap consecutive list items in <ul>
    text = re.sub(r'(<li>.*</li>(?:[\s\S]*?<li>.*</li>)*)', r'<ul>\1</ul>', text)

    return text

@ai_bp.route('/ask', methods=['POST'])
def ask_ai():
    prompt = request.form.get('prompt')
    if not prompt:
        return f"<strong>{t('Error:')}</strong> {t('Please provide a prompt.')}", 400

    # Pass the remote IP as user identifier
    user_id = request.remote_addr
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
        <div id="chat-result">
            <article>
                <header><strong>{t("AI Answer")}</strong></header>
                <div style="white-space: pre-wrap;">{formatted_answer}</div>
            </article>
        </div>
        '''
    elif status == 'generating':
        # Use a faster poll during generation
        formatted_answer = format_ai_message(result.get('answer', ''))
        return f'''
        <div id="chat-result" hx-get="/ai/status/{task_id}" hx-trigger="every 0.5s" hx-swap="outerHTML">
            <article>
                <header><strong aria-busy="true">{t("AI is typing...")}</strong></header>
                <div style="white-space: pre-wrap;">{formatted_answer}</div>
            </article>
        </div>
        '''
    elif status == 'waking_up':
        return f'''
        <div id="chat-result" hx-get="/ai/status/{task_id}" hx-trigger="every 2s" hx-swap="outerHTML">
            <article class="thinking" style="border-color: var(--pico-primary);">
                <header><strong aria-busy="true">{t("AI Engine")}</strong></header>
                ⚡ {t("Waking up from idle...")}
                <p><small>{t("The model is loading into system RAM. This may take 30-60 seconds.")}</small></p>
            </article>
        </div>
        '''
    elif status == 'error':
        safe_error = html.escape(result.get('message', 'Unknown error occurred.'))
        return f'''
        <div id="chat-result">
            <article>
                <header style="color: var(--pico-del-color);"><strong>{t("Error Processing Request")}</strong></header>
                <p>{safe_error}</p>
            </article>
        </div>
        '''
    else:
        pos = result.get('queue_pos', 1)
        msg = t("AI is processing your request...") if pos == 1 else f"{t('In Queue')}: {t('You are')} #{pos} {t('in line')}..."
        return f'''
        <div id="chat-result" hx-get="/ai/status/{task_id}" hx-trigger="every 1.5s" hx-swap="outerHTML">
            <article class="thinking">
                <header><strong aria-busy="true">{t("AI Assistant")}</strong></header>
                {msg}
            </article>
        </div>
        '''