import asyncio
import logging
import uuid
import os
import json
from datetime import datetime, timezone
from redis.asyncio import Redis as AsyncRedis

from apps.worker.browser.manager import BrowserManager
from apps.worker.workflows.job_workflow import process_job
from apps.worker.queue.manager import worker_queue
from apps.backend.app.database.config import SessionLocal
from apps.backend.app.database import models
from apps.backend.app.database.models import Job
from apps.backend.app.auth.encryption import decrypt_data
from apps.worker.portal.adapter import (
    PortalAuthFailedException,
    AuthInterventionRequiredException,
    BrowserClosedException,
    mask_pan,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

worker_id = f"WORKER-{uuid.uuid4().hex[:6].upper()}"
worker_state = {
    "status": "ONLINE",
    "current_job_id": None
}

HEADLESS = os.getenv("BROWSER_HEADLESS", "false").lower() == "true"
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

async def heartbeat_task():
    """Reports worker heartbeat every 5 seconds."""
    while True:
        db = SessionLocal()
        try:
            worker = db.query(models.Worker).filter(models.Worker.worker_id == worker_id).first()
            if not worker:
                worker = models.Worker(
                    worker_id=worker_id, 
                    hostname=os.getenv("COMPUTERNAME", "local-machine"), 
                    status=worker_state["status"]
                )
                db.add(worker)
            
            worker.status = worker_state["status"]
            worker.current_job_id = worker_state["current_job_id"]
            worker.last_heartbeat = datetime.now(timezone.utc)
            db.commit()
        except Exception as e:
            logger.debug(f"Heartbeat note: {e}")
        finally:
            db.close()
        await asyncio.sleep(5)

async def redis_command_listener(browser_manager: BrowserManager):
    """
    Listens for correlated browser session commands from backend over Redis PubSub.
    Dispatches to BrowserManager and replies to a unique, request-specific Redis response list.
    """
    logger.info("Starting Redis browser session command listener on channel 'form141:browser:commands'...")
    while True:
        try:
            r = AsyncRedis.from_url(REDIS_URL, decode_responses=True)
            pubsub = r.pubsub()
            await pubsub.subscribe("form141:browser:commands")
            logger.info("Subscribed to form141:browser:commands")

            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                try:
                    payload = json.loads(message["data"])
                    request_id = payload.get("request_id")
                    job_id = payload.get("job_id")
                    command = payload.get("command")

                    if not request_id or not job_id or not command:
                        continue

                    logger.info(f"[RPC] Handling {command} for job {job_id} (request {request_id})")

                    if command == "OPEN_SESSION":
                        res = await browser_manager.open_session(job_id)
                    elif command == "CLOSE_SESSION":
                        res = await browser_manager.close_session(job_id)
                    elif command == "CHECK_SESSION":
                        res = browser_manager.check_session(job_id)
                    elif command == "PROCEED_TO_PAYMENT":
                        sess = browser_manager.sessions.get(job_id)
                        if not sess or not sess.get("page") or sess["page"].is_closed():
                            res = {"success": False, "session_available": False, "reason": "SESSION_UNAVAILABLE"}
                        else:
                            page = sess["page"]
                            db_rpc = SessionLocal()
                            try:
                                rpc_job = db_rpc.query(Job).filter(Job.id == job_id).first()
                                if rpc_job:
                                    rpc_job.status = "PAYMENT_AUTHORIZED"
                                    rpc_job.current_step = "PAYMENT_AUTHORIZED"
                                    db_rpc.commit()
                                
                                from apps.worker.portal.adapter import PortalAdapter
                                portal = PortalAdapter(sess["context"])
                                portal.page = page
                                await portal.click_pay_now()

                                if rpc_job:
                                    rpc_job.status = "PAYMENT_PENDING"
                                    rpc_job.current_step = "PAYMENT_PENDING"
                                    event = models.JobEvent(
                                        job_id=rpc_job.id,
                                        event_type="PAYMENT_PENDING",
                                        status="PAYMENT_PENDING",
                                        message="Pay Now clicked. Real payment page open. Awaiting employee payment."
                                    )
                                    db_rpc.add(event)
                                    db_rpc.commit()

                                sess["state"] = "PAYMENT_PENDING"
                                res = {
                                    "success": True,
                                    "session_available": True,
                                    "browser_context_id": sess.get("browser_context_id"),
                                    "page_id": sess.get("page_id"),
                                    "job_reference": sess.get("job_reference")
                                }
                            except Exception as pe:
                                logger.error(f"Error executing Pay Now for job {job_id}: {pe}", exc_info=True)
                                res = {"success": False, "session_available": True, "reason": str(pe)}
                            finally:
                                db_rpc.close()
                    else:
                        res = {"success": False, "session_available": False, "reason": "UNKNOWN_COMMAND"}

                    reply = {
                        "request_id": request_id,
                        "job_id": job_id,
                        "command": command,
                        "success": res.get("success", False),
                        "session_available": res.get("session_available", False),
                        "reason": res.get("reason"),
                        "browser_context_id": res.get("browser_context_id"),
                        "page_id": res.get("page_id"),
                        "job_reference": res.get("job_reference"),
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }

                    resp_key = f"form141:browser:response:{request_id}"
                    await r.rpush(resp_key, json.dumps(reply))
                    await r.expire(resp_key, 30)
                    logger.info(f"[RPC] Sent response for {command} (job {job_id}, success={reply['success']})")
                except Exception as ex:
                    logger.error(f"Error processing browser command: {ex}", exc_info=True)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.debug(f"Redis command listener reconnecting: {e}")
            await asyncio.sleep(3)

async def run_worker():
    logger.info(f"Starting Form 141 Automation Worker [{worker_id}]...")
    
    # Keep persistent references to prevent garbage collection of pending coroutines
    _bg_tasks = []
    _bg_tasks.append(asyncio.create_task(heartbeat_task()))
    
    browser_manager = BrowserManager(headless=HEADLESS)
    await browser_manager.start()

    # Start correlated Redis command listener for session interaction
    _bg_tasks.append(asyncio.create_task(redis_command_listener(browser_manager)))
    
    try:
        while True:
            # 1. Check if queue is paused
            if worker_queue.is_paused():
                worker_state["status"] = "PAUSED"
                await asyncio.sleep(2)
                continue

            worker_state["status"] = "ONLINE"
            worker_state["current_job_id"] = None

            # 2. Strict single-filing concurrency check (MAX_ACTIVE_FORM141_JOBS = 1)
            # If any job is already in PROCESSING, PREVIEW_PENDING, or PAYMENT_PENDING, wait until it completes or is cancelled
            db_check = SessionLocal()
            try:
                active_job = db_check.query(Job).filter(
                    Job.status.in_(["PROCESSING", "PREVIEW_PENDING", "PAYMENT_PENDING", "MANUAL_INTERVENTION"])
                ).first()
                if active_job:
                    # Concurrency lock engaged: wait for the active filing session to conclude
                    await asyncio.sleep(2)
                    continue
            except Exception as lock_err:
                logger.debug(f"Concurrency lock check note: {lock_err}")
            finally:
                db_check.close()

            # 3. Claim next queued job
            job_id = worker_queue.claim_job()
            if not job_id:
                await asyncio.sleep(1)
                continue

            worker_state["status"] = "PROCESSING"
            worker_state["current_job_id"] = job_id

            db = SessionLocal()
            context = None
            session_handoff = False
            try:
                job = db.query(Job).filter(Job.id == job_id).first()
                if not job:
                    logger.error(f"Job {job_id} not found in database!")
                    worker_queue.complete_job(job_id)
                    continue

                # Don't re-process completed or cancelled jobs
                if job.status in ["COMPLETED", "CANCELLED"]:
                    worker_queue.complete_job(job_id)
                    continue

                logger.info(f"[WORKER] Claimed {job.job_reference} (ID: {job_id})")
                prev_st = job.status

                # Mark as processing
                job.status = "PROCESSING"
                job.current_step = "AUTOMATING"
                job.worker_id = worker_id
                job.started_at = datetime.now(timezone.utc)
                job.last_heartbeat = datetime.now(timezone.utc)
                db.commit()

                logger.info(f"[WORKER] {job.job_reference} status {prev_st} -> PROCESSING")
                logger.info(f"Processing job {job.job_reference} for client {job.customer_id}")

                # Build job data payload
                data_payload = job.data_payload or {}
                job_data = {
                    "job_id": job.id,
                    "job_reference": job.job_reference,
                    "customer_id": job.customer_id,
                    "filing_id": job.filing_id,
                    "logical_filing_id": job.logical_filing_id,
                    "data_payload": data_payload
                }

                # Check for Form 141 multi-customer login credentials in payload
                if data_payload.get("_loginPan"):
                    job_data["portal_user_id"] = data_payload["_loginPan"]
                    logger.info(f"Using Form 141 login PAN from data payload")
                else:
                    customer = db.query(models.Customer).filter(models.Customer.id == job.customer_id).first()
                    if customer and customer.pan_encrypted:
                        job_data["portal_user_id"] = decrypt_data(customer.pan_encrypted)

                if data_payload.get("_loginPassword"):
                    try:
                        job_data["portal_password"] = decrypt_data(data_payload["_loginPassword"])
                    except Exception:
                        job_data["portal_password"] = data_payload["_loginPassword"]
                    logger.info(f"Using Form 141 login password from data payload")

                # Execute browser automation until human challenge or payment gateway is reached
                context = await process_job(
                    job_data=job_data,
                    browser_manager=browser_manager
                )

                page = getattr(context, "_active_page", None) or (context.pages[0] if context.pages else None)
                handoff_state = getattr(context, "_handoff_state", "PAYMENT_PENDING")

                if handoff_state == "MANUAL_INTERVENTION":
                    job.status = "MANUAL_INTERVENTION"
                    job.current_step = "AWAITING_AUTH_ASSISTANCE"
                    job.error_code = "AUTH_INTERVENTION_REQUIRED"
                    job.error_message = getattr(context, "_intervention_reason", "Human assistance required on portal")
                    if job.logical_filing_id:
                        db.query(models.Form141LogicalFiling).filter(
                            models.Form141LogicalFiling.logical_filing_id == job.logical_filing_id
                        ).update({"status": "MANUAL_INTERVENTION", "current_step": "AWAITING_AUTH_ASSISTANCE", "updated_at": datetime.now(timezone.utc)})
                    event = models.JobEvent(
                        job_id=job.id,
                        event_type="AUTH_INTERVENTION_REQUIRED",
                        status="MANUAL_INTERVENTION",
                        message=job.error_message
                    )
                    db.add(event)
                    db.commit()

                    session_info = await browser_manager.register_session(
                        job_id=job.id,
                        job_reference=job.job_reference,
                        customer_id=job.customer_id,
                        filing_id=job.filing_id,
                        context=context,
                        page=page,
                        state="MANUAL_INTERVENTION"
                    )
                    session_handoff = True

                    logger.info(f"[{job.job_reference}] MANUAL_INTERVENTION: Browser session preserved ({session_info['browser_context_id']})")
                    worker_queue.complete_job(job_id)
                    worker_state["status"] = "ONLINE"
                    worker_state["current_job_id"] = None

                elif handoff_state == "PREVIEW_PENDING":
                    job.status = "PREVIEW_PENDING"
                    job.current_step = "FORM_141_PREVIEW"
                    job.error_code = None
                    job.error_message = None
                    preview_meta = getattr(context, "_preview_metadata", {})
                    job.preview_metadata = preview_meta
                    job.preview_reached_at = datetime.now(timezone.utc)
                    job.preview_screenshot_path = preview_meta.get("preview_screenshot_path")
                    if job.logical_filing_id:
                        db.query(models.Form141LogicalFiling).filter(
                            models.Form141LogicalFiling.logical_filing_id == job.logical_filing_id
                        ).update({"status": "PREVIEW_PENDING", "current_step": "FORM_141_PREVIEW", "updated_at": datetime.now(timezone.utc)})
                    event = models.JobEvent(
                        job_id=job.id,
                        event_type="PREVIEW_PENDING",
                        status="PREVIEW_PENDING",
                        message="Form 141 preview reached. Automation halted. Awaiting employee review & authorization.",
                        metadata_json=preview_meta
                    )
                    db.add(event)
                    db.commit()

                    session_info = await browser_manager.register_session(
                        job_id=job.id,
                        job_reference=job.job_reference,
                        customer_id=job.customer_id,
                        filing_id=job.filing_id,
                        context=context,
                        page=page,
                        state="PREVIEW_PENDING"
                    )
                    session_handoff = True

                    logger.info(f"[{job.job_reference}] PREVIEW_PENDING: Browser session preserved for review ({session_info['browser_context_id']})")
                    logger.info(f"[{job.job_reference}] Automation worker released queue slot")
                    worker_queue.complete_job(job_id)
                    worker_state["status"] = "ONLINE"
                    worker_state["current_job_id"] = None

                else:
                    job.status = "PAYMENT_PENDING"
                    job.current_step = "PAYMENT_PENDING"
                    job.error_code = None
                    job.error_message = None
                    if job.logical_filing_id:
                        db.query(models.Form141LogicalFiling).filter(
                            models.Form141LogicalFiling.logical_filing_id == job.logical_filing_id
                        ).update({"status": "PAYMENT_PENDING", "current_step": "PAYMENT_PENDING", "updated_at": datetime.now(timezone.utc)})
                    event = models.JobEvent(
                        job_id=job.id,
                        event_type="PAYMENT_PENDING",
                        status="PAYMENT_PENDING",
                        message="Payment gateway reached. Automation halted. Browser preserved for employee review & payment."
                    )
                    db.add(event)
                    db.commit()

                    session_info = await browser_manager.register_session(
                        job_id=job.id,
                        job_reference=job.job_reference,
                        customer_id=job.customer_id,
                        filing_id=job.filing_id,
                        context=context,
                        page=page,
                        state="PAYMENT_PENDING"
                    )
                    session_handoff = True

                    logger.info(f"[{job.job_reference}] PAYMENT_PENDING: Browser session preserved ({session_info['browser_context_id']})")
                    worker_queue.complete_job(job_id)
                    worker_state["status"] = "ONLINE"
                    worker_state["current_job_id"] = None

            except BrowserClosedException as bce:
                logger.warning(f"Browser session closed by user for job {job_id}: {bce}")
                try:
                    job = db.query(Job).filter(Job.id == job_id).first()
                    if job:
                        job.status = "CANCELLED"
                        job.current_step = "SESSION_LOST"
                        job.error_code = "BROWSER_SESSION_CLOSED"
                        job.error_message = "Automation stopped because the browser session was closed by the user. No further portal actions were performed."
                        job.completed_at = datetime.now(timezone.utc)
                        if job.logical_filing_id:
                            db.query(models.Form141LogicalFiling).filter(
                                models.Form141LogicalFiling.logical_filing_id == job.logical_filing_id
                            ).update({"status": "CANCELLED", "current_step": "SESSION_LOST", "updated_at": datetime.now(timezone.utc)})
                        event = models.JobEvent(
                            job_id=job.id,
                            event_type="SESSION_LOST",
                            status="CANCELLED",
                            message="Automation stopped because the browser session was closed by the user. No further portal actions were performed."
                        )
                        db.add(event)
                        db.commit()
                except Exception as dbe:
                    logger.error(f"Error updating job status for browser closure: {dbe}")
            except PortalAuthFailedException as pafe:
                logger.warning(f"Authentication failure for job {job_id}: {pafe}")
                try:
                    job = db.query(Job).filter(Job.id == job_id).first()
                    if job:
                        job.status = "FAILED"
                        job.current_step = "AUTHENTICATION_FAILED"
                        job.error_code = "PORTAL_AUTH_FAILED"
                        job.error_message = str(pafe)
                        if job.logical_filing_id:
                            db.query(models.Form141LogicalFiling).filter(
                                models.Form141LogicalFiling.logical_filing_id == job.logical_filing_id
                            ).update({"status": "FAILED", "current_step": "AUTHENTICATION_FAILED", "updated_at": datetime.now(timezone.utc)})
                        event = models.JobEvent(
                            job_id=job.id,
                            event_type="PORTAL_AUTH_FAILED",
                            status="FAILED",
                            message=str(pafe)
                        )
                        db.add(event)
                        db.commit()
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Error executing job {job_id}: {e}", exc_info=True)
                try:
                    job = db.query(Job).filter(Job.id == job_id).first()
                    if job:
                        job.status = "FAILED"
                        job.current_step = "FAILED"
                        job.error_code = "AUTOMATION_ERROR"
                        job.error_message = str(e)
                        if job.logical_filing_id:
                            db.query(models.Form141LogicalFiling).filter(
                                models.Form141LogicalFiling.logical_filing_id == job.logical_filing_id
                            ).update({"status": "FAILED", "current_step": "FAILED", "updated_at": datetime.now(timezone.utc)})
                        event = models.JobEvent(
                            job_id=job.id,
                            event_type="JOB_ERROR",
                            status="FAILED",
                            message=f"Error: {str(e)}"
                        )
                        db.add(event)
                        db.commit()
                except Exception:
                    pass
            finally:
                if not session_handoff and context:
                    try:
                        await context.close()
                        logger.info(f"Closed browser context for failed/cancelled job {job_id}.")
                    except Exception:
                        pass
                if not session_handoff:
                    worker_queue.complete_job(job_id)
                    worker_state["status"] = "ONLINE"
                    worker_state["current_job_id"] = None
                db.close()
                
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Worker termination requested.")
    finally:
        await browser_manager.stop()
        logger.info(f"Worker {worker_id} safely stopped.")

if __name__ == "__main__":
    asyncio.run(run_worker())
