from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import json
import redis
import os

from apps.backend.app.database.config import get_db
from apps.backend.app.database import models
from apps.backend.app.services.queue_manager import queue_manager
from apps.backend.app.services.session_service import session_service
from apps.backend.app.services.browser_viewer_service import browser_viewer_service
from apps.backend.app.auth.encryption import decrypt_data
from apps.backend.app.api.auth import get_current_active_user

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

ACTIVE_JOB_STATUSES = [
    "QUEUED",
    "PROCESSING",
    "PREVIEW_PENDING",
    "PAYMENT_PENDING",
    "MANUAL_INTERVENTION",
    "REVIEW_REQUIRED",
    "WAITING_FOR_HUMAN",
    "PAYMENT_IN_PROGRESS"
]


def mask_pan(pan: Optional[str]) -> str:
    """Masks Indian PAN e.g. ABCDE1234F -> ABCDE****F or ****"""
    if not pan:
        return "N/A"
    clean = pan.strip().upper()
    if len(clean) == 10:
        return f"{clean[:5]}****{clean[-1]}"
    return f"{clean[:2]}****" if len(clean) > 4 else "****"

def publish_ws_event(event_type: str, job_id: str, status: str, message: str, payload: Optional[dict] = None):
    """Publishes event to Redis pubsub for real-time WebSocket distribution."""
    try:
        r = redis.from_url(REDIS_URL, decode_responses=True)
        event = {
            "event": event_type,
            "job_id": str(job_id),
            "status": status,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload or {}
        }
        r.publish("form141:events", json.dumps(event))
    except Exception:
        pass

@router.get("/active-lock")
def get_active_lock(db: Session = Depends(get_db)):
    """
    Returns the strict single-filing concurrency lock status (MAX_ACTIVE_FORM141_JOBS = 1).
    An active job is any job in QUEUED, PROCESSING, PREVIEW_PENDING, or PAYMENT_PENDING status.
    """
    active_job = (
        db.query(models.Job)
        .filter(models.Job.status.in_(ACTIVE_JOB_STATUSES))
        .order_by(desc(models.Job.updated_at))
        .first()
    )


    if not active_job:
        return {
            "has_active_job": False,
            "can_start": True,
            "active_job": None,
            "reason": None
        }

    customer = db.query(models.Customer).filter(models.Customer.id == active_job.customer_id).first()
    filing = db.query(models.Filing).filter(models.Filing.id == active_job.filing_id).first() if active_job.filing_id else None

    # Check if a live browser session exists
    session_meta = session_service.get_session_metadata(active_job.id)
    session_available = bool(session_meta and session_meta.get("session_available", False))

    reason_text = (
        f"Filing {active_job.job_reference} for {customer.name if customer else 'Unknown'} "
        f"is currently in status '{active_job.status}'. "
        f"Strict single-filing concurrency limit (MAX_ACTIVE_FORM141_JOBS = 1) is active. "
        f"Complete or cancel this filing before starting another."
    )

    return {
        "has_active_job": True,
        "can_start": False,
        "active_job": {
            "id": active_job.id,
            "job_reference": active_job.job_reference,
            "customer_id": active_job.customer_id,
            "customer_name": customer.name if customer else "N/A",
            "customer_code": customer.customer_code if customer else "N/A",
            "filing_id": active_job.filing_id,
            "filing_reference": filing.filing_reference if filing else "N/A",
            "status": active_job.status,
            "current_step": active_job.current_step,
            "session_available": session_available,
            "updated_at": active_job.updated_at.isoformat() if active_job.updated_at else None
        },
        "reason": reason_text
    }

@router.get("")
@router.get("/")
@router.get("/history")
def list_jobs(
    status: Optional[str] = Query(None, description="Filter by status: QUEUED, PROCESSING, PAYMENT_PENDING, COMPLETED, FAILED, CANCELLED"),
    search: Optional[str] = Query(None, description="Search by customer code, name, or job reference"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    query = db.query(models.Job)
    
    if status and status.upper() != "ALL":
        query = query.filter(models.Job.status == status.upper())

    if search:
        search_pattern = f"%{search}%"
        # Join customer to search name or customer_code
        query = query.join(models.Customer, models.Job.customer_id == models.Customer.id, isouter=True).filter(
            or_(
                models.Job.job_reference.ilike(search_pattern),
                models.Customer.customer_code.ilike(search_pattern),
                models.Customer.name.ilike(search_pattern)
            )
        )

    total_count = query.count()
    offset = (page - 1) * limit
    jobs = query.order_by(desc(models.Job.created_at)).offset(offset).limit(limit).all()

    items = []
    for j in jobs:
        customer = db.query(models.Customer).filter(models.Customer.id == j.customer_id).first()
        filing = db.query(models.Filing).filter(models.Filing.id == j.filing_id).first() if j.filing_id else None
        
        raw_pan = decrypt_data(customer.pan_encrypted) if customer and customer.pan_encrypted else ""
        masked_pan = mask_pan(raw_pan)

        items.append({
            "id": j.id,
            "job_reference": j.job_reference,
            "logical_filing_id": j.logical_filing_id,
            "customer_id": j.customer_id,
            "customer_code": customer.customer_code if customer else "N/A",
            "customer_name": customer.name if customer else "N/A",
            "pan_masked": masked_pan,
            "filing_id": j.filing_id,
            "amount": filing.amount if filing else 0.0,
            "tds_amount": filing.tds_amount if (filing and filing.tds_amount is not None) else None,
            "status": j.status,
            "current_step": j.current_step,
            "attempt_count": j.attempt_count,
            "worker_id": j.worker_id,
            "error_code": j.error_code,
            "error_message": j.error_message,
            "started_at": j.started_at.isoformat() if j.started_at else None,
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            "last_heartbeat": j.last_heartbeat.isoformat() if j.last_heartbeat else None,
            "created_at": j.created_at.isoformat() if j.created_at else None,
            "updated_at": j.updated_at.isoformat() if j.updated_at else None,
            "preview_metadata": j.preview_metadata,
            "preview_reached_at": j.preview_reached_at.isoformat() if j.preview_reached_at else None,
            "preview_screenshot_path": j.preview_screenshot_path
        })

    return {
        "total": total_count,
        "page": page,
        "limit": limit,
        "items": items
    }

@router.get("/{job_id}")
def get_job_detail(job_id: int, db: Session = Depends(get_db)):
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    customer = db.query(models.Customer).filter(models.Customer.id == job.customer_id).first()
    filing = db.query(models.Filing).filter(models.Filing.id == job.filing_id).first() if job.filing_id else None
    events = db.query(models.JobEvent).filter(models.JobEvent.job_id == job.id).order_by(models.JobEvent.created_at).all()

    raw_pan = decrypt_data(customer.pan_encrypted) if customer and customer.pan_encrypted else ""
    masked_pan = mask_pan(raw_pan)

    timeline = [
        {
            "id": ev.id,
            "event_type": ev.event_type,
            "status": ev.status,
            "message": ev.message,
            "metadata": ev.metadata_json,
            "created_at": ev.created_at.isoformat() if ev.created_at else None
        }
        for ev in events
    ]

    return {
        "id": job.id,
        "job_reference": job.job_reference,
        "customer": {
            "id": customer.id if customer else None,
            "customer_code": customer.customer_code if customer else "N/A",
            "name": customer.name if customer else "N/A",
            "pan_masked": masked_pan
        },
        "filing": {
            "id": filing.id if filing else None,
            "filing_reference": filing.filing_reference if filing else "N/A",
            "amount": filing.amount if filing else 0.0,
            "tds_amount": filing.tds_amount if (filing and filing.tds_amount is not None) else None,
            "status": filing.status if filing else "N/A"
        },
        "status": job.status,
        "current_step": job.current_step,
        "attempt_count": job.attempt_count,
        "worker_id": job.worker_id,
        "error_code": job.error_code,
        "error_message": job.error_message,
        "data_payload": {k: ("••••••••" if "password" in k.lower() else v) for k, v in (job.data_payload or {}).items()},
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "last_heartbeat": job.last_heartbeat.isoformat() if job.last_heartbeat else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "preview_metadata": job.preview_metadata,
        "preview_reached_at": job.preview_reached_at.isoformat() if job.preview_reached_at else None,
        "preview_screenshot_path": job.preview_screenshot_path,
        "timeline": timeline
    }

@router.post("/{job_id}/start")
def start_job(job_id: int, db: Session = Depends(get_db)):
    """
    Explicitly starts a single selected Form 141 filing job.
    Enforces strict single-filing concurrency lock (MAX_ACTIVE_FORM141_JOBS = 1).
    Returns HTTP 409 Conflict if another Form 141 job is currently active.
    """
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status in ACTIVE_JOB_STATUSES:
        raise HTTPException(status_code=400, detail=f"Job is already active in status '{job.status}'")


    if job.status == "COMPLETED":
        raise HTTPException(status_code=400, detail="Filing job is already COMPLETED. Cannot re-start completed filing.")

    # Concurrency check: Ensure NO other job is currently active
    other_active = (
        db.query(models.Job)
        .filter(models.Job.id != job.id, models.Job.status.in_(ACTIVE_JOB_STATUSES))
        .first()
    )


    if other_active:
        other_cust = db.query(models.Customer).filter(models.Customer.id == other_active.customer_id).first()
        raise HTTPException(
            status_code=409,
            detail={
                "error": "CONCURRENCY_LOCK_ACTIVE",
                "message": (
                    f"Cannot start filing {job.job_reference}: Another filing {other_active.job_reference} "
                    f"for {other_cust.name if other_cust else 'Unknown'} is currently in status '{other_active.status}'. "
                    f"Form 141 requires strict single-filing concurrency (MAX_ACTIVE_FORM141_JOBS = 1). "
                    f"Please complete or cancel the active filing first."
                ),
                "active_job": {
                    "id": other_active.id,
                    "job_reference": other_active.job_reference,
                    "status": other_active.status,
                    "customer_name": other_cust.name if other_cust else "N/A"
                }
            }
        )

    # Transition job to QUEUED and push ONLY this job to Redis queue
    prev_status = job.status
    job.status = "QUEUED"
    job.current_step = "QUEUED"
    job.error_code = None
    job.error_message = None

    event = models.JobEvent(
        job_id=job.id,
        event_type="JOB_STARTED",
        status="QUEUED",
        message=f"Job explicitly started by user (Previous status: {prev_status})"
    )
    db.add(event)

    audit = models.AuditLog(
        action="JOB_STARTED",
        entity_type="JOB",
        entity_id=job.job_reference,
        metadata_json={"previous_status": prev_status}
    )
    db.add(audit)
    db.commit()

    # Enqueue ONLY this job to Redis queue
    try:
        queue_manager.enqueue_job(job.id)
    except Exception as eq_err:
        pass

    publish_ws_event("JOB_STATUS_CHANGED", job.job_reference, "QUEUED", f"Job {job.job_reference} queued for processing.")

    return {
        "success": True,
        "message": f"Filing {job.job_reference} started successfully.",
        "job_id": job.id,
        "status": "QUEUED"
    }

@router.post("/{job_id}/retry")
def retry_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status == "PROCESSING":
        raise HTTPException(status_code=400, detail="Cannot retry a job that is currently processing")

    if job.status in ["PAYMENT_PENDING", "PREVIEW_PENDING"]:
        session_meta = session_service.get_session_metadata(job.id)
        if session_meta and session_meta.get("session_available"):
            # Close session cleanly on retry
            try:
                session_service.close_session(job.id)
            except Exception:
                pass

    job.status = "QUEUED"
    job.current_step = "REQUEUED"
    job.attempt_count += 1
    job.error_code = None
    job.error_message = None
    
    event = models.JobEvent(
        job_id=job.id,
        event_type="JOB_RETRIED",
        status="QUEUED",
        message=f"Job queued for retry (Attempt {job.attempt_count})"
    )
    db.add(event)

    audit = models.AuditLog(
        action="JOB_RETRIED",
        entity_type="JOB",
        entity_id=job.job_reference,
        metadata_json={"attempt_count": job.attempt_count}
    )
    db.add(audit)
    db.commit()

    # Push to Redis queue
    queue_manager.enqueue_job(job.id)
    publish_ws_event("JOB_STATUS_CHANGED", job.job_reference, "QUEUED", f"Job queued for retry (Attempt {job.attempt_count})")

    return {"message": "Job queued for retry", "attempt_count": job.attempt_count}

@router.post("/{job_id}/cancel")
def cancel_job(job_id: int, reason: Optional[str] = Body(None, embed=True), db: Session = Depends(get_db)):
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status in ["COMPLETED", "CANCELLED"]:
        raise HTTPException(status_code=400, detail=f"Job is already {job.status}")

    prev_status = job.status
    job.status = "CANCELLED"
    job.current_step = "CANCELLED"
    job.error_message = reason or "Cancelled by user"

    event = models.JobEvent(
        job_id=job.id,
        event_type="JOB_CANCELLED",
        status="CANCELLED",
        message=f"Job cancelled: {job.error_message}"
    )
    db.add(event)

    audit = models.AuditLog(
        action="JOB_CANCELLED",
        entity_type="JOB",
        entity_id=job.job_reference,
        metadata_json={"previous_status": prev_status, "reason": job.error_message}
    )
    db.add(audit)
    db.commit()

    # Clean up browser session if one was active
    session_service.close_session(job.id)

    publish_ws_event("JOB_STATUS_CHANGED", job.job_reference, "CANCELLED", f"Job cancelled: {job.error_message}")
    return {"message": "Job successfully cancelled"}

@router.post("/{job_id}/preview/authorize")
def authorize_preview_payment(job_id: int, db: Session = Depends(get_db)):
    """
    Employee confirms that the real portal Preview and Make Payment page is correct.
    Dispatches PROCEED_TO_PAYMENT command to worker to click Pay Now on the existing session.
    Transitions state to PAYMENT_AUTHORIZED, then worker sets PAYMENT_PENDING when bank page loads.
    """
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != "PREVIEW_PENDING":
        raise HTTPException(
            status_code=400,
            detail=f"Job is in '{job.status}' status, not 'PREVIEW_PENDING'. Cannot authorize payment."
        )

    # Dispatch correlated PROCEED_TO_PAYMENT command to worker
    res = session_service.proceed_to_payment(job.id)
    if not res.get("success"):
        raise HTTPException(
            status_code=500,
            detail=res.get("reason", "Failed to execute Pay Now on worker session")
        )

    db.refresh(job)
    return {
        "success": True,
        "message": "Payment authorized and Pay Now executed successfully on portal session.",
        "job_id": job.id,
        "status": job.status
    }

@router.post("/{job_id}/open-session")
def open_browser_session(
    job_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Locates the existing isolated browser session belonging to this exact job,
    activates its page tab, and brings its window to the foreground on the employee's screen.
    Does not create a new login, duplicate job, or restart automation.
    Returns safe metadata only.
    """
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    allowed_statuses = [
        "PAYMENT_PENDING",
        "PREVIEW_PENDING",
        "PROCESSING",
        "MANUAL_INTERVENTION",
        "REVIEW_REQUIRED",
        "WAITING_FOR_HUMAN"
    ]
    if job.status not in allowed_statuses:
        return {
            "success": False,
            "session_available": False,
            "reason": "SESSION_UNAVAILABLE",
            "detail": f"Job is in '{job.status}' status, no active browser session is available."
        }

    # Dispatch correlated OPEN_SESSION RPC command to worker
    res = session_service.open_session(job.id)
    if not res.get("success") or not res.get("session_available"):
        return {
            "success": False,
            "session_available": False,
            "reason": res.get("reason", "SESSION_UNAVAILABLE"),
            "detail": "Browser session unavailable. The session may have been closed or the worker restarted."
        }

    customer = db.query(models.Customer).filter(models.Customer.id == job.customer_id).first()
    filing = db.query(models.Filing).filter(models.Filing.id == job.filing_id).first() if job.filing_id else None

    # Generate cryptographically signed, short-lived viewer session token bound to user and job
    viewer_token = browser_viewer_service.generate_token(job.id, user_id=current_user.id)
    viewer_url = f"/api/jobs/{job.id}/viewer?token={viewer_token}"

    return {
        "success": True,
        "session_available": True,
        "job_id": job.id,
        "job_reference": job.job_reference,
        "customer_name": customer.name if customer else "N/A",
        "filing_reference": filing.filing_reference if filing else "N/A",
        "browser_context_id": res.get("browser_context_id"),
        "page_id": res.get("page_id"),
        "url": res.get("url"),
        "title": res.get("title"),
        "viewer_url": viewer_url,
        "viewer_token": viewer_token,
        "message": f"Browser session for {job.job_reference} focused successfully."
    }

@router.get("/{job_id}/session")
def check_browser_session(job_id: int, db: Session = Depends(get_db)):
    """
    Checks if an isolated browser session is currently running for this job.
    """
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    allowed_statuses = ["PAYMENT_PENDING", "PREVIEW_PENDING", "REVIEW_REQUIRED", "WAITING_FOR_HUMAN"]
    if job.status not in allowed_statuses:
        return {"job_id": job.id, "session_available": False, "status": job.status}

    res = session_service.check_session(job.id)
    return {
        "job_id": job.id,
        "job_reference": job.job_reference,
        "session_available": res.get("session_available", False),
        "status": job.status
    }

@router.post("/{job_id}/review/confirm")
def confirm_form_review(
    job_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Employee confirms that they have visually inspected and reviewed the completed Form 141 in the browser session.
    Advances status from REVIEW_REQUIRED to PAYMENT_PENDING so that manual payment may be executed.
    """
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    review_statuses = ["REVIEW_REQUIRED", "WAITING_FOR_HUMAN", "PREVIEW_PENDING", "PAYMENT_PENDING"]
    if job.status not in review_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Job is in '{job.status}' status, review confirmation is only valid during review stage."
        )

    job.status = "PAYMENT_PENDING"
    job.current_step = "REVIEW_CONFIRMED"
    event = models.JobEvent(
        job_id=job.id,
        event_type="REVIEW_CONFIRMED",
        status="PAYMENT_PENDING",
        message="Employee confirmed visual inspection of completed Form 141. Ready for payment."
    )
    db.add(event)

    user_id = getattr(current_user, "id", None) if current_user else None

    audit = models.AuditLog(
        user_id=user_id,
        action="REVIEW_CONFIRMED",
        entity_type="JOB",
        entity_id=job.job_reference,
        metadata_json={"reviewed_at": datetime.now(timezone.utc).isoformat()}
    )
    db.add(audit)
    db.commit()

    publish_ws_event("REVIEW_CONFIRMED", job.job_reference, "PAYMENT_PENDING", "Form 141 review confirmed. Ready for payment.")
    publish_ws_event("JOB_STATUS_CHANGED", job.job_reference, "PAYMENT_PENDING", "Form 141 review confirmed by employee. Awaiting payment.")
    return {"success": True, "message": "Form 141 review confirmed. You may now proceed with manual payment."}

@router.post("/{job_id}/payment/confirm")
def confirm_payment(
    job_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Employee completes payment manually and confirms via dashboard.
    Transitions state to COMPLETED and signals worker to cleanly close browser session.
    """
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status not in ["PAYMENT_PENDING", "PREVIEW_PENDING", "REVIEW_REQUIRED", "WAITING_FOR_HUMAN"]:
        raise HTTPException(status_code=400, detail=f"Job is in '{job.status}' status, not in a review/payment pending state")

    job.status = "COMPLETED"
    job.current_step = "PAYMENT_CONFIRMED"
    job.completed_at = datetime.now(timezone.utc)


    # Update filing if present
    if job.filing_id:
        filing = db.query(models.Filing).filter(models.Filing.id == job.filing_id).first()
        if filing:
            filing.status = "COMPLETED"
            filing.completed_at = datetime.now(timezone.utc)

    event = models.JobEvent(
        job_id=job.id,
        event_type="PAYMENT_CONFIRMED",
        status="COMPLETED",
        message="Employee confirmed payment completion. Automation finalizing."
    )
    db.add(event)

    user_id = getattr(current_user, "id", None) if current_user else None

    audit = models.AuditLog(
        user_id=user_id,
        action="PAYMENT_CONFIRMED",
        entity_type="JOB",
        entity_id=job.job_reference,
        metadata_json={"completed_at": job.completed_at.isoformat()}
    )
    db.add(audit)
    db.commit()

    # Clean up browser session via correlated worker command
    session_service.close_session(job.id)

    # Notify worker and UI via Redis event
    publish_ws_event("PAYMENT_CONFIRMED", job.job_reference, "COMPLETED", "Payment confirmed by employee.")
    publish_ws_event("JOB_STATUS_CHANGED", job.job_reference, "COMPLETED", "Payment confirmed. Filing completed.")
    return {"message": "Payment confirmed and job marked COMPLETED"}

@router.post("/{job_id}/payment/complete")
def complete_payment(
    job_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Alias for confirm_payment: Employee confirms payment completion.
    Marks job COMPLETED, closes isolated browser session, and releases single-filing lock.
    """
    return confirm_payment(job_id=job_id, current_user=current_user, db=db)

@router.post("/{job_id}/payment/cancel")
def cancel_payment(job_id: int, reason: Optional[str] = Body(None, embed=True), db: Session = Depends(get_db)):
    """
    Employee cancels or rejects payment during PAYMENT_PENDING or PREVIEW_PENDING.
    Marks job CANCELLED, closes browser session, and releases single-filing lock.
    """
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status not in ["PAYMENT_PENDING", "PREVIEW_PENDING", "MANUAL_INTERVENTION", "REVIEW_REQUIRED", "WAITING_FOR_HUMAN"]:
        raise HTTPException(status_code=400, detail=f"Job is in '{job.status}', not in a pending payment or review state")

    job.status = "CANCELLED"
    job.current_step = "PAYMENT_CANCELLED"
    job.error_message = reason or "Payment cancelled by employee"

    event = models.JobEvent(
        job_id=job.id,
        event_type="PAYMENT_CANCELLED",
        status="CANCELLED",
        message=f"Payment cancelled by employee: {job.error_message}"
    )
    db.add(event)

    audit = models.AuditLog(
        action="PAYMENT_CANCELLED",
        entity_type="JOB",
        entity_id=job.job_reference,
        metadata_json={"reason": job.error_message}
    )
    db.add(audit)
    db.commit()

    # Clean up browser session
    session_service.close_session(job.id)

    publish_ws_event("JOB_STATUS_CHANGED", job.job_reference, "CANCELLED", f"Payment cancelled: {job.error_message}")
    return {"message": "Payment cancelled and browser session closed"}

@router.post("/{job_id}/payment/problem")
def report_payment_problem(
    job_id: int, 
    problem_type: str = Body("PAYMENT_FAILED", embed=True),
    details: Optional[str] = Body(None, embed=True),
    db: Session = Depends(get_db)
):
    """
    Employee reports payment failure or manual intervention requirement.
    """
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status not in ["PAYMENT_PENDING", "PREVIEW_PENDING", "REVIEW_REQUIRED", "WAITING_FOR_HUMAN", "MANUAL_INTERVENTION"]:
        raise HTTPException(status_code=400, detail=f"Job is in '{job.status}', not in review or payment pending state")

    status = "MANUAL_INTERVENTION" if problem_type == "MANUAL_INTERVENTION" else "FAILED"
    job.status = status
    job.current_step = f"PAYMENT_PROBLEM_{problem_type}"
    job.error_code = problem_type
    job.error_message = details or f"Payment problem: {problem_type}"

    event = models.JobEvent(
        job_id=job.id,
        event_type="PAYMENT_PROBLEM",
        status=status,
        message=f"Employee reported problem: {job.error_message}"
    )
    db.add(event)

    audit = models.AuditLog(
        action="PAYMENT_PROBLEM_REPORTED",
        entity_type="JOB",
        entity_id=job.job_reference,
        metadata_json={"problem_type": problem_type, "details": details}
    )
    db.add(audit)
    db.commit()

    # Clean up browser session
    session_service.close_session(job.id)

    publish_ws_event("JOB_STATUS_CHANGED", job.job_reference, status, f"Payment problem: {job.error_message}")
    return {"message": f"Payment problem recorded as {status}"}

@router.delete("/{job_id}")
def delete_job_history(job_id: int, db: Session = Depends(get_db)):
    """
    Deletes an execution job from history by job_id.
    Blocks deletion if the job is actively running or queued.
    Does NOT trigger a browser, worker, Redis task, retry, or portal action.
    """
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status in ACTIVE_JOB_STATUSES:
        raise HTTPException(status_code=400, detail="Cannot delete an active or running job.")


    # Disassociate from logical filing if linked
    db.query(models.Form141LogicalFiling).filter(models.Form141LogicalFiling.job_id == job.id).update({
        models.Form141LogicalFiling.job_id: None
    })

    # Disassociate from worker if referenced
    db.query(models.Worker).filter(models.Worker.current_job_id == job.id).update({
        models.Worker.current_job_id: None
    })

    # Delete job events
    db.query(models.JobEvent).filter(models.JobEvent.job_id == job.id).delete()

    ref = job.job_reference
    db.delete(job)

    audit = models.AuditLog(
        action="DELETE_JOB_HISTORY",
        entity_type="JOB",
        entity_id=ref,
        metadata_json={"job_id": job_id}
    )
    db.add(audit)
    db.commit()

    return {
        "success": True,
        "message": f"Job #{job_id} deleted successfully.",
        "job_id": job_id
    }
