# 🔐 proglem Admin & Operations Guide

This guide covers database management, admin panel features, localization controls, and deployment operations.

---

## 🛠 Direct Database Access

The platform uses **SQLite** — no server process needed to inspect data. Use the built-in CLI tool.

```powershell
# Windows
sqlite3 proglem.db

# Docker (the DB lives in the mounted ./data volume)
docker exec -it proglem-app-1 sqlite3 /app/data/proglem.db
```

### Useful SQL Commands

```sql
.tables                                              -- List all tables
.schema Users                                        -- View a table schema
SELECT * FROM Analytics_Logs ORDER BY created_at DESC LIMIT 20;
SELECT g.title, COUNT(l.id) as likes FROM Godot_Games g LEFT JOIN Game_Likes l ON l.game_id = g.id GROUP BY g.id ORDER BY likes DESC;

-- Promote a user to Admin
UPDATE Users SET is_admin = 1 WHERE username = 'your_username';

.quit
```

### Reset the database (fresh start)
```powershell
# Windows local
Remove-Item proglem.db

# Docker — delete the data volume
docker compose down -v    # WARNING: destroys all data
docker compose up
```
The schema and default `💬 General` chat room are recreated automatically on next boot.

---

## 🔑 Admin Registration

When registering a new account, enter the admin secret code to gain immediate Admin status.

- **Current Secret**: `PROGLEM_ADMIN_SECRET`
- **Where to change it**: `app/routes/auth_routes.py` — search for `PROGLEM_ADMIN_SECRET`.

---

## 🌍 AI-Powered Translation (Admin Panel)

The platform auto-registers every UI string seen during rendering into `translations.json`.

### How to translate new strings:
1. Log in as Admin → go to `/admin`
2. Find the **"Scan & Translate Missing UI"** button
3. Click it — the local **Gemma 4 model** translates all missing keys in batches of 15
4. Progress is saved incrementally (no timeout risk)
5. Refresh any page and toggle 🇹🇷 to verify Turkish output

### Manual editing:
`translations.json` in the project root contains all translations. Format:
```json
{
  "en": { "My Key": "My Key" },
  "tr": { "My Key": "Benim Anahtarım" }
}
```

---

## 📊 Metrics & Analytics Dashboard (`/dashboard`)

The Admin dashboard shows:
- **Live CPU & RAM bars** — real `psutil` readings (CPU sampled over 0.5s for accuracy)
- **AI Core RAM** — memory used by the `llama-server` process specifically
- **Response time** — actual server-side time to generate the metrics HTML
- **Request analytics** — all HTTP traffic logged to `Analytics_Logs` table
- **Error log viewer** — tail of `error.log`, clearable from the panel

### Clearing analytics:
Admin Panel → **Traffic Analytics** → **"Clear Traffic Logs"** button.

---

## 🎮 Game Jam Management (Admin Panel)

- **Create Jam**: Set title, theme, start/end times, optional YouTube stream URL
- **Edit Jam**: Inline form with HTMX, no page reload needed
- **Delete Jam**: Removes the jam; submitted games remain but become unjammed
- **Chat Rooms**: Create/toggle/delete rooms, optionally tie them to a Jam

---

## 🖥 Live Log Monitoring

```powershell
# Windows — tail the error log
Get-Content error.log -Wait -Tail 20

# Docker
docker logs -f proglem-app-1
```

---

## 🚀 Deployment & Releases

### Git flow
```
feature/my-feature  →  dev  →  main
```
Never push directly to `main`. All changes go via Pull Request.

### Publishing a release
```bash
# 1. Merge dev → main via PR (CI must pass)
# 2. Tag the release
git tag v1.0.0
git push origin v1.0.0
```

GitHub Actions (`release.yml`) will automatically:
1. Run the full test suite
2. Build the Docker image
3. Push to `ghcr.io/berkantxaydin/berkant.app:latest` + `:v1.0.0`
4. Create a GitHub Release with `docker-compose.yml` as a downloadable asset

### CI checks on every PR
| Check | Tool |
|-------|------|
| Linting | `flake8` |
| Unit tests | `pytest` |
| Security scan | `bandit` |
| AI code review | Gemini API (posts comment on PR) |

---

## 📁 Key File Locations

| File | Purpose |
|------|---------|
| `proglem.db` | SQLite database (local dev) |
| `translations.json` | All EN/TR UI string pairs |
| `error.log` | Application error log |
| `llm_server_error.log` | llama-server debug output |
| `.env` | Secrets (S3 keys, SECRET_KEY) |
| `app/database.py` | Schema definitions + `init_db()` |
| `app/services/ai_service.py` | AI queue, context snapshot, llama-server management |
| `app/i18n.py` | Translation helper `t()` |
