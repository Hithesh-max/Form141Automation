# Form 141 Automation Platform — Ubuntu VPS Production Deployment Guide

This guide provides step-by-step instructions for deploying the Form 141 Filing Automation platform to an Ubuntu VPS using Docker Compose, Nginx, and Let's Encrypt HTTPS.

---

## 1. Architecture Overview

In production on an Ubuntu VPS, the architecture runs as containerized services communicating over an internal private Docker bridge network (`form141_network`):

| Service | Container Role | Public Access | Internal Port |
|---------|---------------|---------------|---------------|
| `frontend` | Nginx Reverse Proxy + React SPA | **Ports 80 & 443** (HTTP/HTTPS) | 80, 443 |
| `backend` | FastAPI Application Server | No (Proxied via Nginx) | 8000 |
| `worker` | Playwright Chromium + Xvfb + x11vnc | No (Private internal stream) | 5900 (VNC) |
| `postgres`| PostgreSQL Database | **No** (Private Docker network only) | 5432 |
| `redis` | Queue, Event Bus & Session Cache | **No** (Private Docker network only) | 6379 |

> [!IMPORTANT]
> **Zero Public Port Exposure for Internal Services:**
> PostgreSQL (5432), Redis (6379), Backend (8000), and VNC (5900) are **never** exposed to the public internet. All traffic enters through Nginx on ports 80/443. Remote browser viewing is streamed via an authenticated WebSocket proxy protected by HMAC-SHA256 tokens.

---

## 2. Project Preparation on Windows (Local Machine)

### A. Verify Clean Separation
1. Ensure your original development copy remains untouched in its separate folder.
2. Work exclusively on this VPS project copy (`FormFilling141`).
3. Check `.gitignore` to ensure `.env`, `*.db`, `venv/`, and sensitive files are excluded:
   ```powershell
   git status
   ```
   Ensure `form141.db` or `.env` are **not** listed under untracked or staged files.

### B. Commit and Push to a Private Repository
```powershell
git init
git add .
git commit -m "feat: VPS compatibility, remote browser viewer, and production Docker deployment"
git remote add origin git@github.com:your-organization/form141-vps.git
git push -u origin main
```

---

## 3. Ubuntu VPS Initial Setup

### A. System Update & Essential Tools
Connect to your VPS via SSH:
```bash
ssh user@your-vps-ip
```

Update system packages:
```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y curl git ufw fail2ban htop jq
```

### B. Configure Firewall (UFW)
Allow only SSH and Web traffic:
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow http
sudo ufw allow https
sudo ufw enable
```
Verify status:
```bash
sudo ufw status verbose
```
> [!CAUTION]
> Never open ports 5432, 6379, 8000, or 5900 in UFW.

### C. Install Docker and Docker Compose
Install the official Docker engine:
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```
Log out and log back in for group membership to take effect, then verify:
```bash
docker --version
docker compose version
```

---

## 4. Production Environment Configuration

### A. Clone Repository to Deployment Directory
```bash
sudo mkdir -p /opt/form141
sudo chown $USER:$USER /opt/form141
git clone git@github.com:your-organization/form141-vps.git /opt/form141
cd /opt/form141/FormFilling141
```

### B. Generate Secure Production Secrets
Run the following commands to generate strong, cryptographically secure keys:

```bash
# 1. Generate Fernet master key for PAN encryption at rest:
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# 2. Generate random 32-byte secret key for session tokens:
openssl rand -hex 32

# 3. Generate strong PostgreSQL password:
openssl rand -base64 24
```

### C. Create Production `.env`
```bash
cp .env.example .env
nano .env
```
Configure your production values:
```env
ENV=production
PORTAL_MODE=real

# PostgreSQL Credentials
POSTGRES_USER=form141_admin
POSTGRES_PASSWORD=<INSERT_GENERATED_POSTGRES_PASSWORD>
POSTGRES_DB=form141
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_URL=redis://redis:6379/0

# Security Keys
SECRET_KEY=<INSERT_GENERATED_32_BYTE_HEX>
ENCRYPTION_MASTER_KEY=<INSERT_GENERATED_FERNET_KEY>

# Worker Automation
BROWSER_HEADLESS=false
MAX_CONCURRENT_JOBS=1
DISPLAY=:99
VNC_PORT=5900

# Public Port
PORT=80
```
Protect file permissions:
```bash
chmod 600 .env
```

---

## 5. Deployment & Service Initialization

### A. Validate Docker Compose Configuration
```bash
docker compose config
```
Ensure no syntax or environment variable errors are reported.

### B. Build and Start Services
```bash
docker compose build
docker compose up -d
```

### C. Run Database Migrations
Execute Alembic migrations inside the running backend container:
```bash
docker compose exec backend alembic upgrade head
```

### D. Verify Service Health
Check running container states:
```bash
docker compose ps
```
Expected output:
- `postgres`: Up (healthy)
- `redis`: Up (healthy)
- `backend`: Up (healthy)
- `worker`: Up
- `frontend`: Up

Check system health endpoint:
```bash
curl -s http://localhost/api/system/health | jq .
```
Expected response:
```json
{
  "status": "HEALTHY",
  "components": {
    "api": "ONLINE",
    "database": "ONLINE",
    "redis": "ONLINE",
    "worker": "ONLINE",
    "browser": "READY"
  }
}
```

---

## 6. Configuring HTTPS with Let's Encrypt

If pointing your domain name (e.g., `tax.yourdomain.com`) to the VPS IP:

### A. Install Certbot
```bash
sudo apt-get install -y certbot python3-certbot-nginx
```

### B. Obtain Certificate
```bash
sudo certbot certonly --standalone -d tax.yourdomain.com
```

### C. Mount SSL Certificates in `docker-compose.yml`
Add certificate volumes to the `frontend` service in `docker-compose.yml`:
```yaml
    volumes:
      - /etc/letsencrypt:/etc/letsencrypt:ro
    ports:
      - "80:80"
      - "443:443"
```
And enable HTTPS listening in `infrastructure/docker/nginx.conf`.

---

## 7. Operational Runbook

### A. Starting, Stopping, and Restarting
```bash
# View live logs of all services
docker compose logs -f --tail=100

# View logs of worker only
docker compose logs -f worker

# Restart a specific service (e.g. after worker update)
docker compose restart worker

# Graceful full shutdown
docker compose stop

# Start back up
docker compose start
```

### B. Database Backup & Restore
**Create a backup:**
```bash
mkdir -p /opt/form141/backups
docker compose exec -T postgres pg_dump -U form141_admin form141 | gzip > /opt/form141/backups/form141_$(date +%Y%m%d_%H%M%S).sql.gz
```

**Restore a backup:**
```bash
gunzip < /opt/form141/backups/form141_YYYYMMDD_HHMMSS.sql.gz | docker compose exec -T postgres psql -U form141_admin form141
```

### C. Updating the Application
```bash
cd /opt/form141/FormFilling141
git pull origin main

# Re-run migrations if new database changes were pushed
docker compose exec backend alembic upgrade head

# Rebuild only modified services
docker compose up -d --build
```

---

## 8. Safe Troubleshooting Guide

| Symptom | Diagnosis Command | Solution |
|---------|-------------------|----------|
| Backend reports database offline | `docker compose logs postgres` | Verify `POSTGRES_USER` and `POSTGRES_PASSWORD` match in `.env`. Check disk space with `df -h`. |
| Worker shows `OFFLINE` in health check | `docker compose logs worker` | Verify worker process is running. Worker sends heartbeat every 5s. Check `docker compose ps worker`. |
| Remote browser viewer fails to load | `docker compose logs backend` | Ensure filing job is active and has an open session. Viewer tokens expire in 15 minutes; click "Open Browser Session" in the dashboard to refresh. |
| Redis connection refused | `docker compose logs redis` | Verify Redis health: `docker compose exec redis redis-cli ping`. |
| High memory usage | `docker stats` | Check memory limits. Chromium generally requires ~500MB RAM during active rendering. |

> [!WARNING]
> Never run `docker compose down -v` in production. The `-v` flag permanently deletes the PostgreSQL and Redis persistent volumes!
