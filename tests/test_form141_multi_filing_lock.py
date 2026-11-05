import pytest
import os
import io
import json
from apps.backend.app.database import models
from apps.backend.app.auth.encryption import encrypt_data
from apps.worker.browser.manager import BrowserManager
from apps.worker.workflows.job_workflow import process_job

EXCEL_PATH = r"c:\Users\MAHE\Desktop\income-tax-antigravity\Form_141_Multi_Customer_Grouped_Type.xlsx"

def test_form141_matrix_preview_structure(client):
    """
    Test 1: Preview parses fields as rows and all customers as columns.
    Validates dynamic customer detection and matrix structure.
    """
    with open(EXCEL_PATH, "rb") as f:
        file_bytes = f.read()

    res = client.post(
        "/api/import/form141/preview",
        files={"file": ("Form_141_Multi_Customer_Grouped_Type.xlsx", io.BytesIO(file_bytes), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_form141"] is True
    assert "fields" in data
    assert len(data["fields"]) >= 40
    assert len(data["customers"]) >= 1
    # Check that each field has section and label
    first_field = data["fields"][0]
    assert "fieldLabel" in first_field
    assert "sectionKey" in first_field
    assert "fetchType" in first_field


def test_form141_multi_filing_strict_concurrency_lock(test_db, client):
    """
    Test 2: With 3 Filings (A, B, C):
    1. Import creates jobs in validation status (e.g. READY).
    2. Filing A starts -> status transitions to QUEUED/PROCESSING.
    3. Active lock endpoint reports has_active_job = True.
    4. Attempting to start Filing B returns HTTP 409 Conflict with active job details.
    5. Attempting to start Filing C returns HTTP 409 Conflict.
    6. Filing A completes payment -> lock is released.
    7. Filing B can now start successfully.
    """
    # Create 3 distinct customers and filings
    cust_a = models.Customer(customer_code="CUST-A", name="Customer A", pan_encrypted=encrypt_data("ABCDE1234A"))
    cust_b = models.Customer(customer_code="CUST-B", name="Customer B", pan_encrypted=encrypt_data("BCDEF2345B"))
    cust_c = models.Customer(customer_code="CUST-C", name="Customer C", pan_encrypted=encrypt_data("CDEFG3456C"))
    test_db.add_all([cust_a, cust_b, cust_c])
    test_db.flush()

    fil_a = models.Filing(customer_id=cust_a.id, filing_reference="FIL-A", amount=5000000.0, tds_amount=50000.0, status="IMPORTED")
    fil_b = models.Filing(customer_id=cust_b.id, filing_reference="FIL-B", amount=6000000.0, tds_amount=60000.0, status="IMPORTED")
    fil_c = models.Filing(customer_id=cust_c.id, filing_reference="FIL-C", amount=7000000.0, tds_amount=70000.0, status="IMPORTED")
    test_db.add_all([fil_a, fil_b, fil_c])
    test_db.flush()

    job_a = models.Job(job_reference="JOB-141-A", customer_id=cust_a.id, filing_id=fil_a.id, status="READY", attempt_count=0)
    job_b = models.Job(job_reference="JOB-141-B", customer_id=cust_b.id, filing_id=fil_b.id, status="READY", attempt_count=0)
    job_c = models.Job(job_reference="JOB-141-C", customer_id=cust_c.id, filing_id=fil_c.id, status="READY", attempt_count=0)
    test_db.add_all([job_a, job_b, job_c])
    test_db.commit()

    # Step 1: Check initial lock status - should be free
    lock_res = client.get("/api/jobs/active-lock")
    assert lock_res.status_code == 200
    lock_data = lock_res.json()
    assert lock_data["has_active_job"] is False
    assert lock_data["can_start"] is True

    # Step 2: Start Filing A
    start_a = client.post(f"/api/jobs/{job_a.id}/start")
    assert start_a.status_code == 200
    assert start_a.json()["status"] == "QUEUED"

    # Step 3: Check lock status - now active
    lock_res2 = client.get("/api/jobs/active-lock")
    assert lock_res2.status_code == 200
    lock_data2 = lock_res2.json()
    assert lock_data2["has_active_job"] is True
    assert lock_data2["can_start"] is False
    assert lock_data2["active_job"]["id"] == job_a.id

    # Step 4: Attempt to start Filing B -> Must return HTTP 409 Conflict
    start_b = client.post(f"/api/jobs/{job_b.id}/start")
    assert start_b.status_code == 409
    err_b = start_b.json()
    assert "CONCURRENCY_LOCK_ACTIVE" in str(err_b)

    # Step 5: Attempt to start Filing C -> Must return HTTP 409 Conflict
    start_c = client.post(f"/api/jobs/{job_c.id}/start")
    assert start_c.status_code == 409
    err_c = start_c.json()
    assert "CONCURRENCY_LOCK_ACTIVE" in str(err_c)

    # Step 6: Advance Job A to PAYMENT_PENDING
    job_a.status = "PAYMENT_PENDING"
    test_db.commit()

    # Still locked while in PAYMENT_PENDING
    start_b_pending = client.post(f"/api/jobs/{job_b.id}/start")
    assert start_b_pending.status_code == 409

    # Step 7: Employee completes payment on Filing A
    comp_a = client.post(f"/api/jobs/{job_a.id}/payment/complete")
    assert comp_a.status_code == 200

    # Step 8: Verify Filing B does NOT auto-start
    test_db.refresh(job_b)
    assert job_b.status == "READY"

    # Step 9: Lock is released
    lock_res3 = client.get("/api/jobs/active-lock")
    assert lock_res3.json()["has_active_job"] is False
    assert lock_res3.json()["can_start"] is True

    # Step 10: Now Filing B can be started explicitly
    start_b_ok = client.post(f"/api/jobs/{job_b.id}/start")
    assert start_b_ok.status_code == 200
    assert start_b_ok.json()["status"] == "QUEUED"

    # Filing C is now locked by Filing B
    start_c_locked = client.post(f"/api/jobs/{job_c.id}/start")
    assert start_c_locked.status_code == 409
