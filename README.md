# 🚀 proglem — Scalable Micro-Platform

A resource-efficient, full-featured developer community platform built to run on **constrained hardware** (8GB RAM, 22 Mbps upload, CGNAT ISP). It hosts developer CV portfolios, runs Game Jam events with Godot WebGL submissions, and powers a community chat — all on a single home server.

> **Live platform:** [berkant.app](https://berkant.app)

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🧑‍💼 **CV Pool** | Developers publish structured CV cards. Filterable talent pool, with optional raw HTMX resume injection. |
| 🎮 **Gaming Hub** | Godot WebGL game library with likes, comments, and live in-browser play. |
| 🏆 **Game Jam** | Host timed events. Players upload ZIP exports; the browser extracts and streams files directly to Cloudflare R2. Server bandwidth is never touched. |
| 💬 **Community Hub** | Multi-room real-time chat with HTMX polling. Rooms can be tied to Game Jams. |
| 🤖 **Local AI Assistant** | Powered by a local **Gemma 4** model via `llama-server`. Context-aware: knows top games, active jams, CVs, and live CPU/RAM stats. |
| 🌍 **Full i18n (EN/TR)** | Every UI string — templates, HTMX fragments, error messages — is wrapped in `t()`. A Gemma-powered admin job auto-translates missing keys in batches. |
| 📊 **Metrics Dashboard** | Real-time CPU, RAM, AI memory usage bars, request analytics, and error log viewer. |
| 🔐 **IAM** | Session-based auth with admin roles, login-required routes, and activation code registration. |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.11+, Flask, Waitress (Windows) / Gunicorn (Linux) |
| **Database** | SQLite3 with `PRAGMA journal_mode=WAL` + `PRAGMA synchronous=NORMAL` + JSON1 extension |
| **Frontend** | HTMX 1.9 + Pico.css (classless, CDN-free local copy) — zero build step, <20KB payload |
| **AI Engine** | `llama-server` (llama.cpp binary) running Gemma 4 locally; queue-protected with a single-slot semaphore |
| **AI Translation** | Same Gemma 4 model auto-translates missing UI strings in batches of 15 via the Admin panel |
| **Uploads** | AWS S3 / Cloudflare R2 via `boto3` pre-signed POST — browser uploads directly, server never handles file bytes |
| **Networking** | Nginx reverse proxy, `cloudflared` (HTTPS tunnel), `playit.gg` (TCP/UDP tunnel) |
| **CI/CD** | GitHub Actions: `flake8`, `pytest`, `bandit` + Gemini AI automated PR review |
| **Containers** | Docker + GitHub Container Registry (`ghcr.io`) |

---

## 🧠 Engineering Solutions to Hardware Constraints

### 1. RAM Bottleneck (8GB)
Running Flask + Gemma 4 (~5GB VRAM) simultaneously risks OOM crashes.
- **Solution:** The AI worker thread is guarded by a `queue.Queue` + single-slot processing. Concurrent users receive an HTTP "queued" response with HTMX polling — only one inference runs at a time.

### 2. Upload Bandwidth (22 Mbps)
Hosting 500MB Game Jam ZIP files locally would choke the network.
- **Solution:** Flask generates a **Cloudflare R2 pre-signed POST URL**. The user's browser extracts the ZIP via `JSZip` in-memory and streams each file directly to R2. The server handles zero bytes of file data.

### 3. ISP CGNAT (No Port Forwarding)
The ISP blocks all inbound connections.
- **Solution:** `cloudflared` maintains an outbound tunnel for HTTPS web traffic. `playit.gg` handles TCP/UDP game tunnels. Both work without any router configuration.

---

## 🐳 Docker Deployment (Quick Start)

Releases are published to the **GitHub Container Registry**. You only need `docker-compose.yml` and your own Gemma model file.

### 1. Download the compose file
```bash
curl -L https://github.com/berkantxaydin/berkant.app/releases/latest/download/docker-compose.yml -o docker-compose.yml
```

### 2. Prepare directories
```bash
mkdir -p models data
```

### 3. Download the AI model
Get `gemma-4-E4B-it-Q4_K_M.gguf` from Hugging Face and place it in `./models/`:
```bash
# Example using huggingface-cli:
huggingface-cli download google/gemma-4-GGUF gemma-4-E4B-it-Q4_K_M.gguf --local-dir ./models
```
> The model is ~3-5GB and is **not** bundled in the Docker image.

### 4. Configure environment
```bash
cp .env.example .env
# Edit .env with your SECRET_KEY and optional R2 credentials
```

### 5. Run
```bash
docker compose up
```
The platform will be available at `http://localhost:5000`. On first boot, the database schema is created automatically and a default `💬 General` chat room is seeded.

---

## ⚙️ Local Development (Windows)

```powershell
git clone https://github.com/berkantxaydin/berkant.app
cd berkant.app
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
# Place your .gguf model in ./models/
.\scripts\run_dev_windows.bat
```

### Linux / macOS
```bash
chmod +x scripts/run_dev_linux.sh
./scripts/run_dev_linux.sh
```

### Environment variables (`.env`)
```env
SECRET_KEY=your-super-secret-key
R2_ENDPOINT_URL=https://your-account.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=your-key
R2_SECRET_ACCESS_KEY=your-secret
R2_BUCKET_NAME=jam-uploads
GEMINI_API_KEY=your-gemini-key     # For automated PR reviews only
```

---

## 🌍 Localization (EN/TR)

The platform is fully bilingual. All strings are wrapped in `{{ t("...") }}` (Jinja2 templates) or `t("...")` (Python fragments).

**How translation works:**
1. Any new string is auto-registered into `translations.json` on first render.
2. An Admin goes to the **Admin Panel → "Scan & Translate Missing UI"**.
3. The local **Gemma 4 model** translates all missing keys in batches of 15, saving incrementally to avoid timeouts.
4. Users toggle the 🇹🇷 flag in the navbar to switch languages (persisted in session).

---

## 🧪 Testing & CI/CD

Every push and Pull Request triggers:

| Check | Tool |
|-------|------|
| Syntax / linting | `flake8` |
| Unit tests | `pytest` |
| Security scan | `bandit` (SQL injection, subprocess safety) |
| AI Code Review | Gemini API — posts a review comment directly on the PR |

**Git flow:** Never push to `main` directly. All changes go through a `feature/` branch → PR to `dev` → PR to `main`.

---

## 📦 Releases

Docker images are published automatically when a version tag is pushed:

```bash
git tag v1.0.0
git push origin v1.0.0
```

GitHub Actions will:
1. Run the full CI test suite
2. Build the Docker image
3. Push to `ghcr.io/berkantxaydin/berkant.app:latest` and `:v1.0.0`
4. Create a GitHub Release with `docker-compose.yml` attached as a download

---

## 📄 License

[Creative Commons Zero v1.0 Universal (CC0 1.0)](LICENSE) — public domain. Use freely for any purpose.
