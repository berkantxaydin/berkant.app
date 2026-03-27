from app import create_app

app = create_app()

if __name__ == '__main__':
    # Running strictly on 127.0.0.1 for an NGINX reverse-proxy setup
    app.run(host='127.0.0.1', port=5000, debug=True)
