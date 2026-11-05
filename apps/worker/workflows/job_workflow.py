import logging
import asyncio
from datetime import datetime, timezone
from playwright.async_api import BrowserContext
from apps.worker.browser.manager import BrowserManager
from apps.worker.portal.adapter import (
    PortalAdapter,
    PortalAuthFailedException,
    AuthInterventionRequiredException,
    PortalStateUnexpectedException,
    BrowserClosedException,
)
from apps.worker.events.publisher import publish_event
from apps.backend.app.database import config as db_config
from apps.backend.app.database.config import SessionLocal
from apps.backend.app.database import models

logger = logging.getLogger(__name__)


def persist_job_step(job_id: int = None, step_name: str = "", message: str = "", status: str = None, error_code: str = None, error_message: str = None, job_ref: str = None, db = None):
    """Safely updates Job, Form141LogicalFiling, and creates a JobEvent in SQLite."""
    if not job_id and not job_ref:
        return
    close_db = False
    if db is None:
        db = db_config.SessionLocal()
        close_db = True
    try:
        query = db.query(models.Job)
        if job_id:
            job = query.filter(models.Job.id == job_id).first()
        else:
            job = query.filter(models.Job.job_reference == job_ref).first()

        if job:
            job.current_step = step_name
            if status:
                job.status = status
            if error_code is not None:
                job.error_code = error_code
            if error_message is not None:
                job.error_message = error_message
            job.last_heartbeat = datetime.now(timezone.utc)
            job.updated_at = datetime.now(timezone.utc)

            # Sync parent logical filing if linked
            if job.logical_filing_id:
                lf = db.query(models.Form141LogicalFiling).filter(
                    models.Form141LogicalFiling.logical_filing_id == job.logical_filing_id
                ).first()
                if lf:
                    lf.current_step = step_name
                    if status:
                        lf.status = status
                    lf.updated_at = datetime.now(timezone.utc)

            event = models.JobEvent(
                job_id=job.id,
                event_type=step_name,
                status=job.status,
                message=message
            )
            db.add(event)
            db.commit()
    except Exception as ex:
        logger.error(f"Error persisting step {step_name}: {ex}")
    finally:
        if close_db:
            db.close()


async def record_stage(job_id: int, job_ref: str, step_name: str, message: str, status: str = None, db = None):
    """Persists stage to DB and broadcasts real-time WebSocket event."""
    persist_job_step(job_id=job_id, step_name=step_name, message=message, status=status, job_ref=job_ref, db=db)
    await publish_event("JOB_STATUS_CHANGED", job_ref, step_name, message)


async def process_job(job_data: dict, browser_manager: BrowserManager) -> BrowserContext:
    """
    Official Form 141 portal flow:
      1. BROWSER_INITIALIZED (Context created, page alive, session registered)
      2. PORTAL_AUTHENTICATED (Verified dashboard after genuine login)
      3. FORM_POPULATED (Deductor Particulars + Transaction Details filled & verified)
      4. FORM_VALIDATED (Tab 2 saved, payment mode chosen, preview verified without errors)
      5. PAYMENT_PENDING (Preview reached, automation halted for human review & payment)
    """
    job_id = job_data.get("job_id")
    job_ref = job_data.get("job_reference")
    customer_id = job_data.get("customer_id")
    filing_id = job_data.get("filing_id")
    data = job_data.get("data_payload", {})
    portal_user_id = job_data.get("portal_user_id", "")
    portal_password = job_data.get("portal_password", "")

    deductee_type = (
        data.get("deducteeType")
        or data.get("deductee_type")
        or "Non-Corporate"
    )
    if deductee_type not in ("Corporate", "Non-Corporate"):
        logger.warning(f"[{job_ref}] Unknown deductee type, defaulting to Non-Corporate")
        deductee_type = "Non-Corporate"

    logger.info(f"[{job_ref}] Starting Form 141 automation. DeducteeType={deductee_type}")

    # STAGE 1: BROWSER INITIALIZATION
    try:
        context = await browser_manager.create_context()
        context._user_closed = False

        def _mark_user_closed():
            context._user_closed = True
            logger.info(f"[{job_ref}] Browser closure detected during active automation.")

        context.on("close", lambda c: _mark_user_closed())

        portal = PortalAdapter(context)
        await portal.initialize()
        portal.page.on("close", lambda p: _mark_user_closed())

        # Verify page is responsive
        is_alive = await portal.page.evaluate("() => true")
        if not is_alive or portal.page.is_closed():
            raise BrowserClosedException("Browser page was closed immediately upon launch.")

        # Register session immediately with browser_manager so Open Session works right away
        if job_id:
            await browser_manager.register_session(
                job_id=job_id,
                job_reference=job_ref,
                customer_id=customer_id,
                filing_id=filing_id,
                context=context,
                page=portal.page,
                state="PROCESSING"
            )

        # Confirm STAGE 1 completion
        await record_stage(job_id, job_ref, "BROWSER_INITIALIZED", "Chromium browser session initialized successfully.")
        logger.info(f"[{job_ref}] STAGE 1: BROWSER_INITIALIZED")
    except Exception as e:
        logger.error(f"[{job_ref}] Browser initialization failed: {e}", exc_info=True)
        persist_job_step(
            job_id, "BROWSER_INIT_FAILED", f"Browser initialization failed: {e}",
            status="FAILED", error_code="BROWSER_LAUNCH_FAILED", error_message=str(e)
        )
        await publish_event("JOB_ERROR", job_ref, "FAILED", f"Browser initialization failed: {e}")
        raise

    try:
        # STAGE 2: PORTAL AUTHENTICATION
        await record_stage(job_id, job_ref, "LOGIN_IN_PROGRESS", "Logging into Income Tax portal...")
        logger.info(f"[{job_ref}] Authenticating...")
        try:
            await portal.login(portal_user_id, portal_password)
        except AuthInterventionRequiredException as e:
            logger.info(f"[{job_ref}] Auth challenge: {e}")
            try:
                await portal.page.evaluate(
                    f"() => {{ document.title = 'Income Tax Portal - [{job_ref}] Auth Required'; }}"
                )
            except Exception:
                pass
            context._active_page = portal.page
            context._handoff_state = "MANUAL_INTERVENTION"
            context._intervention_reason = str(e)
            await record_stage(
                job_id, job_ref, "AWAITING_AUTH_ASSISTANCE",
                "Please complete portal authentication in the browser session.",
                status="MANUAL_INTERVENTION"
            )
            return context
        except PortalAuthFailedException as e:
            logger.warning(f"[{job_ref}] Auth failed / timeout: {e}. Preserving browser session for manual review.")
            try:
                await portal.page.evaluate(
                    f"() => {{ document.title = 'Income Tax Portal - [{job_ref}] Auth Failed'; }}"
                )
            except Exception:
                pass
            context._active_page = portal.page
            context._handoff_state = "MANUAL_INTERVENTION"
            context._intervention_reason = str(e)
            await record_stage(
                job_id, job_ref, "AWAITING_AUTH_ASSISTANCE",
                f"Portal authentication required manual review: {e}",
                status="MANUAL_INTERVENTION"
            )
            return context

        await record_stage(job_id, job_ref, "PORTAL_AUTHENTICATED", "Authenticated successfully with portal.")
        logger.info(f"[{job_ref}] STAGE 2: PORTAL_AUTHENTICATED")

        # STAGE 3: FORM POPULATION
        await record_stage(job_id, job_ref, "FORM_NAVIGATION", "Navigating: e-File -> e-Pay Tax -> Form 141...")
        try:
            await portal.navigate_form_141(data)
        except PortalStateUnexpectedException as e:
            persist_job_step(
                job_id, "FORM_NAVIGATION_FAILED", str(e),
                status="FAILED", error_code="NAVIGATION_FAILED", error_message=str(e)
            )
            await publish_event("JOB_STATUS_CHANGED", job_ref, "PORTAL_STATE_UNEXPECTED", str(e))
            raise

        await record_stage(job_id, job_ref, "FORM_FILLING_TAB1", "Populating Deductor particulars (Tab 1)...")
        try:
            await portal.fill_tax_applicable_details(data)
        except PortalStateUnexpectedException as e:
            persist_job_step(
                job_id, "TAB1_FILLING_FAILED", str(e),
                status="FAILED", error_code="TAB1_FAILED", error_message=str(e)
            )
            await publish_event("JOB_STATUS_CHANGED", job_ref, "PORTAL_STATE_UNEXPECTED", str(e))
            raise

        await record_stage(job_id, job_ref, "FORM_FILLING_TAB2", "Populating Form 141 Transaction details (Tab 2)...")
        await portal.fill_form_141(data)

        # Verify form population
        is_populated = await portal.verify_form_populated(data)
        if not is_populated:
            err_msg = "Form 141 fields could not be verified on the portal page."
            persist_job_step(
                job_id, "FORM_POPULATION_FAILED", err_msg,
                status="FAILED", error_code="POPULATION_FAILED", error_message=err_msg
            )
            raise PortalStateUnexpectedException(err_msg)

        await record_stage(job_id, job_ref, "FORM_POPULATED", "Form 141 fields populated and verified.")
        logger.info(f"[{job_ref}] STAGE 3: FORM_POPULATED verified.")

        # STAGE 4: FORM VALIDATION
        await record_stage(job_id, job_ref, "FORM_VALIDATING", "Validating Form 141 data with portal...")
        try:
            await portal.save_form()
        except PortalStateUnexpectedException as e:
            persist_job_step(
                job_id, "FORM_VALIDATION_FAILED", f"Save error: {e}",
                status="FAILED", error_code="VALIDATION_FAILED", error_message=str(e)
            )
            await publish_event("JOB_STATUS_CHANGED", job_ref, "PORTAL_STATE_UNEXPECTED", f"Save error: {e}")
            raise

        try:
            await portal.select_payment_mode()
        except PortalStateUnexpectedException as e:
            persist_job_step(
                job_id, "PAYMENT_MODE_FAILED", f"Payment mode error: {e}",
                status="FAILED", error_code="PAYMENT_MODE_ERROR", error_message=str(e)
            )
            await publish_event("JOB_STATUS_CHANGED", job_ref, "PORTAL_STATE_UNEXPECTED", f"Payment mode error: {e}")
            raise

        try:
            preview_metadata = await portal.navigate_to_preview()
        except PortalStateUnexpectedException as e:
            persist_job_step(
                job_id, "PREVIEW_PAGE_FAILED", f"Preview page error: {e}",
                status="FAILED", error_code="PREVIEW_ERROR", error_message=str(e)
            )
            await publish_event("JOB_STATUS_CHANGED", job_ref, "PORTAL_STATE_UNEXPECTED", f"Preview page not found: {e}")
            raise

        is_validated = await portal.verify_form_validated()
        if not is_validated:
            err_msg = "Form 141 validation check failed on portal."
            persist_job_step(
                job_id, "FORM_VALIDATION_FAILED", err_msg,
                status="FAILED", error_code="VALIDATION_CHECK_FAILED", error_message=err_msg
            )
            raise PortalStateUnexpectedException(err_msg)

        await record_stage(job_id, job_ref, "FORM_VALIDATED", "Form 141 validated successfully by portal.")
        logger.info(f"[{job_ref}] STAGE 4: FORM_VALIDATED verified.")

        # STAGE 5: PAYMENT GATEWAY HANDOFF (Preview ready, awaiting human review & payment)
        try:
            await portal.page.evaluate(
                f"() => {{ document.title = 'Income Tax Portal - [{job_ref}] FORM 141 PREVIEW'; }}"
            )
        except Exception:
            pass

        logger.info(f"[{job_ref}] STAGE 5: PREVIEW / PAYMENT GATEWAY reached. URL={portal.page.url}")
        await record_stage(
            job_id, job_ref, "REVIEW_REQUIRED",
            "Form 141 preview ready. Automation halted. Please open browser session to review Form 141 before proceeding.",
            status="REVIEW_REQUIRED"
        )
        # Also persist PAYMENT_PENDING step event for test and telemetry compatibility
        persist_job_step(
            job_id, "PAYMENT_PENDING",
            "Form 141 preview ready. Ready for human review and payment.",
            status="REVIEW_REQUIRED"
        )

        context._active_page = portal.page
        context._handoff_state = "REVIEW_REQUIRED"
        context._preview_metadata = preview_metadata
        return context

    except BrowserClosedException:
        logger.info(f"[{job_ref}] Automation stopped because the browser session was closed by the user.")
        persist_job_step(
            job_id, "SESSION_LOST",
            "Automation stopped because the browser session was closed by the user. No further portal actions were performed.",
            status="CANCELLED", error_code="BROWSER_SESSION_CLOSED"
        )
        await publish_event(
            "JOB_STATUS_CHANGED", job_ref, "SESSION_LOST",
            "Automation stopped because the browser session was closed by the user. No further portal actions were performed."
        )
        raise
    except (PortalAuthFailedException, PortalStateUnexpectedException):
        if getattr(context, "_user_closed", False):
            logger.info(f"[{job_ref}] Error occurred due to browser closure by user.")
            persist_job_step(
                job_id, "SESSION_LOST",
                "Automation stopped because the browser session was closed by the user.",
                status="CANCELLED", error_code="BROWSER_SESSION_CLOSED"
            )
            await publish_event(
                "JOB_STATUS_CHANGED", job_ref, "SESSION_LOST",
                "Automation stopped because the browser session was closed by the user."
            )
            raise BrowserClosedException("Automation stopped because the browser session was closed by the user.")
        raise
    except Exception as e:
        if getattr(context, "_user_closed", False) or "Target page, context or browser has been closed" in str(e) or "browser has been closed" in str(e):
            logger.info(f"[{job_ref}] Automation stopped: browser closed by user ({e})")
            persist_job_step(
                job_id, "SESSION_LOST",
                "Automation stopped because the browser session was closed by the user.",
                status="CANCELLED", error_code="BROWSER_SESSION_CLOSED"
            )
            await publish_event(
                "JOB_STATUS_CHANGED", job_ref, "SESSION_LOST",
                "Automation stopped because the browser session was closed by the user."
            )
            raise BrowserClosedException("Automation stopped because the browser session was closed by the user.")
        logger.error(f"[{job_ref}] Automation error: {e}", exc_info=True)
        persist_job_step(
            job_id, "FAILED", f"Automation error: {e}",
            status="FAILED", error_code="AUTOMATION_ERROR", error_message=str(e)
        )
        await publish_event("JOB_ERROR", job_ref, "FAILED", f"Error: {e}")
        try:
            await context.close()
        except Exception:
            pass
        raise


async def execute_pay_now(job_ref: str, portal: PortalAdapter) -> None:
    """
    Called ONLY after employee authorizes payment.
    Clicks the real Pay Now on the existing open preview page.
    """
    logger.info(f"[{job_ref}] PROCEED_TO_PAYMENT. Clicking Pay Now...")
    await publish_event(
        "JOB_STATUS_CHANGED", job_ref, "PAYMENT_AUTHORIZED",
        "Employee authorized payment. Clicking Pay Now..."
    )
    await portal.click_pay_now()
    logger.info(f"[{job_ref}] Pay Now clicked. URL={portal.page.url}")
    await publish_event(
        "JOB_STATUS_CHANGED", job_ref, "PAYMENT_PENDING",
        "Pay Now clicked. Real payment page open. Awaiting employee payment."
    )
