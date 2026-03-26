import pytest
from app import app
import database

@pytest.fixture
def client():
    """Sets up a test client for the Flask application."""
    app.config['TESTING'] = True
    
    with app.test_client() as client:
        # Initialize the database context for testing
        with app.app_context():
            database.init_db()
        yield client

def test_homepage_loads(client):
    """Verifies that the main HTML page serves correctly."""
    response = client.get('/')
    assert response.status_code == 200
    # Check if the Pico.css/HTMX template is actually rendering
    assert b"proglem" in response.data

def test_server_status_endpoint(client):
    """Verifies the HTMX endpoint returns the expected HTML snippet."""
    response = client.get('/api/server_status')
    assert response.status_code == 200
    assert b"RimWorld Server" in response.data

def test_cv_catalog_api(client):
    """Verifies the JSON API for Godot/WebGL clients returns a list."""
    response = client.get('/api/cv')
    assert response.status_code == 200
    # Even if the database is empty, it should return an empty JSON array []
    assert isinstance(response.json, list)