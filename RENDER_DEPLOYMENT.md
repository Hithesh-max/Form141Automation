# 100% Free Render Deployment Guide (Form 141 Platform)

Deploy the entire platform (Frontend + Backend + Automation Worker + Redis Queue + Database) to **Render for FREE ($0/month)**.

---

## Why You Don't Need Any Paid Services

Standard multi-service deployments on Render charge for Redis ($7/mo) and Background Workers ($7/mo).

We have packaged the entire architecture into **ONE single self-contained Docker Web Service**:
* **Redis Server**: Runs locally inside the container (`redis-server`) — **$0**
* **Database**: Runs locally on SQLite (`form141.db`) — **$0**
* **Frontend**: Built and served directly by FastAPI from root `/` — **$0**
* **Automation Worker**: Runs as a background process inside the container — **$0**
* **Render Web Service**: Select the **Free Tier ($0/month)**

---

## Step 1: Push Code to GitHub

Open **PowerShell** in the project folder:

```powershell
cd "E:\5th sem\WT\income-tax-vps\income-tax-antigravity-vps\FormFilling141"

git init
git add .
git commit -m "feat: 100% free single-container render deployment"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo-name>.git
git push -u origin main
```

---

## Step 2: Deploy as a Free Web Service on Render

1. Log in to **[dashboard.render.com](https://dashboard.render.com)** (Sign up for free if you haven't).
2. Click the blue **New +** button in the top right.
3. Select **Web Service** (NOT Blueprint).
4. Connect your GitHub repository.
5. Fill in the service details:
   * **Name:** `form141-platform` (or any name you like)
   * **Region:** Any (e.g. *Oregon* or *Frankfurt*)
   * **Language / Runtime:** `Docker`
   * **Dockerfile Path:** `./Dockerfile`
   * **Instance Type:** Select **Free** ($0 / month)
6. Scroll down to **Environment Variables** and add:
   | Key | Value |
   | :--- | :--- |
   | `ENV` | `production` |
   | `PORTAL_MODE` | `real` |
   | `ENCRYPTION_MASTER_KEY` | `Nt2FDh26fcarOyx4pF48qLbNafloz4fmG2TeAZJCsxU=` |
   | `SECRET_KEY` | `form141-production-secret-key-32chars` |
7. Click **Deploy Web Service** at the bottom!

---

## Step 3: Access Your Platform

Render will spend ~3 to 4 minutes downloading the Chromium browser and building the Docker container.

Once it says **Live**:
1. Click the public URL Render gives you (e.g., `https://form141-platform.onrender.com`).
2. Log in with:
   * **Username:** `admin`
   * **Password:** `admin123`

---

> [!NOTE]
> **Free Tier Behavior:** Render's free tier spins down after 15 minutes of inactivity. When you open the URL after it has been asleep, it takes ~30–45 seconds for the container to wake up.
