from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional
from datetime import datetime, timezone, timedelta
import os
import redis

from apps.backend.app.database.config import get_db, engine
from apps.backend.app.database import models

router = APIRouter(prefix="/api/system", tags=["System"])

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

@router.get("/health")
def get_system_health(db: Session = Depends(get_db)):
    """Comprehensive health check across API, DB, Redis, and Worker without revealing secrets."""
    # 1. DB Health
    db_status = "ONLINE"
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
    except Exception as dbe:
        db_status = "OFFLINE"

    # 2. Redis Health
    redis_status = "OFFLINE"
    try:
        r = redis.from_url(REDIS_URL, decode_responses=True)
        if r.ping():
            redis_status = "ONLINE"
    except Exception:
        redis_status = "OFFLINE"

    # 3. Worker Health
    now_utc = datetime.now(timezone.utc)
    stale_threshold = now_utc - timedelta(seconds=25)
    active_worker = (
        db.query(models.Worker)
        .filter(models.Worker.status == "ONLINE", models.Worker.last_heartbeat >= stale_threshold)
        .first()
    ) if db_status == "ONLINE" else None
    worker_status = "ONLINE" if active_worker else "OFFLINE"

    overall = "HEALTHY" if (db_status == "ONLINE" and redis_status == "ONLINE") else "DEGRADED"

    return {
        "status": overall,
        "timestamp": now_utc.isoformat(),
        "components": {
            "api": "ONLINE",
            "database": db_status,
            "redis": redis_status,
            "worker": worker_status,
            "browser": "READY" if worker_status == "ONLINE" else "STANDBY"
        }
    }

@router.get("/live")
def liveness():
    """Lightweight process liveness probe for Docker/Kubernetes."""
    return {"status": "alive"}

@router.get("/ready")
def readiness(db: Session = Depends(get_db)):
    """Readiness probe verifying DB connectivity."""
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Database not ready")


@router.get("/workers")
def list_workers(db: Session = Depends(get_db)):
    workers = db.query(models.Worker).order_by(desc(models.Worker.last_heartbeat)).all()
    now_utc = datetime.now(timezone.utc)
    
    result = []
    for w in workers:
        is_live = False
        if w.last_heartbeat:
            hb = w.last_heartbeat
            if hb.tzinfo is None:
                hb = hb.replace(tzinfo=timezone.utc)
            is_live = (now_utc - hb).total_seconds() < 25

        result.append({
            "id": w.id,
            "worker_id": w.worker_id,
            "hostname": w.hostname,
            "status": "ONLINE" if is_live else "OFFLINE",
            "current_job_id": w.current_job_id,
            "last_heartbeat": w.last_heartbeat.isoformat() if w.last_heartbeat else None
        })
    return result

@router.get("/audit")
def list_audit_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db)
):
    query = db.query(models.AuditLog)
    total = query.count()
    logs = query.order_by(desc(models.AuditLog.timestamp)).offset((page - 1) * limit).limit(limit).all()

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "items": [
            {
                "id": l.id,
                "user_id": l.user_id,
                "action": l.action,
                "entity_type": l.entity_type,
                "entity_id": l.entity_id,
                "metadata": l.metadata_json,
                "timestamp": l.timestamp.isoformat() if l.timestamp else None
            }
            for l in logs
        ]
    }
