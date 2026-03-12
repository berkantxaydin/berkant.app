# 🚀 Scalable Micro-Platform

A highly optimized, resource-efficient web platform and API backend built to run on constrained hardware. This project hosts developer portfolios(users will be able to togle if they looking for job), manages Game Jam events or similar for sofware devs, serves as a backend for Godot WebGL games, and acts as a bridge to a live C# multiplayer game server (RimWorld Together).

Designed from the ground up to operate on an 8GB RAM headless Debian server, behind a strict ISP CGNAT, with a 22 Mbps upload limit.

---

## ✨ Core Features
* **CV Catalog & Game Jam Dashboard:** Ultra-lightweight web UI for users to view portfolios and register for events.
* **Godot Game API:** Fast, secure JSON endpoints for Godot WebGL clients to read/write game data.
* **Multiplayer Server Bridge:** Secure reading and writing to a local RimWorld Together C# server configuration to display live server stats.
* **Local AI Integration:** A local LFM 2.5-Thinking 1.2B LLM that assists users, wrapped in a strict concurrency queue to prevent server RAM overload.
* **Bandwidth Saver Uploads:** Bypasses the 22 Mbps server upload limit by generating pre-signed cloud URLs (S3/R2) for massive Game Jam file submissions.
* **CGNAT Bypass:** The entire platform is tunneled securely to the public internet without port forwarding.

---

## 🛠️ Tech Stack & Architecture
* **OS:** Headless Debian Linux
* **Backend:** Python 3.11+, Flask, Gunicorn
* **Database:** SQLite (Configured with `WAL` mode & `JSON1` for high concurrency and dynamic data)
* **Frontend:** HTMX + Pico.css (Zero-build, under 20KB total payload for instant loading)
* **Networking:** Nginx Reverse Proxy, Cloudflare Tunnels (`cloudflared` for web), Playit.gg (TCP/UDP Game Tunnel)
* **CI/CD & DevOps:** GitHub Actions (pytest, bandit) + Gemini AI API for Automated Pull Request Code Reviews.

---

## 🧠 Engineering Solutions to Hardware Constraints

### 1. The RAM Bottleneck (8GB Limit)
Running a web server, a C# game server, and an AI model simultaneously risks Out-Of-Memory (OOM) crashes. 
* **Solution:** Implemented `asyncio.Semaphore(1)` around the LLM inference. Only one AI request processes at a time, returning an HTTP 202 "Thinking" status to concurrent users, keeping RAM usage strictly capped.

### 2. The Bandwidth Bottleneck (22 Mbps Upload)
Hosting 500MB Game Jam ZIPs locally would choke the network and disconnect multiplayer game users. 
* **Solution:** The Flask API generates Cloudflare R2/S3 Pre-signed POST URLs. Users upload files directly from their browser to the cloud bucket, bypassing the local server network entirely.

### 3. The ISP CGNAT Problem
The local ISP blocks incoming web traffic, making traditional port forwarding impossible. 
* **Solution:** `cloudflared` handles HTTP/HTTPS web traffic via outbound tunneling, and `playit.gg` handles raw TCP/UDP game traffic, making the server publicly accessible without router configuration.

---

## ⚙️ Local Development Setup

**Clone the repository:**
   git clone [https://github.com/your-username/scalable-micro-platform.git](https://github.com/your-username/scalable-micro-platform.git)
   cd scalable-micro-platform
   Create and activate a virtual environment:

    python3 -m venv venv
    source venv/bin/activate

    Install dependencies:

    pip install -r requirements.txt

    Set up Environment Variables:
    Create a .env file in the root directory and add your secret keys (e.g., Cloudflare R2 credentials, Gemini API key).

    Run the Flask development server:

    flask run --debug

🧪 Testing & CI/CD (Shift-Left)

This project utilizes a "Shift-Left" testing approach integrated with Jira. On every push and Pull Request, GitHub Actions will automatically run:

    flake8 for Python linting.

    pytest for unit testing the API and database logic.

    bandit for security and SQL injection scanning.

    Gemini AI Code Review: An automated agent that analyzes the git diff of Pull Requests for bugs, security flaws, and best practices.

📄 License

This project is licensed under the Creative Commons Zero v1.0 Universal (CC0 1.0) license. You are free to copy, modify, distribute, and perform the work, even for commercial purposes, all without asking permission.
