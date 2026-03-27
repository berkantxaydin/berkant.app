import pytest
from app import create_app
import sqlite3
import os

# SHIFT-LEFT: Test internal mechanics, security functions, and pure logic independently of deployment.
# We map explicitly to the Flask testing client to skip networking layers.

@pytest.fixture
def client():
    # Use a mock memory db/config for safe shift-left scoping
    app = create_app()
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test_key'
    
    with app.test_client() as client:
        yield client

def test_landing_page_loads(client):
    """Verifies that the core routing map compiles the Home UI successfully."""
    response = client.get('/')
    assert response.status_code == 200
    assert b'proglem' in response.data

def test_unauthorized_dashboard_blocks(client):
    """Verifies that IAM correctly blocks anonymous users from /account."""
    response = client.get('/account')
    # Should redirect (302) to /login
    assert response.status_code == 302
    assert b'/login' in response.data

def test_password_hashing():
    """Shift-left logic proof for IAM."""
    from werkzeug.security import generate_password_hash, check_password_hash
    pwhash = generate_password_hash("shiftleft123")
    assert check_password_hash(pwhash, "shiftleft123") is True
    assert check_password_hash(pwhash, "wrong") is False
