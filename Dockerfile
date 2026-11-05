# Multi-stage Dockerfile for Render Deployment
# Stage 1: Build React Frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /build
COPY apps/desktop/package*.json ./
RUN npm install
COPY apps/desktop/ ./
RUN npm run build

# Stage 2: Python Application with Playwright & Chromium
FROM python:3.11-slim

WORKDIR /app

# Install system libraries for Chromium, Playwright, Xvfb, and local Redis
RUN apt-get update && apt-get install -y --no-install-recommends \
    redis-server \
    redis-tools \
    xvfb \
    x11vnc \
    procps \
    curl \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxcb1 \
    libxkbcommon0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    fonts-liberation \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m playwright install chromium

# Copy Python application code
COPY apps ./apps
COPY alembic ./alembic
COPY alembic.ini .

# Copy compiled frontend from Stage 1
COPY --from=frontend-builder /build/dist ./apps/desktop/dist

# Copy startup script
COPY entrypoint_render.sh /entrypoint_render.sh
RUN chmod +x /entrypoint_render.sh

ENV DISPLAY=:99
ENV BROWSER_HEADLESS=false
ENV VNC_PORT=5900
ENV PORT=10000

EXPOSE 10000

CMD ["/entrypoint_render.sh"]
