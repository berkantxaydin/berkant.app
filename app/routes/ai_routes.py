from flask import Blueprint, request
from app.services import ai_service

ai_bp = Blueprint('ai', __name__, url_prefix='/ai')

@ai_bp.route('/ask', methods=['POST'])
def ask_ai():
    """
    Called by HTMX when the user submits a form.
    Returns a snippet of HTML that automatically polls /ai/status.
    """
    prompt = request.form.get('prompt')
    if not prompt:
        return "<strong>Error:</strong> Please provide a prompt.", 400

    # Submit to background queue targeting the single local core
    task_id, _ = ai_service.submit_prompt(prompt)

    # Return an HTMX polling element immediately
    return f'''
    <div id="chat-result" hx-get="/ai/status/{task_id}" hx-trigger="every 2s" hx-swap="outerHTML">
        <article class="thinking" aria-busy="true">
            AI is thinking in the background... (Task {task_id[:8]})
        </article>
    </div>
    '''

@ai_bp.route('/status/<task_id>', methods=['GET'])
def ai_status(task_id):
    """
    Polled smoothly by HTMX. Once the queue task finishes,
    HTMX replaces the polling loop with the final UI answer block.
    """
    result = ai_service.get_result(task_id)
    status = result.get('status')
    
    if status == 'done':
        # Final answer box
        return f'''
        <div id="chat-result">
            <article>
                <header><strong>AI Answer:</strong></header>
                <p style="white-space: pre-wrap;">{result.get('answer')}</p>
            </article>
        </div>
        '''
    elif status == 'error':
        return f'''
        <div id="chat-result">
            <article>
                <header style="color: var(--pico-del-color);"><strong>Error Processing Request</strong></header>
                <p>{result.get('message', 'Unknown error occurred in local llm queue.')}</p>
            </article>
        </div>
        '''
    else:
        # Still thinking / pending in queue
        return f'''
        <div id="chat-result" hx-get="/ai/status/{task_id}" hx-trigger="every 2s" hx-swap="outerHTML">
            <article class="thinking" aria-busy="true">
                AI is thinking in the background... (Queue processing)
            </article>
        </div>
        '''
