#!/bin/bash
set -e

echo "=================================================="
echo "  Form 141 Automation Worker - VPS Entrypoint"
echo "=================================================="

# 1. Start Xvfb virtual display if not already running
export DISPLAY="${DISPLAY:-:99}"
if ! pgrep -x "Xvfb" > /dev/null; then
    echo "Starting Xvfb virtual display on $DISPLAY (1280x800x24)..."
    rm -f /tmp/.X*-lock /tmp/.X11-unix/X*
    Xvfb "$DISPLAY" -screen 0 1280x800x24 -nolisten tcp &
    sleep 1
else
    echo "Xvfb virtual display already active on $DISPLAY."
fi

# 2. Start x11vnc attached strictly to 127.0.0.1:5900 (private to container/pod)
VNC_PORT="${VNC_PORT:-5900}"
if ! pgrep -x "x11vnc" > /dev/null; then
    echo "Starting x11vnc server on 127.0.0.1:$VNC_PORT..."
    x11vnc -display "$DISPLAY" -forever -shared -nopw -listen 0.0.0.0 -rfbport "$VNC_PORT" &
    sleep 1
else
    echo "x11vnc already running on port $VNC_PORT."
fi

# 3. Start Python Worker
echo "Starting Form 141 Automation Worker..."
exec python -m apps.worker.main
