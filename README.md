# Form 141 Automation Platform

A complete, production-quality desktop automation platform for securely importing client data,
queueing Form 141 TDS filing jobs, and running browser automation with real-time UI monitoring
and an employee payment-handoff workflow.

---

## Architecture

| Layer | Tech |
|-------|------|
| Database | SQLite (dev, zero setup) · PostgreSQL (production) |
| Queue | Redis list/BLMOVE · in-memory fallback when Redis offline |
| Backend | FastAPI · SQLAlchemy · Fernet encryption |
| Worker | Playwright/Chromium · asyncio |
| Desktop UI | React 18 · TypeScript · Vite · Tailwind CSS |

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10 + | Tested on 3.14 |
| Node.js | 18 + | Tested on v24 |
| Redis | Optional | Queue degrades gracefully to in-memory without it |
| PostgreSQL | Optional | Uses SQLite automatically for dev |

> **Docker is NOT required.** The system works out of the box with SQLite + in-memory queue.

---

## Quick Start (Windows)

### 1. Open project

```powershell
cd FormFilling141
```

### 2. Setup Python

```powershell
py -3 -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

### 3. Setup frontend

```powershell
cd apps\desktop
npm install
npm run build
cd ..\..
```

### 4. Configure `.env`

```powershell
Copy-Item .env.example .env
notepad .env
```

Set:

```env
DATABASE_URL=sqlite:///./form141.db
PORTAL_MODE=mock
ENCRYPTION_MASTER_KEY=YOUR_FERNET_KEY
```

Generate the Fernet key:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Paste it into `.env`.

### 5. Start

If PowerShell blocks the script:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Then:

```powershell
.\run_system.ps1
```

### 6. Open

Dashboard: `http://localhost:5173`

API: `http://localhost:8000/docs`

**First test:** keep `PORTAL_MODE=mock`. PostgreSQL and Redis are optional.


## Environment Variables (.env)

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | No | Defaults to `sqlite:///./form141.db` |
| `REDIS_URL` | No | Defaults to `redis://localhost:6379/0` |
| `ENCRYPTION_MASTER_KEY` | **Yes (prod)** | Fernet key for PAN encryption at rest |
| `PORTAL_MODE` | No | Set `mock` for offline testing without real portal |
| `SECRET_KEY` | No | Session secret — auto-generated if omitted |

Generate an encryption key:
```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## Running Tests

```powershell
.\venv\Scripts\pytest -v
# Expected: 19 passed in ~100s
```

Tests cover: PAN validation, import API, all REST endpoints, worker browser automation, recovery.

---

## Switching to Production

### PostgreSQL
```
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/form141
```
Tables are created automatically on first startup.

### Redis
```
REDIS_URL=redis://localhost:6379/0
```
Quick Docker run: `docker run -d -p 6379:6379 redis:7-alpine`

### Real Income Tax Portal
Open `apps/worker/portal/adapter.py`, update `_run_real_portal()` with real URLs/selectors,
then unset `PORTAL_MODE` (or set to `real`).

---

## Payment Handoff Workflow

```
Worker fills form → PAYMENT_PENDING
    ↓  Dashboard shows warning banner
Employee completes payment in open browser window
    ↓  Clicks "Confirm Payment" in dashboard
Backend sets job → COMPLETED
    ↓  Worker detects change (polls every 2s)
Worker closes browser → picks next job
```

---

## Security

| Feature | Implementation |
|---|---|
| PAN encryption at rest | Fernet (AES-128-CBC + HMAC-SHA256) |
| Password hashing | SHA-256 + per-user salt |
| PAN masking in API | `ABCDE****F` (first 5 + last 1) |
| Audit log | Every action written to AuditLog table |
| Admin seeding | First login seeds `admin`/`admin123` — change immediately |

---

## Recovery

```powershell
# Run once or schedule via Windows Task Scheduler
.\venv\Scripts\python -m apps.worker.recovery.monitor
```
Jobs stuck in `PROCESSING` > 10 min with a dead worker heartbeat are auto-requeued.

---

## Project Structure

```
FormFilling141/
├── apps/
│   ├── backend/app/
│   │   ├── api/           # auth, import, jobs, dashboard, queue, customers, system
│   │   ├── database/      # SQLAlchemy models + config
│   │   ├── services/      # validator.py, queue_manager.py, encryption
│   │   └── websocket/     # real-time event broadcaster
│   ├── worker/
│   │   ├── portal/        # adapter.py — real + mock portal
│   │   ├── workflows/     # job_workflow.py — end-to-end filing
│   │   ├── events/        # publisher.py — Redis pub/sub
│   │   ├── queue/         # manager.py — BLMOVE queue
│   │   └── recovery/      # monitor.py — stale-job detection
│   └── desktop/src/
│       ├── components/    # Header, MetricsOverview, ActiveJobCard, JobTable, ...
│       ├── App.tsx        # Root — WebSocket, polling, all state
│       └── types.ts       # Shared TypeScript interfaces
├── tests/                 # 19 pytest tests (all passing)
├── requirements.txt
├── pytest.ini
├── run_system.ps1         # One-click launcher
└── .env.example
```
