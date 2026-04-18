# 🗄️ Database Management Guide (SQLite)

This platform uses **SQLite3** as its primary database. It is stored in a single file: `proglem.db`.

## 🛠️ Accessing the Database

You can interact with the database directly from the terminal using the `sqlite3` command-line tool.

### Open the database
```bash
sqlite3 proglem.db
```

### Useful SQLite Meta-Commands
While inside the `sqlite3` prompt:
- `.tables` : List all tables in the database.
- `.schema <table_name>` : See the structure (columns) of a specific table.
- `.mode box` : (Recommended) Formats output into a beautiful readable box.
- `.header on` : Shows column names in results.
- `.quit` : Exit the database shell.

---

## 🔍 Common SQL Commands

### 1. View Tables and Structure
```sql
-- List all tables
.tables

-- See how the Users table is built
.schema Users
```

### 2. Querying Data (Check things)
```sql
-- See all users
SELECT * FROM Users;

-- See only admins
SELECT * FROM Users WHERE is_admin = 1;

-- See the 10 most recent analytics logs
SELECT * FROM Analytics_Logs ORDER BY created_at DESC LIMIT 10;

-- See all chat messages from a specific user
SELECT * FROM Chat_Messages WHERE user_id = 5;
```

### 3. Deleting Data (Be Careful!)
> [!CAUTION]
> Always use a `WHERE` clause when deleting. If you run `DELETE FROM Users` without a `WHERE` clause, it will delete **EVERY** user in the database.

```sql
-- Delete a specific user by their ID
DELETE FROM Users WHERE id = 12;

-- Clear ALL analytics logs (same as the button in Admin Panel)
DELETE FROM Analytics_Logs;

-- Delete a specific game entry
DELETE FROM Godot_Games WHERE id = 3;
```

### 4. Updating Data
```sql
-- Make a user an admin manually
UPDATE Users SET is_admin = 1 WHERE username = 'berkant';

-- Change a game's validation status
UPDATE Godot_Games SET validation_status = 'Approved' WHERE id = 5;
```

---

## 📊 Available Tables Reference

| Table | Purpose |
| :--- | :--- |
| `Users` | Account information and permissions. |
| `Analytics_Logs` | Traffic tracking, error rates, and IP hashes. |
| `Godot_Games` | Submissions, view counts, and URLs. |
| `Game_Jams` | Event titles, themes, and timelines. |
| `CV_Catalog` | Developer portfolios and HTMX resumes. |
| `Chat_Messages` | All real-time messages across rooms. |
| `Chat_Rooms` | Room settings and Jam links. |
| `Game_Likes` | Keeps track of who liked which game. |
| `Game_Comments` | User feedback on games. |

---

## 💾 Backups
To create a manual backup of your database:
```powershell
cp proglem.db proglem_backup.db
```
*(Or use the automated `scripts/backup_db.ps1` script).*
