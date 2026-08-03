# Dashboard of My Life

A local-first personal dashboard for managing programming workflows, sim racing routines, timers, storage checks, and quality-of-life automations.

## Project Structure

```txt
dashboard-of-my-life/
├─ docker-compose.yml
├─ app/
│  ├─ frontend/
│  │  ├─ Dockerfile
│  │  └─ .dockerignore
│  └─ backend/
│     ├─ Dockerfile
│     └─ .dockerignore
├─ data/          # Local app data, ignored by git
├─ docs/          # Planning and documentation
├─ scripts/       # Local helper scripts
└─ README.md
```

## Frontend

```bat
cd app\frontend
npm install
npm run dev
```

Default frontend URL:

```txt
http://localhost:3000
```

## Backend

```bat
cd app\backend
.venv\Scripts\activate
uvicorn app.main:app --reload
```

Default backend URL:

```txt
http://localhost:8000
```

API docs:

```txt
http://localhost:8000/docs
```

## Desktop App (Windows)

Packages the dashboard into a single portable `DashboardOfMyLife.exe` - the FastAPI
backend serves the built frontend directly (one process, one port), wrapped in a
native window via `pywebview`. No Docker needed to run it.

```bat
cd app\frontend
npm install
npm run build

cd ..\backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-desktop.txt
pyinstaller DashboardOfMyLife.spec
```

The exe is written to `app\backend\dist\DashboardOfMyLife.exe`. For full CPU/GPU
temperatures and per-drive stats, run
[LibreHardwareMonitor](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor)
with **Options > Remote Web Server** enabled (default port 8085) before launching -
otherwise the System Health card falls back to approximate CPU/memory plus real
drive-letter usage from `psutil`.

## Desktop App (Linux)

Same PyInstaller spec, built natively on Linux instead of cross-compiled - it
produces a single-file ELF binary (`DashboardOfMyLife`) instead of an `.exe`.
`pywebview` needs a GTK WebKit backend on Linux, so install that first:

```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.1

cd app/frontend
npm install
npm run build

cd ../backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-desktop.txt
pyinstaller DashboardOfMyLife.spec
```

The binary is written to `app/backend/dist/DashboardOfMyLife` - mark it executable
(`chmod +x`) and run it directly, or double-click it from a file manager that
allows executing local files. No LibreHardwareMonitor equivalent is needed on
Linux: CPU/GPU temperatures and drive stats are read natively via `psutil`'s
`hwmon` sensors (and `nvidia-smi` if an NVIDIA GPU is present), so the System
Health card gets real temperature data out of the box.

## Backend Linting

```bat
cd app\backend
.venv\Scripts\activate
ruff check .
```

## Frontend Checks

```bat
cd app\frontend
npm run lint
npm run build
```

## Current Status

Initialized project scaffold only. No dashboard features have been implemented yet.

Current setup includes:

- Git repository
- React + TypeScript + Vite frontend
- Tailwind CSS
- shadcn/ui
- FastAPI backend
- Python virtual environment
- Ruff backend linting
- Basic project folders

## Goal

The goal of this project is to build a personal local dashboard that can eventually help manage:

- Work/programming mode
- Sim racing mode
- Calendar
- Timers and reminders
- Local file and storage checks
- Stream Deck-triggered routines
- Action history
- Quality-of-life automations

And eventually make it a desktop application that can run on my device

## Planned Features

### **Calendar**

The calendar will be able to help me keep track of assignments, classes and any planned events.

### **Racing Calendar**

A racing calendar will allow me to track what racing events are upcoming, both IRL and in the sim.

### **iRacing Helper**

This will allow me to see any upcoming events and track my progress as a driver. (Ideally some streamdeck components too with another project)

### **Timers and Reminders**

I want to be able to put up timers and reminders for myself and be notified when they are completed.

### **Local Device Data Management**

Tracking disk usage, CPU usage, WiFi usage, temperatures, and whatever else I can think of.

### **Spotify Now Playing**

Have a mini now playing widget

## Potential Features

### **"Work Modes"**

I'd want to be able to click a button and have my device enter certain modes: Work, Sim Racing, Streaming, Programming

### **Github Integration**

To be able to see PR statuses

### **Discord integration**

To be able to see who is playing what and if people are in voice calls
