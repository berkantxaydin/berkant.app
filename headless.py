# Headless Waitress OS Wrapper
# Driven purely independent of any Thin-Client window constraints!

from app import create_app
from waitress import serve
import logging

if __name__ == '__main__':
    logging.getLogger('waitress').setLevel(logging.ERROR)
    print("[Headless] Booting pure background WSGI...")
    server = create_app()
    serve(server, host='127.0.0.1', port=5000)
