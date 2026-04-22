# Windows Release & Portability Guide

This document outlines how to package the **proglem** platform for distribution to other Windows machines without requiring manual path configurations or permission fixes.

## 1. Portability Principles

To make the platform run on any computer:
- **Avoid Absolute Paths**: Never use `C:\Users\berka\...`. Use relative paths derived from the script's location.
- **Embedded Python**: For a true "one-click" release, include a [Portable Python](https://github.com/indygreg/python-build-standalone) distribution inside the project folder.
- **Self-Healing Scripts**: Scripts should detect the environment and create/repair the virtual environment automatically.

## 2. Recommended Release Structure

A portable release should look like this:
```text
proglem-release/
├── bin/                # Nginx, cloudflared, playit.gg executables
├── python/             # (Optional) Portable Python interpreter
├── app/                # Flask application code
├── scripts/            # Startup and management scripts
├── venv/               # (Generated) Local virtual environment
├── run.bat             # One-click entry point
└── requirements.txt    # Dependencies
```

## 3. Creating the Release

### Step A: Refactor Scripts for Portability
Update all `.ps1` and `.bat` files to use `$PSScriptRoot` to find the project directory.
Example:
```powershell
$ProjectDir = (Get-Item $PSScriptRoot).Parent.FullName
```

### Step B: Handle the "Global Python" Problem
Instead of searching `AppData`, the script should try:
1. A local `python/` folder (if you bundle it).
2. The `py` launcher (which works if any Python is installed).
3. The system `PATH`.

### Step C: One-Click Entry Point (`run.bat`)
Create a simple batch file in the root directory:
```batch
@echo off
powershell -ExecutionPolicy Bypass -File "scripts\restart_server.ps1"
pause
```

## 4. Permission Considerations

When distributing to other users:
- **Folder Location**: Advise users to extract the project to `C:\proglem` or `C:\Users\Public\proglem` to avoid permission issues related to private user folders.
- **Execution Policy**: Use `-ExecutionPolicy Bypass` when calling scripts.

## 5. Building a Standalone EXE (Advanced)

If you want a single file:
1. Use **PyInstaller** to bundle the background worker.
2. Use **Nuitka** for the Flask application (for better performance).
3. Bundle Nginx and other binaries as "Data files".

> [!TIP]
> For most use cases, a **ZIP distribution** with a `run.bat` and relative paths is the most reliable and transparent way to share the platform while adhering to the "No Bloat" rule.
