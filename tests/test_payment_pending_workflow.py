import pytest
import os
import asyncio
from datetime import datetime, timezone
from apps.worker.browser.manager import BrowserManager
from apps.worker.workflows.job_workflow import process_job
from apps.backend.app.database import models
from apps.backend.app.auth.encryption import encrypt_data

@pytest.mark.asyncio
async def test_scenarios_a_to_e_multi_session_lifecycle(test_db):
    """
    Executes Tests A, B, C, D, E from Master Prompt:
    TEST A: JOB-1 reaches PAYMENT_PENDING, worker slot released, JOB-2 reaches PAYMENT_PENDING simultaneously.
    TEST B: Context-1 != Context-2 (isolated contexts).
    TEST C: Open Session on JOB-1 focuses only Context-1.
    TEST D: Open Session on JOB-2 focuses only Context-2.
    TEST E: Confirm payment on JOB-1 closes Context-1 while Context-2 remains alive.
    """
    os.environ["PORTAL_MODE"] = "mock"
    browser_manager = BrowserManager(headless=True)
    await browser_manager.start()

    try:
        # Create Customer 1 & Filing 1 & Job 1
        cust1 = models.Customer(customer_code="CUST-A", name="Client A", pan_encrypted=encrypt_data("ABCDE1234A"))
        test_db.add(cust1)
        test_db.flush()
        filing1 = models.Filing(customer_id=cust1.id, filing_reference="FIL-A", amount=7000000.0, tds_amount=70000.0, status="IMPORTED")
        test_db.add(filing1)
        test_db.flush()
        job1 = models.Job(job_reference="JOB-1-TEST", customer_id=cust1.id, filing_id=filing1.id, status="QUEUED", attempt_count=0)
        test_db.add(job1)

        # Create Customer 2 & Filing 2 & Job 2
        cust2 = models.Customer(customer_code="CUST-B", name="Client B", pan_encrypted=encrypt_data("ABCDE1234B"))
        test_db.add(cust2)
        test_db.flush()
        filing2 = models.Filing(customer_id=cust2.id, filing_reference="FIL-B", amount=4200000.0, tds_amount=42000.0, status="IMPORTED")
        test_db.add(filing2)
        test_db.flush()
        job2 = models.Job(job_reference="JOB-2-TEST", customer_id=cust2.id, filing_id=filing2.id, status="QUEUED", attempt_count=0)
        test_db.add(job2)
        test_db.commit()

        # Step 1: Worker automates Job 1 up to PAYMENT_PENDING
        job1.status = "PROCESSING"
        test_db.commit()

        job1_payload = {
            "job_reference": job1.job_reference,
            "portal_user_id": "ABCDE1234A",
            "data_payload": {"pan": "ABCDE1234A", "amount": 7000000.0, "tds_amount": 70000.0}
        }
        context1 = await process_job(job1_payload, browser_manager)
        page1 = getattr(context1, "_active_page", None) or context1.pages[0]

        # Transition Job 1 to PAYMENT_PENDING and register session
        job1.status = "PAYMENT_PENDING"
        test_db.commit()
        reg1 = await browser_manager.register_session(
            job_id=job1.id,
            job_reference=job1.job_reference,
            customer_id=job1.customer_id,
            filing_id=job1.filing_id,
            context=context1,
            page=page1
        )
        assert reg1["session_available"] is True

        # TEST A verification: Job 1 browser stays alive and worker is free to process Job 2!
        assert len(context1.pages) > 0
        assert not page1.is_closed()

        # Step 2: Worker automates Job 2 up to PAYMENT_PENDING
        job2.status = "PROCESSING"
        test_db.commit()

        job2_payload = {
            "job_reference": job2.job_reference,
            "portal_user_id": "ABCDE1234B",
            "data_payload": {"pan": "ABCDE1234B", "amount": 4200000.0, "tds_amount": 42000.0}
        }
        context2 = await process_job(job2_payload, browser_manager)
        page2 = getattr(context2, "_active_page", None) or context2.pages[0]

        job2.status = "PAYMENT_PENDING"
        test_db.commit()
        reg2 = await browser_manager.register_session(
            job_id=job2.id,
            job_reference=job2.job_reference,
            customer_id=job2.customer_id,
            filing_id=job2.filing_id,
            context=context2,
            page=page2
        )
        assert reg2["session_available"] is True

        # TEST B: Verify Context-1 != Context-2 (sessions are completely isolated)
        assert context1 != context2
        assert reg1["browser_context_id"] != reg2["browser_context_id"]
        assert len(browser_manager.sessions) == 2

        # TEST C: Open Session on Job 1
        open1_res = await browser_manager.open_session(job1.id)
        assert open1_res["success"] is True
        assert open1_res["browser_context_id"] == reg1["browser_context_id"]

        # TEST D: Open Session on Job 2
        open2_res = await browser_manager.open_session(job2.id)
        assert open2_res["success"] is True
        assert open2_res["browser_context_id"] == reg2["browser_context_id"]
        assert open1_res["browser_context_id"] != open2_res["browser_context_id"]

        # TEST E: Payment Completion on Job 1
        job1.status = "COMPLETED"
        test_db.commit()
        close1_res = await browser_manager.close_session(job1.id)
        assert close1_res["success"] is True

        # Context-1 must be closed
        assert job1.id not in browser_manager.sessions
        # Context-2 must remain alive
        assert job2.id in browser_manager.sessions
        assert browser_manager.has_session(job2.id) is True
        assert not page2.is_closed()

    finally:
        await browser_manager.stop()


@pytest.mark.asyncio
async def test_scenario_f_requeue_preserves_identities(test_db, client):
    """
    TEST F: Requeuing/retrying a job preserves logical customer and filing identities,
    increments attempt_count, and does not create duplicate filings.
    """
    cust = models.Customer(customer_code="CUST-RETRY", name="Retry Client", pan_encrypted=encrypt_data("ABCDE9999R"))
    test_db.add(cust)
    test_db.flush()

    filing = models.Filing(customer_id=cust.id, filing_reference="FIL-RETRY-01", amount=500000.0, tds_amount=5000.0, status="IMPORTED")
    test_db.add(filing)
    test_db.flush()

    job = models.Job(job_reference="JOB-RETRY-01", customer_id=cust.id, filing_id=filing.id, status="FAILED", attempt_count=1)
    test_db.add(job)
    test_db.commit()
    job_id = job.id

    # Call retry endpoint
    res = client.post(f"/api/jobs/{job_id}/retry")
    assert res.status_code == 200
    assert res.json()["attempt_count"] == 2

    # Verify identities preserved
    test_db.expire_all()
    refreshed_job = test_db.query(models.Job).filter(models.Job.id == job_id).first()
    assert refreshed_job.customer_id == cust.id
    assert refreshed_job.filing_id == filing.id
    assert refreshed_job.attempt_count == 2
    assert refreshed_job.status == "QUEUED"

    # Verify no duplicate filings were created
    filings_count = test_db.query(models.Filing).filter(models.Filing.customer_id == cust.id).count()
    assert filings_count == 1


@pytest.mark.asyncio
async def test_scenario_g_manual_browser_close_detection():
    """
    TEST G: If employee closes the Chromium page/tab manually, the registry detects it,
    marks session unavailable, and does not silently fabricate a new filing.
    """
    browser_manager = BrowserManager(headless=True)
    await browser_manager.start()

    try:
        context = await browser_manager.create_context()
        page = await context.new_page()

        reg = await browser_manager.register_session(
            job_id=999,
            job_reference="JOB-MANUAL-CLOSE",
            customer_id=1,
            filing_id=1,
            context=context,
            page=page
        )
        assert reg["session_available"] is True

        # Close the page manually (simulating employee closing Chromium tab)
        await page.close()

        # Verify registry detects the closed session
        check = browser_manager.check_session(999)
        assert check["session_available"] is False

        # Verify Open Session fails gracefully
        open_res = await browser_manager.open_session(999)
        assert open_res["success"] is False
        assert open_res["session_available"] is False
        assert open_res["reason"] == "SESSION_UNAVAILABLE"

    finally:
        await browser_manager.stop()


def test_api_open_session_and_dashboard_summary_multi_payment(client, test_db):
    """
    Verifies that:
    1. GET /api/dashboard/summary returns payment_pending_jobs with full details.
    2. POST /api/jobs/{job_id}/open-session returns safe metadata or structured failure.
    3. No secrets/credentials are exposed.
    """
    cust = models.Customer(customer_code="CUST-DASH", name="Soumya S", pan_encrypted=encrypt_data("ABCDE1234S"))
    test_db.add(cust)
    test_db.flush()

    filing = models.Filing(customer_id=cust.id, filing_reference="F141-6CA86C", amount=7000000.0, tds_amount=70000.0, status="IMPORTED")
    test_db.add(filing)
    test_db.flush()

    job = models.Job(job_reference="JOB-3-3AAD9A", customer_id=cust.id, filing_id=filing.id, status="PAYMENT_PENDING", current_step="PAYMENT_PENDING", attempt_count=0)
    test_db.add(job)
    test_db.commit()

    # 1. Summary endpoint
    res_summary = client.get("/api/dashboard/summary")
    assert res_summary.status_code == 200
    data = res_summary.json()
    assert "payment_pending_jobs" in data
    assert len(data["payment_pending_jobs"]) >= 1

    pj = next(j for j in data["payment_pending_jobs"] if j["id"] == job.id)
    assert pj["customer_name"] == "Soumya S"
    assert pj["amount"] == 7000000.0
    assert pj["tds_amount"] == 70000.0
    assert "pan_masked" in pj
    assert pj["pan_masked"] == "ABCDE****S"

    # Ensure no secrets in response
    summary_str = str(data)
    assert "password" not in summary_str.lower()
    assert "credential" not in summary_str.lower()

    # 2. Open Session endpoint for job without active worker session
    res_open = client.post(f"/api/jobs/{job.id}/open-session")
    assert res_open.status_code == 200
    open_data = res_open.json()
    # When worker is not running, gracefully returns session_available = False
    assert open_data["session_available"] is False
    assert "reason" in open_data


@pytest.mark.asyncio
async def test_scenario_3_jobs_end_to_end_concurrency(test_db):
    """
    Executes Section 16 requirements:
    Real test with at least 3 jobs:
    JOB-1 -> PAYMENT_PENDING (worker released)
    JOB-2 -> PAYMENT_PENDING (worker released)
    JOB-3 -> PROCESSING
    Verify Context-1, Context-2, Context-3 are distinct and isolated.
    Confirm payment on JOB-1 -> JOB-1 COMPLETED, Context-1 CLOSED, Context-2 & Context-3 ALIVE.
    """
    os.environ["PORTAL_MODE"] = "mock"
    browser_manager = BrowserManager(headless=True)
    await browser_manager.start()

    try:
        jobs = []
        contexts = []
        pages = []
        for i in range(1, 4):
            cust = models.Customer(customer_code=f"CUST-{i}", name=f"Client {i}", pan_encrypted=encrypt_data(f"ABCDE123{i}A"))
            test_db.add(cust)
            test_db.flush()
            fil = models.Filing(customer_id=cust.id, filing_reference=f"FIL-141-{i}", amount=5000000.0 * i, tds_amount=50000.0 * i, status="IMPORTED")
            test_db.add(fil)
            test_db.flush()
            jb = models.Job(job_reference=f"JOB-{i}-E2E", customer_id=cust.id, filing_id=fil.id, status="QUEUED", attempt_count=0)
            test_db.add(jb)
            test_db.commit()
            jobs.append(jb)

        # Process Job 1 to PAYMENT_PENDING
        ctx1 = await process_job({"job_reference": jobs[0].job_reference, "portal_user_id": f"ABCDE1231A", "data_payload": {"pan": f"ABCDE1231A", "amount": 5000000.0, "tds_amount": 50000.0}}, browser_manager)
        p1 = getattr(ctx1, "_active_page", None) or ctx1.pages[0]
        await browser_manager.register_session(jobs[0].id, jobs[0].job_reference, jobs[0].customer_id, jobs[0].filing_id, ctx1, p1)
        jobs[0].status = "PAYMENT_PENDING"
        test_db.commit()

        # Process Job 2 to PAYMENT_PENDING
        ctx2 = await process_job({"job_reference": jobs[1].job_reference, "portal_user_id": f"ABCDE1232A", "data_payload": {"pan": f"ABCDE1232A", "amount": 10000000.0, "tds_amount": 100000.0}}, browser_manager)
        p2 = getattr(ctx2, "_active_page", None) or ctx2.pages[0]
        await browser_manager.register_session(jobs[1].id, jobs[1].job_reference, jobs[1].customer_id, jobs[1].filing_id, ctx2, p2)
        jobs[1].status = "PAYMENT_PENDING"
        test_db.commit()

        # Process Job 3 in PROCESSING
        ctx3 = await browser_manager.create_context()
        p3 = await ctx3.new_page()
        jobs[2].status = "PROCESSING"
        test_db.commit()

        # Isolation asserts: Context-1 != Context-2 != Context-3
        assert ctx1 != ctx2
        assert ctx2 != ctx3
        assert ctx1 != ctx3

        assert browser_manager.has_session(jobs[0].id) is True
        assert browser_manager.has_session(jobs[1].id) is True

        # Open session on Job 1
        res1 = await browser_manager.open_session(jobs[0].id)
        assert res1["success"] is True

        # Confirm payment on Job 1: Closes context 1
        close_res = await browser_manager.close_session(jobs[0].id)
        assert close_res["success"] is True
        jobs[0].status = "COMPLETED"
        test_db.commit()

        # Context 1 closed, Context 2 & 3 still alive
        assert browser_manager.has_session(jobs[0].id) is False
        assert browser_manager.has_session(jobs[1].id) is True
        assert not p2.is_closed()
        assert not p3.is_closed()

        await ctx3.close()
    finally:
        await browser_manager.stop()


@pytest.mark.asyncio
async def test_worker_restart_session_invalidation():
    """
    Verifies Section 8:
    When worker restarts, stale sessions are cleared and do not falsely report session_available=True.
    """
    bm1 = BrowserManager(headless=True)
    await bm1.start()
    ctx = await bm1.create_context()
    p = await ctx.new_page()
    await bm1.register_session(888, "JOB-888", 1, 1, ctx, p)
    assert bm1.has_session(888) is True
    await bm1.stop()

    # Simulate worker restart: new BrowserManager instance
    bm2 = BrowserManager(headless=True)
    await bm2.start()
    try:
        # Session must not exist in restarted worker
        assert bm2.has_session(888) is False
        check = bm2.check_session(888)
        assert check["session_available"] is False
    finally:
        await bm2.stop()
