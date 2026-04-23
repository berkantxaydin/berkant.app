import requests
from flask import current_app, request

def verify_turnstile(token: str) -> bool:
    """Verifies a Cloudflare Turnstile token with the Cloudflare API."""
    secret_key = current_app.config.get('TURNSTILE_SECRET_KEY')
    
    # If no secret key is configured, assume verification is disabled/passed
    if not secret_key:
        return True
        
    if not token:
        return False
        
    try:
        response = requests.post(
            'https://challenges.cloudflare.com/turnstile/v0/siteverify',
            data={
                'secret': secret_key,
                'response': token,
                'remoteip': request.remote_addr
            },
            timeout=10
        )
        result = response.json()
        return result.get('success', False)
    except Exception as e:
        current_app.logger.error(f"Turnstile verification error: {e}")
        return False
