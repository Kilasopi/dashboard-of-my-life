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

## Potential Features

### **"Work Modes"**

I'd want to be able to click a button and have my device enter certain modes: Work, Sim Racing, Streaming, Programming

### **Github Integration**

To be able to see PR statuses

### **Discord integration**

To be able to see who is playing what and if people are in voice calls
