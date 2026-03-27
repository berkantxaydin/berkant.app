import pytest
from app import create_app
from app import database

@pytest.fixture
def client():
    """Sets up a test client for the Flask application."""
    app = create_app()
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
    """Verifies the healthcheck endpoint."""
    response = client.get('/health')
    assert response.status_code == 200
    assert b"OK" in response.data

def test_cv_catalog_api(client):
    """Verifies the JSON API returns a structure."""
    response = client.get('/api/cv')
    assert response.status_code == 200
    # The API returns a dict: {"status": "success", "count": ..., "data": []}
    assert isinstance(response.json, dict)
    assert response.json.get("status") == "success"
    assert "data" in response.json
    assert isinstance(response.json["data"], list)