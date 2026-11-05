from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone, timedelta

from apps.backend.app.database.config import get_db
from apps.backend.app.database import models
from apps.backend.app.services.queue_manager import queue_manager
from apps.backend.app.services.session_service import session_service
from apps.backend.app.auth.encryption import decrypt_data
from apps.backend.app.api.jobs import mask_pan

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

@router.get("/summary")
def get_dashboard_summary(db: Session = Depends(get_db)):
    # 1. Total counts by status
    status_counts = dict(
        db.query(models.Job.status, func.count(models.Job.id))
        .group_by(models.Job.status)
        .all()
    )

    total_jobs = db.query(models.Job).count()
    total_customers = db.query(models.Customer).count()
    
    queued = status_counts.get("QUEUED", 0)
    processing = status_counts.get("PROCESSING", 0)
    preview_pending = status_counts.get("PREVIEW_PENDING", 0)
    payment_pending = status_counts.get("PAYMENT_PENDING", 0)
    completed = status_counts.get("COMPLETED", 0)
    failed = status_counts.get("FAILED", 0)
    manual_intervention = status_counts.get("MANUAL_INTERVENTION", 0)
    cancelled = status_counts.get("CANCELLED", 0)

    # Queue completion percentage
    completion_percentage = 0
    if total_jobs > 0:
        completion_percentage = round((completed / total_jobs) * 100, 1)

    now = datetime.now(timezone.utc)

    # 2a. Build list of all PREVIEW_PENDING jobs
    preview_jobs = (
        db.query(models.Job)
        .filter(models.Job.status == "PREVIEW_PENDING")
        .order_by(models.Job.created_at.asc())
        .all()
    )

    preview_pending_jobs = []
    for pj in preview_jobs:
        cust = db.query(models.Customer).filter(models.Customer.id == pj.customer_id).first()
        fil = db.query(models.Filing).filter(models.Filing.id == pj.filing_id).first() if pj.filing_id else None
        elapsed = 0
        ref_time = pj.preview_reached_at or pj.started_at or pj.updated_at or pj.created_at
        if ref_time:
            if ref_time.tzinfo is None:
                ref_time = ref_time.replace(tzinfo=timezone.utc)
            elapsed = max(0, int((now - ref_time).total_seconds()))

        raw_pan = decrypt_data(cust.pan_encrypted) if cust and cust.pan_encrypted else ""
        masked_pan = mask_pan(raw_pan)
        meta = session_service.get_session_metadata(pj.id)
        session_avail = bool(meta and meta.get("session_available", False))

        preview_pending_jobs.append({
            "id": pj.id,
            "job_reference": pj.job_reference,
            "customer_id": pj.customer_id,
            "customer_name": cust.name if cust else "N/A",
            "customer_code": cust.customer_code if cust else "N/A",
            "pan_masked": masked_pan,
            "filing_id": pj.filing_id,
            "filing_reference": fil.filing_reference if fil else "N/A",
            "amount": fil.amount if fil else 0.0,
            "tds_amount": fil.tds_amount if (fil and fil.tds_amount is not None) else None,
            "status": pj.status,
            "current_step": pj.current_step,
            "elapsed_seconds": elapsed,
            "attempt_count": pj.attempt_count,
            "session_available": session_avail,
            "preview_metadata": pj.preview_metadata,
            "preview_reached_at": pj.preview_reached_at.isoformat() if pj.preview_reached_at else None,
            "created_at": pj.created_at.isoformat() if pj.created_at else None
        })

    # 2b. Build list of all PAYMENT_PENDING jobs
    pending_jobs = (
        db.query(models.Job)
        .filter(models.Job.status == "PAYMENT_PENDING")
        .order_by(models.Job.created_at.asc())
        .all()
    )

    payment_pending_jobs = []
    for pj in pending_jobs:
        cust = db.query(models.Customer).filter(models.Customer.id == pj.customer_id).first()
        fil = db.query(models.Filing).filter(models.Filing.id == pj.filing_id).first() if pj.filing_id else None
        
        elapsed = 0
        ref_time = pj.started_at or pj.updated_at or pj.created_at
        if ref_time:
            if ref_time.tzinfo is None:
                ref_time = ref_time.replace(tzinfo=timezone.utc)
            elapsed = max(0, int((now - ref_time).total_seconds()))

        raw_pan = decrypt_data(cust.pan_encrypted) if cust and cust.pan_encrypted else ""
        masked_pan = mask_pan(raw_pan)

        # Quick check for session availability from runtime metadata
        meta = session_service.get_session_metadata(pj.id)
        session_avail = bool(meta and meta.get("session_available", False))

        payment_pending_jobs.append({
            "id": pj.id,
            "job_reference": pj.job_reference,
            "customer_id": pj.customer_id,
            "customer_name": cust.name if cust else "N/A",
            "customer_code": cust.customer_code if cust else "N/A",
            "pan_masked": masked_pan,
            "filing_id": pj.filing_id,
            "filing_reference": fil.filing_reference if fil else "N/A",
            "amount": fil.amount if fil else 0.0,
            "tds_amount": fil.tds_amount if (fil and fil.tds_amount is not None) else None,
            "status": pj.status,
            "current_step": pj.current_step,
            "elapsed_seconds": elapsed,
            "attempt_count": pj.attempt_count,
            "session_available": session_avail,
            "created_at": pj.created_at.isoformat() if pj.created_at else None
        })

    # 3. Find currently actively automating or intervention-requiring job
    processing_job = (
        db.query(models.Job)
        .filter(models.Job.status.in_(["PROCESSING", "MANUAL_INTERVENTION"]))
        .order_by(models.Job.updated_at.desc())
        .first()
    )

    # For active_job: prefer PROCESSING / MANUAL_INTERVENTION -> PREVIEW_PENDING -> PAYMENT_PENDING
    active_job = processing_job or (preview_jobs[0] if preview_jobs else None) or (pending_jobs[0] if pending_jobs else None)

    active_job_info = None
    if active_job:
        customer = db.query(models.Customer).filter(models.Customer.id == active_job.customer_id).first()
        elapsed_seconds = 0
        if active_job.started_at:
            started = active_job.started_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            elapsed_seconds = max(0, int((now - started).total_seconds()))
            
        active_job_info = {
            "id": active_job.id,
            "job_reference": active_job.job_reference,
            "customer_id": active_job.customer_id,
            "customer_name": customer.name if customer else "N/A",
            "customer_code": customer.customer_code if customer else "N/A",
            "status": active_job.status,
            "current_step": active_job.current_step,
            "elapsed_seconds": elapsed_seconds,
            "attempt_count": active_job.attempt_count
        }

    # 4. Check worker heartbeat
    now_utc = datetime.now(timezone.utc)
    recent_threshold = now_utc - timedelta(seconds=20)
    active_workers = (
        db.query(models.Worker)
        .filter(models.Worker.status == "ONLINE", models.Worker.last_heartbeat >= recent_threshold)
        .all()
    )
    worker_online = len(active_workers) > 0
    worker_id = active_workers[0].worker_id if active_workers else None

    # Queue state
    queue_state = queue_manager.get_state()

    return {
        "metrics": {
            "total_clients": total_customers,
            "total_jobs": total_jobs,
            "ready": status_counts.get("READY", 0) + status_counts.get("VALIDATION_REQUIRED", 0),
            "queued": queued,
            "processing": processing,
            "preview_pending": preview_pending,
            "payment_pending": payment_pending,
            "completed": completed,
            "failed": failed,
            "manual_intervention": manual_intervention,
            "cancelled": cancelled,
            "completion_percentage": completion_percentage
        },
        "active_job": active_job_info,
        "preview_pending_jobs": preview_pending_jobs,
        "payment_pending_jobs": payment_pending_jobs,
        "system": {
            "queue_state": queue_state,
            "worker_status": "ONLINE" if worker_online else "OFFLINE",
            "worker_id": worker_id,
            "browser_status": "ACTIVE" if (active_job or payment_pending_jobs) else "READY"
        }
    }
