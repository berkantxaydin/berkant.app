import pytest
import json
from app import create_app

@pytest.fixture
def client():
    # Use the same 'Shift-Left' logic as other unit tests
    app = create_app()
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test_key'
    
    with app.test_client() as client:
        yield client

def test_get_upload_url_logic(client):
    """
    Verifies that the pre-signed URL generator issues the correct mock/S3 fields.
    This test runs in the 'Shift-Left' CI environment without needing a live server.
    """
    url = '/api/jam/get_upload_url?filename=test/index.html&content_type=text/html'
    resp = client.get(url)
    
    assert resp.status_code == 200
    data = json.loads(resp.data)
    
    assert 'url' in data
    assert 'fields' in data
    assert 'key' in data['fields']

def test_mock_upload_logic(client):
    """
    Verifies the mock upload endpoint logic used for local development.
    """
    # Simulate the multipart/form-data upload expected by our JS client
    form_data = {
        'key': 'test/index.html',
        'content-type': 'text/html',
        'file': (b'<h1>Hello Game</h1>', 'index.html')
    }
    
    resp = client.post('/api/jam/mock_upload', data=form_data, content_type='multipart/form-data')
    
    # Mock upload usually returns 200/204 on success depending on AWS imitation
    assert resp.status_code in [200, 204]
