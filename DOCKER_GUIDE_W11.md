# 🐳 Docker for Windows 11: Production Guide

This guide explains how to containerize the **proglem** platform on a Windows 11 machine using Docker Desktop and the WSL2 backend.

## 🛠️ Prerequisites
1. **Docker Desktop**: Install and ensure "Use the WSL 2 based engine" is checked in Settings.
2. **WSL2**: Run `wsl --install` in PowerShell if you haven't already.

---

## 📄 1. The Dockerfile
Create a file named `Dockerfile` in the root directory:

```dockerfile
# Use a lightweight Python base
FROM python:3.11-slim-bookworm

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

# Install system dependencies (needed for llama-cpp-python and health checks)
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy application code
COPY . .

# Ensure logs directory exists
RUN mkdir -p logs app/static/mock_s3/submissions

# Expose the Waitress port
EXPOSE 5000

# Start Waitress
CMD ["python", "-m", "waitress", "--port=5000", "--call", "app:create_app"]
```

---

## 🏗️ 2. The Docker Compose
Create a file named `docker-compose.yml` in the root directory:

```yaml
services:
  web:
    build: .
    container_name: proglem_app
    restart: unless-stopped
    ports:
      - "5000:5000"
    volumes:
      - ./proglem.db:/app/proglem.db
      - ./app/static/mock_s3/submissions:/app/app/static/mock_s3/submissions
      - ./logs:/app/logs
    environment:
      - FLASK_ENV=production
      - SECRET_KEY=${SECRET_KEY}

  # Nginx Reverse Proxy (Optional if using Cloudflare Tunnel directly)
  nginx:
    image: nginx:alpine
    container_name: proglem_nginx
    ports:
      - "80:80"
    volumes:
      - ./nginx-1.30.0/conf/nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - web
```

---

## 🚀 3. Running it on Windows 11

### A. Environment Setup
Create a `.env` file in the same folder as your `docker-compose.yml`. 

> [!CAUTION]
> **NEVER** use a placeholder like "your_secret_key_here" in production. A weak secret key allows attackers to hijack user sessions.
> 
> **Generate a secure key with this command:**
> `python -c "import secrets; print(secrets.token_hex(24))"`

```env
# Paste your generated hex key here
SECRET_KEY=y0ur-n3wly-g3n3r4t3d-h3x-k3y
```

### B. Launching
Open a terminal (PowerShell or Terminal) in your project folder and run:
```powershell
docker compose up -d --build
```

### C. Important Windows 11 Notes:
- **File Performance**: For maximum speed, keep your project folder inside the WSL2 file system (e.g., `\\wsl$\Ubuntu\home\user\project`) instead of a Windows folder like `C:\Users`.
- **SQLite Performance**: Always ensure the database is mounted as a volume so your data persists when the container restarts.
- **Port Conflicts**: If Port 80 is taken by Windows (IIS), change the Nginx port mapping in `docker-compose.yml` to `"8080:80"`.

---

## 🔍 4. Health Checks
Once running, you can verify the status from your Windows browser:
- **App**: `http://localhost:5000/health`
- **Nginx**: `http://localhost:80`
