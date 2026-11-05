#!/bin/bash
set -e

echo "=================================================="
echo "  Form 141 Automation Platform - Render Startup"
echo "=================================================="

# 1. Start Xvfb virtual display
export DISPLAY="${DISPLAY:-:99}"
if ! pgrep -x "Xvfb" > /dev/null; then
    echo "Starting Xvfb on $DISPLAY..."
    rm -f /tmp/.X*-lock /tmp/.X11-unix/X*
    Xvfb "$DISPLAY" -screen 0 1280x800x24 -nolisten tcp &
    sleep 1
fi

# 2. Start x11vnc for remote browser viewing
VNC_PORT="${VNC_PORT:-5900}"
if ! pgrep -x "x11vnc" > /dev/null; then
    echo "Starting x11vnc on port $VNC_PORT..."
    x11vnc -display "$DISPLAY" -forever -shared -nopw -listen 0.0.0.0 -rfbport "$VNC_PORT" &
    sleep 1
fi

# 3. Auto-run database migrations if Postgres or SQLite is configured
echo "Applying database schema..."
python -c "
from apps.backend.app.database.config import init_db
init_db()
print('Database initialized.')
" || true

# 4. Start Worker in background
echo "Starting Automation Worker in background..."
python -m apps.worker.main &

# 5. Start FastAPI Backend on Render's assigned $PORT
PORT="${PORT:-10000}"
echo "Starting FastAPI Backend on port $PORT..."
exec python -m uvicorn apps.backend.app.main:app --host 0.0.0.0 --port "$PORT"
