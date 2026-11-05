# Deploying Form 141 Automation Platform to Render

This guide walks you through deploying the complete platform (React Frontend, FastAPI Backend, Redis Queue, and Playwright Chromium Worker) to **[Render.com](https://render.com)**.

---

## Architecture on Render

```
┌─────────────────────────────────────────────────────────────┐
│                 Render Web Service (Docker)                 │
│                                                             │
│  ┌───────────────────┐    ┌───────────────────────────────┐ │
│  │   React SPA (UI)  │◄───┤    FastAPI Backend Server     │ │
│  │  (Built on /app)  │    │     (Port 10000 / $PORT)      │ │
│  └───────────────────┘    └──────────────┬────────────────┘ │
│                                          │                  │
│  ┌───────────────────────────────────────┴────────────────┐ │
│  │     Playwright Chromium Worker (with Xvfb & VNC)       │ │
│  └────────────────────────────────────────────────────────┘ │
└───────────────────────────▲──────────────────▲──────────────┘
                            │                  │
           ┌────────────────┴────┐        ┌────┴────────────────┐
           │   Render Redis      │        │  Render PostgreSQL  │
           │  (Queue / PubSub)   │        │     (Database)      │
           └─────────────────────┘        └─────────────────────┘
```

---

## Step 1: Push Code to GitHub

Open **PowerShell** or Git Bash in `FormFilling141`:

```powershell
cd "E:\5th sem\WT\income-tax-vps\income-tax-antigravity-vps\FormFilling141"

# Initialize git if not already done
git init
git add .
git commit -m "feat: render deployment configuration with Dockerfile and render.yaml"

# Create a repo on github.com (e.g. form141-platform) and push:
git remote add origin https://github.com/<your-username>/<your-repo-name>.git
git branch -M main
git push -u origin main
```

---

## Step 2: Deploy with Render Blueprint (1-Click Setup)

1. Log in to your **[Render Dashboard](https://dashboard.render.com)**.
2. In the top right, click **New +** and select **Blueprint**.
3. Connect your GitHub repository.
4. Render will automatically detect `render.yaml` and configure:
   * **`form141-platform`**: The unified Docker Web Service.
   * **`form141-redis`**: Managed Redis key-value store.
   * **`form141-db`**: Managed PostgreSQL database.
5. Click **Apply**.
6. Render will build the Docker image, run migrations, and deploy!

---

## Step 3: Or Deploy as a Single Web Service (Alternative)

If you prefer to deploy as a standalone Web Service:

1. Click **New +** -> **Web Service**.
2. Select your repository.
3. Configure the settings:
   * **Name:** `form141-platform`
   * **Language / Environment:** `Docker`
   * **Dockerfile Path:** `./Dockerfile`
   * **Instance Type:** `Starter` (512MB–1GB RAM recommended for Chromium)
4. Add the following **Environment Variables**:
   * `ENV` = `production`
   * `PORTAL_MODE` = `real`
   * `SECRET_KEY` = (Click *Generate* or enter a random 32-char string)
   * `ENCRYPTION_MASTER_KEY` = `Nt2FDh26fcarOyx4pF48qLbNafloz4fmG2TeAZJCsxU=`
   * `DATABASE_URL` = (Your Render PostgreSQL connection string, or omit to use internal SQLite)
   * `REDIS_URL` = (Your Render Redis connection string)
5. Click **Create Web Service**.

---

## Step 4: Access Your Deployed Platform

Once the deployment completes (usually 3–5 minutes for Docker + Chromium build):

* Visit your Render URL: `https://<your-service-name>.onrender.com`
* Log in with:
  * **Username:** `admin`
  * **Password:** `admin123`

---

## Resource Tip for Chromium on Render

> [!TIP]
> **RAM Requirement:** Running headless Chromium with Playwright in Docker requires ~500MB to 1GB of memory during form execution. 
> It is recommended to choose the **Starter Plan ($7/mo)** or higher on Render instead of the Free tier (which has a strict 512MB cap and may kill Chromium processes if memory spikes).
