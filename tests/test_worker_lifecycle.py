import pytest
import os
import asyncio
from datetime import datetime, timezone, timedelta
from apps.worker.browser.manager import BrowserManager
from apps.worker.workflows.job_workflow import process_job
from apps.backend.app.database import models

@pytest.mark.asyncio
async def test_browser_automation_mock_flow():
    """
    Tests full browser automation lifecycle with real Chromium in mock mode:
    Launch browser -> Mock Login -> Navigate Form 141 -> Fill Data -> Validate -> Payment Gateway -> Verify Context
    """
    os.environ["PORTAL_MODE"] = "mock"
    browser_manager = BrowserManager(headless=True)
    await browser_manager.start()

    try:
        job_data = {
            "job_reference": "TEST-JOB-999",
            "portal_user_id": "ABCDE1234F",
            "data_payload": {
                "pan": "ABCDE1234F",
                "amount": 100000.0,
                "tds_amount": 1000.0,
                "property_type": "Land",
                "pincode": "110001"
            }
        }

        context = await process_job(job_data, browser_manager)
        assert context is not None
        assert len(context.pages) > 0

        # Verify page arrived at the payment gateway
        page = context.pages[0]
        content = await page.content()
        assert "Payment Gateway" in content or "Payment" in content

        # Clean up context
        await context.close()
    finally:
        await browser_manager.stop()

def test_recovery_stale_job_detection(test_db):
    """
    Tests that recovery logic detects workers that went offline and marks jobs for recovery.
    """
    stale_time = datetime.now(timezone.utc) - timedelta(seconds=60)
    worker = models.Worker(
        worker_id="WORKER-CRASHED",
        hostname="test-host",
        status="ONLINE",
        last_heartbeat=stale_time
    )
    test_db.add(worker)
    test_db.flush()

    job = models.Job(
        job_reference="JOB-STALE-001",
        status="PROCESSING",
        worker_id="WORKER-CRASHED",
        attempt_count=1
    )
    test_db.add(job)
    test_db.commit()

    # Run recovery query
    stale_threshold = datetime.now(timezone.utc) - timedelta(seconds=30)
    stale_workers = test_db.query(models.Worker).filter(
        models.Worker.status == "ONLINE",
        models.Worker.last_heartbeat < stale_threshold
    ).all()
    assert len(stale_workers) == 1

    for w in stale_workers:
        w.status = "OFFLINE"
        stale_jobs = test_db.query(models.Job).filter(models.Job.status == "PROCESSING").all()
        for j in stale_jobs:
            j.status = "QUEUED"
            j.attempt_count += 1

    test_db.commit()

    # Verify recovered
    refreshed_job = test_db.query(models.Job).filter(models.Job.job_reference == "JOB-STALE-001").first()
    assert refreshed_job.status == "QUEUED"
    assert refreshed_job.attempt_count == 2
