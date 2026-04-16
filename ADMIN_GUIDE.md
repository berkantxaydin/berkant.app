# 🔐 Proglem Admin & Database Guide

This guide explains how to manage the platform, interact with the SQLite database, and use administrative features.

---

## 🛠 Direct Database Interaction
Since we use **SQLite**, you don't need a running server process to check your data. Use the `sqlite3` command line tool.

### Accessing the DB
Open your terminal in the project root and run:
```powershell
sqlite3 proglem.db
```

### Useful SQL Commands
Once inside the `sqlite3` shell:
- **List Tables**: `.tables`
- **View Schema**: `.schema Users`
- **Check Error Logs**: `SELECT * FROM Analytics_Logs ORDER BY created_at DESC LIMIT 10;`
- **Promote a User to Admin**:
  ```sql
  UPDATE Users SET is_admin = 1 WHERE username = 'your_username';
  ```
- **Exit**: `.quit`

---

## 🔑 Admin Secret Code
When registering a new account, you can gain immediate Admin status by entering the secret code in the "Admin Code" field.

- **Current Secret**: `PROGLEM_ADMIN_SECRET`
- **Where to change it**: Found in `app/routes/auth_routes.py` (Line 72).

---

## 📊 Analytics & Error Management
- **Filtered Logging**: We now only log requests that result in **400/500 errors**. Success traffic is ignored to save space/RAM.
- **Clearing Logs**: Go to the **Server Portal** while logged in as an admin. Under **Traffic Analytics**, click the **"Clear Error Logs"** button.

---

## 🖥 Monitoring the Server
To see raw logs while the server is running on Windows:
1. Open a new terminal.
2. Run: `Get-Content error.log -Wait -Tail 20` (This acts like `tail -f` on Linux).

---

## 🚀 Deployment (GitHub Actions)
The CI/CD pipeline is configured in `.github/workflows/ci.yml`.
- **Triggers**: Every Pull Request to `dev` or `main`.
- **Requirements**: Tests must pass and security scans (`bandit`) must find no high-severity vulnerabilities.
