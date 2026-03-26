@echo off
echo 🚀 Starting proglem on Windows...

IF NOT EXIST venv (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate
echo Installing dependencies...
pip install -r requirements.txt

echo Starting server on port 8000...
waitress-serve --port=8000 app:app