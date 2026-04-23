from app import create_app
from flask import session

app = create_app()
with app.app_context():
    with app.test_request_context():
        rooms = [{'id': 1, 'name': 'General', 'is_enabled': 1}, {'id': 2, 'name': 'public', 'is_enabled': 1}]
        rendered = app.jinja_env.get_template('chat.html').render(rooms=rooms, t=lambda x: x, session={})
        print(rendered)
