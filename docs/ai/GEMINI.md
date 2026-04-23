# Project: proglem (Scalable Micro-Platform)

## 🚨 STRICT HARDWARE CONSTRAINTS 🚨
- **RAM:** 8GB Maximum. 
- **Network:** 22 Mbps Upload Limit, behind strict CGNAT.
- **Rule:** NEVER suggest or install bloated frameworks (React, Angular, etc.), heavy ORMs (like SQLAlchemy), or traditional database servers (PostgreSQL/MySQL). 

## 🛠️ Tech Stack
- **Backend:** Python 3.11+, Flask, Gunicorn.
- **Database:** SQLite3 (MUST enforce `PRAGMA journal_mode=WAL` and `PRAGMA synchronous=NORMAL`). Use JSON1 extension for dynamic data.
- **Frontend:** HTMX + Pico.css (Classless via CDN). Zero-build process. Keep JS/CSS payloads under 20KB.
- **Networking:** Nginx Reverse Proxy, `cloudflared` (HTTPS tunneling), `playit.gg` (TCP/UDP tunneling).
- **Cloud/Uploads:** AWS S3 / Cloudflare R2 (via `boto3`).
- **AI:** `llama-cpp-python` (Local 1.2B LLM).

## 🧠 Core Architectural Rules
1. **The Bandwidth Rule:** NEVER handle large file uploads (like .zip Game Jam submissions) on the local server. Always generate a Pre-signed POST URL (S3/R2) via Flask and force the client browser to upload directly to the cloud.
2. **The RAM Rule:** The local LLM must be strictly wrapped in `asyncio.Semaphore(1)` or a background queue. Only ONE AI request processes at a time. Other concurrent requests must immediately receive an HTTP 202 "Thinking" response.
3. **The Frontend Rule:** Do not write custom CSS unless absolutely necessary. Rely purely on Pico.css HTML tags. Use HTMX for dynamic polling and DOM swapping without page reloads.

## ⚙️ DevOps & CI/CD
- Use GitHub Actions for all workflows.
- Testing: `pytest` (unit) and `bandit` (security/SQLi).
- **Git Flow:** NEVER push directly to `main`. Always create a new `feature/` branch from `dev`, and submit a Pull Request to merge back into `dev`.