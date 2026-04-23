@echo off
cd /d "%~dp0.."
echo Starting proglem on Windows...

IF NOT EXIST venv (
    echo Creating virtual environment...
    python -m venv venv
)

echo Using environment at venv\Scripts...

echo Installing dependencies...
venv\Scripts\python.exe -m pip install -r requirements.txt

echo Starting server on port 5000...
start "proglem-worker" venv\Scripts\python.exe bin/worker.py
venv\Scripts\waitress-serve.exe --port=5000 --call app:create_app