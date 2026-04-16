import html
import re
from flask import Blueprint, request
from app.services import ai_service
from app.i18n import t

ai_bp = Blueprint('ai', __name__, url_prefix='/ai')

def format_ai_message(text):
    """
    Escapes HTML for security and ensures basic paragraph formatting.
    No more <think> tags or dropdowns are needed for Gemma 4.
    """
    return html.escape(text)

@ai_bp.route('/ask', methods=['POST'])
def ask_ai():
    # Check if the AI model is ready
    if not ai_service.is_ai_ready():
        return f'''
        <div id="chat-result" hx-post="/ai/ask" hx-trigger="every 5s" hx-include="[name='prompt']" hx-swap="outerHTML">
            <article class="thinking" aria-busy="true" style="border-color: var(--pico-primary);">
                <header><strong>{t("AI Assistant")}</strong></header>
                ⚡ {t("AI is warming up (loading 5GB Gemma model)...")}
                <p><small>{t("The site is ready, but the AI engine is still loading into VRAM. Please wait.")}</small></p>
            </article>
        </div>
        '''

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

    status_msg = t("Adding to queue...") if is_busy else t("Initializing AI...")

    return f'''
    <div id="chat-result" hx-get="/ai/status/{task_id}" hx-trigger="every 1.5s" hx-swap="outerHTML">
        <article class="thinking" aria-busy="true">
            <header><strong>{t("AI Task Manager")}</strong></header>
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
            <article class="thinking" aria-busy="true">
                <header><strong>{t("AI Task Manager")}</strong></header>
                {msg}
            </article>
        </div>
        '''