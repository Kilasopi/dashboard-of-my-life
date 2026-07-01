# Dashboard of My Life

A local-first personal dashboard for managing programming workflows, sim racing routines, timers, storage checks, and quality-of-life automations.

## Project Structure

```txt
dashboard-of-my-life/
├─ app/
│  ├─ frontend/   # React + TypeScript + Vite + Tailwind + shadcn/ui
│  └─ backend/    # FastAPI
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
