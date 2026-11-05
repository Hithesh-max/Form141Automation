#!/bin/bash
set -e

echo "=================================================="
echo "  Form 141 Automation Platform - Render Startup"
echo "=================================================="

# 0. Start local Redis if no external REDIS_URL provided or if pointing to localhost
export REDIS_URL="${REDIS_URL:-redis://127.0.0.1:6379/0}"
if [[ "$REDIS_URL" == *"127.0.0.1"* ]] || [[ "$REDIS_URL" == *"localhost"* ]]; then
    echo "Starting local Redis server inside container..."
    mkdir -p /tmp/redis
    redis-server --daemonize yes --protected-mode no --logfile /tmp/redis/redis.log --dir /tmp/redis || true
    sleep 1
    if redis-cli ping > /dev/null 2>&1; then
        echo "Local Redis started successfully."
    else
        echo "Local Redis startup check:"
        cat /tmp/redis/redis.log || true
    fi
fi

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
export DATABASE_URL="${DATABASE_URL:-sqlite:///./form141.db}"
echo "Applying database schema with DATABASE_URL=$DATABASE_URL..."
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
