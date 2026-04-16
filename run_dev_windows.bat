@echo off
echo Starting proglem on Windows...

IF NOT EXIST venv (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate
echo Installing dependencies...
pip install -r requirements.txt

echo Starting server on port 5000...
waitress-serve --port=5000 --call app:create_app