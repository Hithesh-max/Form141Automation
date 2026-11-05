import asyncio
import logging
from datetime import datetime, timezone, timedelta
from apps.backend.app.database.config import SessionLocal
from apps.backend.app.database.models import Job, Worker, AuditLog
from apps.worker.queue.manager import worker_queue

logger = logging.getLogger(__name__)

def run_single_recovery_check(db):
    """Executes one pass of stale worker detection and orphaned Redis queue reconciliation."""
    # 1. Find workers that haven't sent a heartbeat in 30 seconds
    stale_threshold = datetime.now(timezone.utc) - timedelta(seconds=30)
    stale_workers = db.query(Worker).filter(
        Worker.status == "ONLINE",
        Worker.last_heartbeat < stale_threshold
    ).all()
    
    for worker in stale_workers:
        logger.warning(f"Worker {worker.worker_id} is stale. Marking OFFLINE.")
        worker.status = "OFFLINE"
        
        stale_jobs = db.query(Job).filter(
            Job.status == "PROCESSING"
        ).all()
        
        for job in stale_jobs:
            logger.warning(f"Recovering stale job {job.job_reference}")
            job.status = "QUEUED"
            job.attempt_count += 1
            worker_queue.enqueue_job(job.id)
            
    # 2. Check active items in Redis processing queue for orphaned IDs
    try:
        processing_ids = worker_queue.redis_client.lrange(worker_queue.processing_queue, 0, -1)
        for jid_str in processing_ids:
            try:
                jid = int(jid_str)
            except ValueError:
                worker_queue.redis_client.lrem(worker_queue.processing_queue, 0, jid_str)
                continue

            job_record = db.query(Job).filter(Job.id == jid).first()
            if not job_record:
                logger.warning(f"Orphaned Redis processing job ID {jid} has no DB record. Evicting and auditing.")
                worker_queue.complete_job(jid)
                audit = AuditLog(
                    action="RECOVER_ORPHANED_REDIS_JOB",
                    entity_type="QUEUE",
                    entity_id=str(jid),
                    metadata_json={
                        "reason": "Job ID exists in Redis processing queue but does not exist in database",
                        "recovered_at": datetime.now(timezone.utc).isoformat()
                    }
                )
                db.add(audit)
            elif job_record.status in ["COMPLETED", "CANCELLED", "FAILED", "PAYMENT_PENDING", "MANUAL_INTERVENTION"]:
                logger.info(f"Redis processing job ID {jid} already in terminal/handoff state '{job_record.status}'. Evicting from processing queue.")
                worker_queue.complete_job(jid)
    except Exception as q_err:
        logger.debug(f"Redis queue recovery note: {q_err}")

    db.commit()

async def recovery_task():
    """Periodically checks for stale jobs (worker crashed)."""
    while True:
        logger.info("Running recovery check for stale jobs...")
        db = SessionLocal()
        try:
            run_single_recovery_check(db)
        except Exception as e:
            logger.error(f"Recovery task failed: {e}")
        finally:
            db.close()
            
        await asyncio.sleep(60) # Run every minute

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(recovery_task())
