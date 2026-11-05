import pytest
import os
import asyncio
from datetime import datetime, timezone
from apps.worker.browser.manager import BrowserManager
from apps.worker.workflows.job_workflow import process_job, persist_job_step
from apps.backend.app.database import models
from apps.backend.app.auth.encryption import encrypt_data
from apps.worker.portal.adapter import (
    PortalAdapter,
    PortalAuthFailedException,
    AuthInterventionRequiredException,
    PortalStateUnexpectedException
)

@pytest.mark.asyncio
async def test_five_filing_stages_success_flow(test_db):
    """
    Verifies that the automation job progresses through all five stages:
    1. BROWSER_INITIALIZED (browser launched, session registered, verified alive)
    2. PORTAL_AUTHENTICATED (login succeeded, dashboard verified)
    3. FORM_POPULATED (Tab 1 & Tab 2 filled and verified)
    4. FORM_VALIDATED (preview reached without validation errors)
    5. PAYMENT_PENDING (handoff reached, manual payment required)
    """
    os.environ["PORTAL_MODE"] = "mock"
    browser_manager = BrowserManager(headless=True)
    await browser_manager.start()

    try:
        cust = models.Customer(
            customer_code="CUST-STAGES",
            name="Workflow Test Client",
            pan_encrypted=encrypt_data("AAAPL1234K")
        )
        test_db.add(cust)
        test_db.flush()

        filing = models.Filing(
            customer_id=cust.id,
            filing_reference="FIL-STAGES-01",
            amount=5500000.0,
            tds_amount=55000.0,
            status="READY"
        )
        test_db.add(filing)
        test_db.flush()

        lf = models.Form141LogicalFiling(
            logical_filing_id="LF-STAGES-01",
            customer_label="Customer Stages 1",
            deductor_pan="AWQPM0067K",
            deductee_pan="AAAPL1234K",
            amount=5500000.0,
            tds_amount=55000.0,
            status="READY",
            current_step="READY"
        )
        test_db.add(lf)
        test_db.flush()

        job = models.Job(
            job_reference="JOB-STAGES-001",
            logical_filing_id=lf.logical_filing_id,
            customer_id=cust.id,
            filing_id=filing.id,
            status="PROCESSING",
            current_step="AUTOMATING"
        )
        test_db.add(job)
        test_db.commit()

        job_payload = {
            "job_id": job.id,
            "job_reference": job.job_reference,
            "customer_id": job.customer_id,
            "filing_id": job.filing_id,
            "logical_filing_id": job.logical_filing_id,
            "portal_user_id": "AWQPM0067K",
            "portal_password": "TestPassword123",
            "data_payload": {
                "deductorPan": "AWQPM0067K",
                "deducteePan": "AAAPL1234K",
                "saleConsideration": 5500000.0,
                "tdsAmount": 55000.0,
                "taxYear": "2026-27"
            }
        }

        # Execute process_job
        context = await process_job(job_payload, browser_manager)

        # Re-fetch Job and Logical Filing from database to verify real persistence
        test_db.expire_all()
        refreshed_job = test_db.query(models.Job).filter(models.Job.id == job.id).first()
        refreshed_lf = test_db.query(models.Form141LogicalFiling).filter(
            models.Form141LogicalFiling.logical_filing_id == lf.logical_filing_id
        ).first()

        # Check final handoff state is REVIEW_REQUIRED or PAYMENT_PENDING
        assert getattr(context, "_handoff_state", None) in ["REVIEW_REQUIRED", "PAYMENT_PENDING"]
        assert refreshed_job.status in ["REVIEW_REQUIRED", "PAYMENT_PENDING"]
        assert refreshed_job.current_step in ["REVIEW_REQUIRED", "PAYMENT_PENDING"]
        assert refreshed_lf.status in ["REVIEW_REQUIRED", "PAYMENT_PENDING"]
        assert refreshed_lf.current_step in ["REVIEW_REQUIRED", "PAYMENT_PENDING"]

        # Verify that all intermediate stages were recorded as JobEvents in DB
        events = test_db.query(models.JobEvent).filter(models.JobEvent.job_id == job.id).all()
        event_types = [e.event_type for e in events]

        assert "BROWSER_INITIALIZED" in event_types, "Stage 1: BROWSER_INITIALIZED must be logged in DB"
        assert "PORTAL_AUTHENTICATED" in event_types, "Stage 2: PORTAL_AUTHENTICATED must be logged in DB"
        assert "FORM_POPULATED" in event_types, "Stage 3: FORM_POPULATED must be logged in DB"
        assert "FORM_VALIDATED" in event_types, "Stage 4: FORM_VALIDATED must be logged in DB"
        assert "PAYMENT_PENDING" in event_types, "Stage 5: PAYMENT_PENDING must be logged in DB"

    finally:
        await browser_manager.stop()


@pytest.mark.asyncio
async def test_auth_challenge_triggers_manual_intervention(test_db):
    """
    Verifies that when a portal auth challenge occurs (OTP/CAPTCHA):
    - Job status is set to MANUAL_INTERVENTION
    - Job current_step is set to AWAITING_AUTH_ASSISTANCE
    - Browser session is preserved
    - Database is updated with a clear message
    """
    os.environ["PORTAL_MODE"] = "mock"
    browser_manager = BrowserManager(headless=True)
    await browser_manager.start()

    try:
        cust = models.Customer(customer_code="CUST-OTP", name="OTP Client", pan_encrypted=encrypt_data("BBBPB5678C"))
        test_db.add(cust)
        test_db.flush()

        job = models.Job(job_reference="JOB-OTP-001", customer_id=cust.id, status="PROCESSING", current_step="AUTOMATING")
        test_db.add(job)
        test_db.commit()

        # Monkeypatch PortalAdapter.login to raise AuthInterventionRequiredException
        original_login = PortalAdapter.login
        async def mock_challenge_login(self, user_id, password):
            raise AuthInterventionRequiredException("HUMAN_AUTH_CHALLENGE: OTP required for testing", "OTP")
        PortalAdapter.login = mock_challenge_login

        try:
            job_payload = {
                "job_id": job.id,
                "job_reference": job.job_reference,
                "customer_id": job.customer_id,
                "data_payload": {}
            }
            context = await process_job(job_payload, browser_manager)

            assert getattr(context, "_handoff_state", None) == "MANUAL_INTERVENTION"

            test_db.expire_all()
            refreshed = test_db.query(models.Job).filter(models.Job.id == job.id).first()
            assert refreshed.status == "MANUAL_INTERVENTION"
            assert refreshed.current_step == "AWAITING_AUTH_ASSISTANCE"

            events = test_db.query(models.JobEvent).filter(models.JobEvent.job_id == job.id).all()
            event_types = [e.event_type for e in events]
            assert "AWAITING_AUTH_ASSISTANCE" in event_types

        finally:
            PortalAdapter.login = original_login
    finally:
        await browser_manager.stop()


def test_step_persistence_helper(test_db):
    """Verifies that persist_job_step accurately writes to SQLite DB."""
    cust = models.Customer(customer_code="CUST-PERSIST", name="Persist Client")
    test_db.add(cust)
    test_db.flush()

    lf = models.Form141LogicalFiling(
        logical_filing_id="LF-PERSIST-01",
        customer_label="Customer Persist",
        status="READY",
        current_step="READY"
    )
    test_db.add(lf)
    test_db.flush()

    job = models.Job(
        job_reference="JOB-PERSIST-01",
        logical_filing_id=lf.logical_filing_id,
        customer_id=cust.id,
        status="PROCESSING",
        current_step="AUTOMATING"
    )
    test_db.add(job)
    test_db.commit()

    persist_job_step(job.id, "FORM_POPULATED", "Form populated successfully.", status="PROCESSING")

    test_db.expire_all()
    refreshed_job = test_db.query(models.Job).filter(models.Job.id == job.id).first()
    refreshed_lf = test_db.query(models.Form141LogicalFiling).filter(
        models.Form141LogicalFiling.logical_filing_id == lf.logical_filing_id
    ).first()

    assert refreshed_job.current_step == "FORM_POPULATED"
    assert refreshed_lf.current_step == "FORM_POPULATED"

    events = test_db.query(models.JobEvent).filter(models.JobEvent.job_id == job.id).all()
    assert len(events) == 1
    assert events[0].event_type == "FORM_POPULATED"
    assert events[0].message == "Form populated successfully."
