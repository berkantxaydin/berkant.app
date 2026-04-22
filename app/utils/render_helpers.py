from flask import render_template, make_response
from app.i18n import t

def render_cv_cards(cvs):
    """Renders a list of CV cards as an HTML string."""
    return "".join([render_template('partials/cv_card.html', cv=cv) for cv in cvs])

def render_chat_messages(messages, current_user_id=None, is_admin=False):
    """Renders a list of chat messages. Returns an empty state if no messages."""
    if not messages:
        return render_empty_state(t("No messages yet. Start the conversation!"))
    
    html = "".join([
        render_template('partials/chat_message.html', 
                       msg=m, 
                       current_user_id=current_user_id, 
                       is_admin=is_admin) 
        for m in messages
    ])
    return html

def render_alert(message, type='error'):
    """Renders a standardized alert message."""
    return render_template('partials/alert.html', message=message, type=type)

def render_empty_state(message=None):
    """Renders a standardized empty state message."""
    return render_template('partials/empty_state.html', message=message)

def render_empty_response():
    """Returns an empty response, typically for HTMX deletions."""
    return ""
