import pytest
import requests
import json
import time
import socket

# SHIFT-RIGHT: Test the application AFTER its deployment in the runtime environment.
# We bypass Flask completely and hit `localhost:5000` via standard network sockets (HTTP).
# This validates Waitress, Nginx Proxy layers, and OS App Hook integrations synchronously.

BASE_URL = "http://127.0.0.1:5000"

def is_server_running():
    """Probes the live server port actively to ensure Waitress hasn't crashed in production."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', 5000)) == 0

@pytest.mark.skipif(not is_server_running(), reason="Shift-Right tests require the server to be actively deployed.")
def test_production_landing_api():
    """Hits the live production endpoint verifying the Waitress routing."""
    response = requests.get(f"{BASE_URL}/")
    assert response.status_code == 200
    assert "proglem" in response.text

@pytest.mark.skipif(not is_server_running(), reason="Server not deployed.")
def test_production_rimworld_polling():
    """Hits the explicit /api/server_status JSON endpoint from the active deployment layer."""
    response = requests.get(f"{BASE_URL}/api/server_status")
    assert response.status_code == 200
    
    data = response.json()
    assert "server_status" in data
    assert "players_active" in data
    assert data["server_status"] == "Online"

@pytest.mark.skipif(not is_server_running(), reason="Server not deployed.")
def test_production_secure_s3_url_generator():
    """Verifies that the live Nginx/Waitress deployment natively issues AWS payload URLs."""
    response = requests.get(f"{BASE_URL}/api/jam/get-upload-url?filename=shiftright.zip")
    assert response.status_code == 200
    data = response.json()
    assert "url" in data
    assert "fields" in data
