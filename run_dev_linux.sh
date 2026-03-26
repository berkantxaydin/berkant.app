#!/bin/bash
echo "🚀 Starting proglem on Linux..."

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate
echo "Installing dependencies..."
pip install -r requirements.txt

echo "Starting Gunicorn server on port 8000..."
gunicorn -w 4 -b 127.0.0.1:8000 app:app