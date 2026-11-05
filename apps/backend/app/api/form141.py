from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import json
import redis
import os

from apps.backend.app.database.config import get_db
from apps.backend.app.database import models
from apps.backend.app.services.queue_manager import queue_manager
from apps.backend.app.services.session_service import session_service
from apps.backend.app.auth.encryption import decrypt_data
from apps.backend.app.api.jobs import ACTIVE_JOB_STATUSES

router = APIRouter(prefix="/api/form141", tags=["Form 141"])


REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

def mask_pan(pan: Optional[str]) -> str:
    """Masks PAN for secure display: ABCDE1234F -> ABCDE****F"""
    if not pan:
        return "N/A"
    clean = pan.strip().upper()
    if len(clean) == 10:
        return f"{clean[:5]}****{clean[-1]}"
    return f"{clean[:2]}****" if len(clean) > 4 else "****"

@router.get("/active-lock")
@router.get("/active")
def get_form141_active_lock(db: Session = Depends(get_db)):
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
        f"Only one Form 141 filing can run at a time."
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

@router.get("/imports")
def list_form141_imports(db: Session = Depends(get_db)):
    """Lists all imported Form 141 multi-customer workbooks."""
    imports = db.query(models.Form141Import).order_by(desc(models.Form141Import.created_at)).all()
    results = []
    for imp in imports:
        filing_count = db.query(models.Form141LogicalFiling).filter(models.Form141LogicalFiling.import_id == imp.id).count()
        results.append({
            "id": imp.id,
            "filename": imp.filename,
            "total_customers": imp.total_customers,
            "filing_count": filing_count,
            "status": imp.status,
            "created_at": imp.created_at.isoformat() if imp.created_at else None,
            "updated_at": imp.updated_at.isoformat() if imp.updated_at else None
        })
    return {"imports": results}

@router.get("/imports/{import_id}/filings")
def list_import_filings(import_id: int, db: Session = Depends(get_db)):
    """Lists all logical filings associated with a specific Form 141 import."""
    imp = db.query(models.Form141Import).filter(models.Form141Import.id == import_id).first()
    if not imp:
        raise HTTPException(status_code=404, detail="Form 141 import not found")

    filings = (
        db.query(models.Form141LogicalFiling)
        .filter(models.Form141LogicalFiling.import_id == import_id)
        .order_by(models.Form141LogicalFiling.column_index)
        .all()
    )

    results = []
    for lf in filings:
        job = db.query(models.Job).filter(models.Job.id == lf.job_id).first() if lf.job_id else None
        effective_status = job.status if job else lf.status
        effective_step = job.current_step if job else lf.current_step

        session_meta = session_service.get_session_metadata(job.id) if job else None
        session_available = bool(session_meta and session_meta.get("session_available", False))

        results.append({
            "id": lf.id,
            "import_id": lf.import_id,
            "logical_filing_id": lf.logical_filing_id,
            "customer_label": lf.customer_label,
            "column_index": lf.column_index,
            "deductor_pan": mask_pan(lf.deductor_pan),
            "deductee_pan": mask_pan(lf.deductee_pan),
            "amount": lf.amount,
            "tds_amount": lf.tds_amount,
            "status": effective_status,
            "current_step": effective_step,
            "validation_errors": lf.validation_errors or [],
            "validation_warnings": lf.validation_warnings or [],
            "job_id": lf.job_id,
            "job_reference": job.job_reference if job else None,
            "session_available": session_available,
            "created_at": lf.created_at.isoformat() if lf.created_at else None,
            "updated_at": lf.updated_at.isoformat() if lf.updated_at else None
        })
    return {"import_id": import_id, "filename": imp.filename, "filings": results}

@router.get("/filings")
def list_all_form141_filings(
    status: Optional[str] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search by customer label or filing ID"),
    db: Session = Depends(get_db)
):
    """
    Returns all persisted Form 141 logical filings across all imports.
    Synchronizes status and current_step with linked Job in real-time.
    Supports zero, one, or multiple historical job execution attempts per logical filing.
    """
    filings = db.query(models.Form141LogicalFiling).order_by(desc(models.Form141LogicalFiling.created_at), models.Form141LogicalFiling.column_index).all()

    # Check global active lock
    has_active_global = db.query(models.Job).filter(models.Job.status.in_(ACTIVE_JOB_STATUSES)).first() is not None


    # Fetch imports map for source filename
    import_ids = list(set(lf.import_id for lf in filings if lf.import_id))
    imports_map = {}
    if import_ids:
        imports_rows = db.query(models.Form141Import).filter(models.Form141Import.id.in_(import_ids)).all()
        imports_map = {imp.id: imp.filename for imp in imports_rows}

    results = []
    for lf in filings:
        # Query all jobs associated with this logical filing ordered by latest
        jobs_for_lf = (
            db.query(models.Job)
            .filter(models.Job.logical_filing_id == lf.logical_filing_id)
            .order_by(desc(models.Job.created_at), desc(models.Job.id))
            .all()
        )
        latest_job = jobs_for_lf[0] if jobs_for_lf else (db.query(models.Job).filter(models.Job.id == lf.job_id).first() if lf.job_id else None)
        attempt_count = len(jobs_for_lf) if jobs_for_lf else (1 if latest_job else 0)

        effective_status = latest_job.status if latest_job else (lf.status or "READY")
        effective_step = latest_job.current_step if latest_job else (lf.current_step or "NOT STARTED")

        session_meta = session_service.get_session_metadata(latest_job.id) if latest_job else None
        session_available = bool(session_meta and session_meta.get("session_available", False))

        # Can start if no active job globally and status is eligible and no blocking errors
        can_start = (not has_active_global) and (effective_status in ["READY", "FAILED", "CANCELLED", "SESSION_LOST"]) and (not lf.validation_errors)

        if status and status.upper() != "ALL" and effective_status.upper() != status.upper():
            continue

        if search:
            pat = search.lower()
            if pat not in (lf.customer_label or "").lower() and pat not in (lf.logical_filing_id or "").lower():
                continue

        source_filename = imports_map.get(lf.import_id, "Form 141 Workbook") if lf.import_id else "Form 141 Workbook"
        last_activity_dt = (latest_job.updated_at or latest_job.created_at) if latest_job else (lf.updated_at or lf.created_at)

        results.append({
            "id": lf.id,
            "import_id": lf.import_id,
            "logical_filing_id": lf.logical_filing_id,
            "customer_label": lf.customer_label,
            "customer_code": lf.customer_label,
            "form141_id": lf.logical_filing_id,
            "source_file": source_filename,
            "column_index": lf.column_index,
            "deductor_pan": mask_pan(lf.deductor_pan),
            "deductee_pan": mask_pan(lf.deductee_pan),
            "masked_pan": mask_pan(lf.deductor_pan),
            "amount": lf.amount,
            "tds_amount": lf.tds_amount,
            "status": effective_status,
            "current_step": effective_step,
            "attempt_count": attempt_count,
            "latest_job_id": latest_job.id if latest_job else None,
            "latest_job_reference": latest_job.job_reference if latest_job else None,
            "latest_job": {
                "id": latest_job.id,
                "job_id": latest_job.job_reference,
                "status": latest_job.status,
                "current_step": latest_job.current_step,
                "attempts": latest_job.attempt_count or attempt_count
            } if latest_job else None,
            "can_start": can_start,
            "session_available": session_available,
            "validation_errors": lf.validation_errors or [],
            "validation_warnings": lf.validation_warnings or [],
            "last_activity": last_activity_dt.isoformat() if last_activity_dt else None,
            "created_at": lf.created_at.isoformat() if lf.created_at else None,
            "updated_at": lf.updated_at.isoformat() if lf.updated_at else None
        })

    return {"total": len(results), "filings": results}

@router.get("/kpi-summary")
def get_form141_kpi_summary(db: Session = Depends(get_db)):
    """
    Returns aggregated KPI metrics specifically from logical Form 141 filings.
    Categories: Total Filings, Ready to Start, In Progress, Action Required, Completed, Failed/Cancelled.
    """
    filings = db.query(models.Form141LogicalFiling).all()
    total_filings = len(filings)
    ready = 0
    in_progress = 0
    action_required = 0
    completed = 0
    failed = 0
    cancelled = 0

    for lf in filings:
        latest_job = (
            db.query(models.Job)
            .filter(models.Job.logical_filing_id == lf.logical_filing_id)
            .order_by(desc(models.Job.created_at), desc(models.Job.id))
            .first()
        )
        effective_status = latest_job.status if latest_job else (lf.status or "READY")

        if effective_status in ["READY", "NOT_STARTED"]:
            ready += 1
        elif effective_status in ["QUEUED", "PROCESSING", "IN_PROGRESS", "SAVE_AS_DRAFT_PENDING", "DRAFT_SAVED"]:
            in_progress += 1
        elif effective_status in ["PREVIEW_PENDING", "PAYMENT_PENDING", "SESSION_LOST", "VALIDATION_REQUIRED"]:
            action_required += 1
        elif effective_status == "COMPLETED":
            completed += 1
        elif effective_status == "FAILED":
            failed += 1
        elif effective_status == "CANCELLED":
            cancelled += 1
        else:
            ready += 1

    return {
        "total_filings": total_filings,
        "ready": ready,
        "in_progress": in_progress,
        "action_required": action_required,
        "completed": completed,
        "failed": failed,
        "cancelled": cancelled
    }

@router.get("/filings/{filing_identifier}")
def get_form141_filing_detail(filing_identifier: str, db: Session = Depends(get_db)):
    """
    Returns full details for a logical Form 141 filing including all historical execution attempts,
    browser session availability, and field payloads for the filing details drawer.
    """
    lf = None
    if filing_identifier.isdigit():
        lf = db.query(models.Form141LogicalFiling).filter(models.Form141LogicalFiling.id == int(filing_identifier)).first()
    if not lf:
        lf = db.query(models.Form141LogicalFiling).filter(models.Form141LogicalFiling.logical_filing_id == filing_identifier).first()

    if not lf:
        raise HTTPException(status_code=404, detail=f"Form 141 filing '{filing_identifier}' not found.")

    # Import info
    source_filename = "Form 141 Workbook"
    if lf.import_id:
        imp = db.query(models.Form141Import).filter(models.Form141Import.id == lf.import_id).first()
        if imp:
            source_filename = imp.filename

    # All execution attempts ordered newest first
    jobs = (
        db.query(models.Job)
        .filter(models.Job.logical_filing_id == lf.logical_filing_id)
        .order_by(desc(models.Job.created_at), desc(models.Job.id))
        .all()
    )

    attempts = []
    for j in jobs:
        sess_meta = session_service.get_session_metadata(j.id)
        sess_avail = bool(sess_meta and sess_meta.get("session_available", False))
        attempts.append({
            "id": j.id,
            "job_reference": j.job_reference,
            "status": j.status,
            "current_step": j.current_step,
            "attempt_number": j.attempt_count or 1,
            "worker_id": j.worker_id,
            "error_code": j.error_code,
            "error_message": j.error_message,
            "session_available": sess_avail,
            "started_at": j.started_at.isoformat() if j.started_at else None,
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            "created_at": j.created_at.isoformat() if j.created_at else None,
            "updated_at": j.updated_at.isoformat() if j.updated_at else None
        })

    latest_job = attempts[0] if attempts else None
    effective_status = latest_job["status"] if latest_job else (lf.status or "READY")
    effective_step = latest_job["current_step"] if latest_job else (lf.current_step or "NOT STARTED")

    return {
        "id": lf.id,
        "import_id": lf.import_id,
        "source_file": source_filename,
        "logical_filing_id": lf.logical_filing_id,
        "customer_label": lf.customer_label,
        "column_index": lf.column_index,
        "deductor_pan": mask_pan(lf.deductor_pan),
        "deductee_pan": mask_pan(lf.deductee_pan),
        "masked_pan": mask_pan(lf.deductor_pan),
        "raw_deductor_pan": mask_pan(lf.deductor_pan),
        "amount": lf.amount,
        "tds_amount": lf.tds_amount,
        "status": effective_status,
        "current_step": effective_step,
        "total_attempts": len(attempts),
        "attempts": attempts,
        "latest_job": latest_job,
        "field_values": lf.field_values or {},
        "field_metadata": lf.field_metadata or {},
        "validation_errors": lf.validation_errors or [],
        "validation_warnings": lf.validation_warnings or [],
        "created_at": lf.created_at.isoformat() if lf.created_at else None,
        "updated_at": lf.updated_at.isoformat() if lf.updated_at else None
    }

@router.post("/filings/{filing_identifier}/start")
def start_form141_logical_filing(filing_identifier: str, db: Session = Depends(get_db)):
    """
    Starts filing automation for an individual Form 141 logical filing.
    Enforces strict single-filing concurrency limit (MAX_ACTIVE_FORM141_JOBS = 1).
    Creates a new execution Job linked to the logical filing, preserving historical attempts.
    Returns HTTP 409 Conflict if another filing job is currently active.
    """
    # 1. Lookup logical filing by logical_filing_id or integer PK id
    lf = None
    if filing_identifier.isdigit():
        lf = db.query(models.Form141LogicalFiling).filter(models.Form141LogicalFiling.id == int(filing_identifier)).first()
    if not lf:
        lf = db.query(models.Form141LogicalFiling).filter(models.Form141LogicalFiling.logical_filing_id == filing_identifier).first()

    if not lf:
        raise HTTPException(status_code=404, detail=f"Logical filing '{filing_identifier}' not found.")

    # 2. Check if any active job exists globally
    active_job = db.query(models.Job).filter(models.Job.status.in_(ACTIVE_JOB_STATUSES)).first()


    if active_job:
        active_cust = db.query(models.Customer).filter(models.Customer.id == active_job.customer_id).first()
        raise HTTPException(
            status_code=409,
            detail={
                "error": "CONCURRENCY_LOCK_ACTIVE",
                "message": (
                    f"Cannot start filing '{lf.customer_label}': Active filing {active_job.job_reference} "
                    f"for {active_cust.name if active_cust else 'Unknown'} is currently in status '{active_job.status}'. "
                    f"Form 141 requires strict single-filing concurrency (MAX_ACTIVE_FORM141_JOBS = 1). "
                    f"Please complete or cancel the active filing first."
                ),
                "active_job": {
                    "id": active_job.id,
                    "job_reference": active_job.job_reference,
                    "status": active_job.status,
                    "customer_name": active_cust.name if active_cust else "N/A"
                }
            }
        )

    # 3. Check current status and validation
    if lf.status == "INVALID":
        raise HTTPException(status_code=400, detail=f"Filing {lf.customer_label} has invalid fields and cannot be started. Please review validation errors.")

    # 4. Lookup or create Customer & Filing records for this logical filing
    from apps.backend.app.auth.encryption import encrypt_data, decrypt_data
    import uuid

    pan_to_store = lf.deductor_pan or ""
    existing_customer = None
    if pan_to_store:
        for c in db.query(models.Customer).all():
            if c.pan_encrypted:
                try:
                    if decrypt_data(c.pan_encrypted).upper() == pan_to_store.upper():
                        existing_customer = c
                        break
                except Exception:
                    pass

    if existing_customer:
        customer = existing_customer
    else:
        customer = models.Customer(
            customer_code=f"F141-{uuid.uuid4().hex[:6].upper()}",
            name=lf.customer_label,
            pan_encrypted=encrypt_data(pan_to_store) if pan_to_store else ""
        )
        db.add(customer)
        db.flush()

    filing_rec = models.Filing(
        customer_id=customer.id,
        filing_reference=f"FIL-{uuid.uuid4().hex[:8].upper()}",
        amount=lf.amount or 0.0,
        tds_amount=lf.tds_amount,
        status="IN_PROGRESS"
    )
    db.add(filing_rec)
    db.flush()

    # 5. Count previous execution attempts for this logical filing
    previous_attempts = db.query(models.Job).filter(models.Job.logical_filing_id == lf.logical_filing_id).count()

    # 6. Create exactly ONE new execution Job
    new_job = models.Job(
        job_reference=f"JOB-{filing_rec.id}-{uuid.uuid4().hex[:6].upper()}",
        logical_filing_id=lf.logical_filing_id,
        customer_id=customer.id,
        filing_id=filing_rec.id,
        status="QUEUED",
        current_step="QUEUED",
        data_payload=lf.field_values or {},
        attempt_count=previous_attempts + 1
    )
    db.add(new_job)
    db.flush()

    # 7. Update logical filing to link to new execution job
    lf.job_id = new_job.id
    lf.status = "IN_PROGRESS"
    lf.current_step = "QUEUED"
    lf.updated_at = datetime.now(timezone.utc)
    db.commit()

    # 8. Record JobEvent
    event = models.JobEvent(
        job_id=new_job.id,
        event_type="JOB_QUEUED",
        status="QUEUED",
        message=f"Form 141 logical filing {lf.logical_filing_id} ({lf.customer_label}) manually started by employee (Attempt {new_job.attempt_count})."
    )
    db.add(event)
    db.commit()

    # 9. Enqueue ONLY this job into Redis / Worker
    queue_manager.enqueue_job(new_job.id)

    # 10. Publish WS event
    try:
        r = redis.from_url(REDIS_URL, decode_responses=True)
        r.publish("form141:events", json.dumps({
            "event": "JOB_QUEUED",
            "job_id": str(new_job.id),
            "status": "QUEUED",
            "message": f"Filing {lf.customer_label} ({lf.logical_filing_id}) queued for processing.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "logical_filing_id": lf.logical_filing_id,
                "job_id": new_job.id,
                "attempt_count": new_job.attempt_count
            }
        }))
    except Exception:
        pass

    return {
        "success": True,
        "message": f"Filing {lf.customer_label} ({lf.logical_filing_id}) successfully queued (Attempt {new_job.attempt_count}).",
        "logical_filing_id": lf.logical_filing_id,
        "job_id": new_job.id,
        "job_reference": new_job.job_reference,
        "status": "QUEUED",
        "attempt_count": new_job.attempt_count
    }

@router.delete("/filings/{filing_identifier}")
def delete_form141_filing(filing_identifier: str, db: Session = Depends(get_db)):
    """
    Deletes a Form 141 logical filing by logical_filing_id (e.g. 'LF-001') or numeric ID.
    Blocks deletion if an execution job is actively running.
    Does NOT trigger a browser, worker, Redis task, retry, or portal action.
    """
    lf = None
    if filing_identifier.isdigit():
        lf = db.query(models.Form141LogicalFiling).filter(models.Form141LogicalFiling.id == int(filing_identifier)).first()
    if not lf:
        lf = db.query(models.Form141LogicalFiling).filter(models.Form141LogicalFiling.logical_filing_id == filing_identifier).first()

    if not lf:
        raise HTTPException(status_code=404, detail="Logical filing not found")

    # Check filing status directly
    if (lf.status or "").upper() in ACTIVE_JOB_STATUSES:
        raise HTTPException(status_code=400, detail="Cannot delete filing while an execution job is active or running.")

    # Check if linked to any actively running job
    active_job = db.query(models.Job).filter(
        models.Job.logical_filing_id == lf.logical_filing_id,
        models.Job.status.in_(ACTIVE_JOB_STATUSES)
    ).first()
    if active_job:
        raise HTTPException(status_code=400, detail="Cannot delete filing while an execution job is active or running.")


    lid = lf.logical_filing_id
    label = lf.customer_label

    # Unbind historical jobs from this logical filing ID so job history remains intact
    db.query(models.Job).filter(models.Job.logical_filing_id == lid).update({models.Job.logical_filing_id: None})

    db.delete(lf)

    audit = models.AuditLog(
        action="DELETE_FORM141_FILING",
        entity_type="LOGICAL_FILING",
        entity_id=lid,
        metadata_json={"customer_label": label}
    )
    db.add(audit)
    db.commit()

    return {
        "success": True,
        "message": f"Filing {lid} deleted successfully.",
        "logical_filing_id": lid
    }
