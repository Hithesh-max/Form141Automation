from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional

from apps.backend.app.database.config import get_db
from apps.backend.app.database import models
from apps.backend.app.auth.encryption import decrypt_data

router = APIRouter(prefix="/api/customers", tags=["Customers"])

def mask_pan(pan: Optional[str]) -> str:
    if not pan:
        return "N/A"
    clean = pan.strip().upper()
    if len(clean) == 10:
        return f"{clean[:5]}****{clean[-1]}"
    return f"{clean[:2]}****" if len(clean) > 4 else "****"

@router.get("/")
def list_customers(
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    query = db.query(models.Customer)
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            (models.Customer.customer_code.ilike(pattern)) |
            (models.Customer.name.ilike(pattern))
        )
    
    total = query.count()
    customers = query.order_by(desc(models.Customer.created_at)).offset((page - 1) * limit).limit(limit).all()

    items = []
    for c in customers:
        raw_pan = decrypt_data(c.pan_encrypted) if c.pan_encrypted else ""
        filings_count = db.query(models.Filing).filter(models.Filing.customer_id == c.id).count()
        latest_job = (
            db.query(models.Job)
            .filter(models.Job.customer_id == c.id)
            .order_by(desc(models.Job.created_at))
            .first()
        )
        
        items.append({
            "id": c.id,
            "customer_code": c.customer_code,
            "name": c.name,
            "pan_masked": mask_pan(raw_pan),
            "filings_count": filings_count,
            "latest_job_id": latest_job.id if latest_job else None,
            "latest_status": latest_job.status if latest_job else "NONE",
            "created_at": c.created_at.isoformat() if c.created_at else None
        })

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "items": items
    }

@router.get("/{customer_id}")
def get_customer_detail(customer_id: int, db: Session = Depends(get_db)):
    customer = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    raw_pan = decrypt_data(customer.pan_encrypted) if customer.pan_encrypted else ""
    filings = db.query(models.Filing).filter(models.Filing.customer_id == customer.id).order_by(desc(models.Filing.created_at)).all()
    jobs = db.query(models.Job).filter(models.Job.customer_id == customer.id).order_by(desc(models.Job.created_at)).all()

    return {
        "id": customer.id,
        "customer_code": customer.customer_code,
        "name": customer.name,
        "pan_masked": mask_pan(raw_pan),
        "created_at": customer.created_at.isoformat() if customer.created_at else None,
        "filings": [
            {
                "id": f.id,
                "filing_reference": f.filing_reference,
                "amount": f.amount,
                "tds_amount": f.tds_amount,
                "status": f.status,
                "created_at": f.created_at.isoformat() if f.created_at else None,
                "completed_at": f.completed_at.isoformat() if f.completed_at else None
            }
            for f in filings
        ],
        "jobs": [
            {
                "id": j.id,
                "job_reference": j.job_reference,
                "status": j.status,
                "current_step": j.current_step,
                "attempt_count": j.attempt_count,
                "error_message": j.error_message,
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "completed_at": j.completed_at.isoformat() if j.completed_at else None
            }
            for j in jobs
        ]
    }
