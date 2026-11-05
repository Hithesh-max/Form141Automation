from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from apps.backend.app.services.queue_manager import queue_manager
from apps.backend.app.database.config import get_db
from apps.backend.app.database import models

router = APIRouter(prefix="/api/queue", tags=["Queue"])

@router.get("/status")
def get_queue_status():
    return queue_manager.get_stats()

@router.post("/start")
def start_queue(db: Session = Depends(get_db)):
    queue_manager.start_queue()
    audit = models.AuditLog(
        action="QUEUE_STARTED",
        entity_type="QUEUE",
        entity_id="form141",
        metadata_json={"state": "RUNNING"}
    )
    db.add(audit)
    db.commit()
    return {"message": "Queue started", "status": "RUNNING"}

@router.post("/pause")
def pause_queue(db: Session = Depends(get_db)):
    queue_manager.pause_queue()
    audit = models.AuditLog(
        action="QUEUE_PAUSED",
        entity_type="QUEUE",
        entity_id="form141",
        metadata_json={"state": "PAUSED"}
    )
    db.add(audit)
    db.commit()
    return {"message": "Queue paused", "status": "PAUSED"}

@router.post("/resume")
def resume_queue(db: Session = Depends(get_db)):
    queue_manager.resume_queue()
    audit = models.AuditLog(
        action="QUEUE_RESUMED",
        entity_type="QUEUE",
        entity_id="form141",
        metadata_json={"state": "RUNNING"}
    )
    db.add(audit)
    db.commit()
    return {"message": "Queue resumed", "status": "RUNNING"}

@router.post("/stop")
def stop_queue(db: Session = Depends(get_db)):
    queue_manager.stop_queue()
    audit = models.AuditLog(
        action="QUEUE_STOPPED",
        entity_type="QUEUE",
        entity_id="form141",
        metadata_json={"state": "STOPPED"}
    )
    db.add(audit)
    db.commit()
    return {"message": "Queue stopped", "status": "STOPPED"}
