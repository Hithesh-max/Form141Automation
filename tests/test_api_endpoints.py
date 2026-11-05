import pytest
from datetime import datetime, timezone
from apps.backend.app.database import models
from apps.backend.app.auth.encryption import encrypt_data

@pytest.fixture(autouse=True)
def seed_test_data(test_db):
    customer = models.Customer(
        customer_code="CUST-001",
        name="Sunil Sharma",
        pan_encrypted=encrypt_data("ABCDE1234F")
    )
    test_db.add(customer)
    test_db.flush()

    filing = models.Filing(
        customer_id=customer.id,
        filing_reference="FIL-001",
        amount=75000.0,
        tds_amount=750.0,
        status="IMPORTED"
    )
    test_db.add(filing)
    test_db.flush()

    job1 = models.Job(
        job_reference="JOB-001",
        customer_id=customer.id,
        filing_id=filing.id,
        status="QUEUED",
        current_step="QUEUED",
        attempt_count=0
    )
    job2 = models.Job(
        job_reference="JOB-002",
        customer_id=customer.id,
        filing_id=filing.id,
        status="PAYMENT_PENDING",
        current_step="PAYMENT_PENDING",
        attempt_count=1,
        started_at=datetime.now(timezone.utc)
    )
    test_db.add_all([job1, job2])
    test_db.commit()

def test_auth_endpoints(client):
    res = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["user"]["username"] == "admin"

    res_me = client.get("/api/auth/me")
    assert res_me.status_code == 200
    assert res_me.json()["username"] == "admin"

def test_dashboard_summary(client):
    res = client.get("/api/dashboard/summary")
    assert res.status_code == 200
    data = res.json()
    assert data["metrics"]["total_jobs"] == 2
    assert data["metrics"]["queued"] == 1
    assert data["metrics"]["payment_pending"] == 1
    assert data["active_job"] is not None
    assert data["active_job"]["job_reference"] == "JOB-002"
    assert data["active_job"]["status"] == "PAYMENT_PENDING"

def test_queue_controls(client):
    res = client.get("/api/queue/status")
    assert res.status_code == 200

    res = client.post("/api/queue/pause")
    assert res.status_code == 200
    assert res.json()["status"] == "PAUSED"

    res = client.post("/api/queue/resume")
    assert res.status_code == 200
    assert res.json()["status"] == "RUNNING"

    res = client.post("/api/queue/stop")
    assert res.status_code == 200
    assert res.json()["status"] == "STOPPED"

    res = client.post("/api/queue/start")
    assert res.status_code == 200
    assert res.json()["status"] == "RUNNING"

def test_jobs_list_and_filters(client):
    res = client.get("/api/jobs/")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert data["items"][0]["pan_masked"] == "ABCDE****F"

    res_queued = client.get("/api/jobs/?status=QUEUED")
    assert res_queued.status_code == 200
    assert res_queued.json()["total"] == 1

    res_search = client.get("/api/jobs/?search=Sunil")
    assert res_search.status_code == 200
    assert res_search.json()["total"] == 2

def test_job_detail(client):
    res = client.get("/api/jobs/2")
    assert res.status_code == 200
    data = res.json()
    assert data["job_reference"] == "JOB-002"
    assert data["customer"]["name"] == "Sunil Sharma"
    assert data["customer"]["pan_masked"] == "ABCDE****F"
    assert data["filing"]["amount"] == 75000.0

def test_job_retry_and_cancel(client):
    res_retry = client.post("/api/jobs/1/retry")
    assert res_retry.status_code == 200
    assert res_retry.json()["attempt_count"] == 1

    res_cancel = client.post("/api/jobs/1/cancel", json={"reason": "Testing cancellation"})
    assert res_cancel.status_code == 200

    res_detail = client.get("/api/jobs/1")
    assert res_detail.json()["status"] == "CANCELLED"

def test_payment_confirmation(client):
    res = client.post("/api/jobs/2/payment/confirm")
    assert res.status_code == 200
    assert res.json()["message"] == "Payment confirmed and job marked COMPLETED"

    res_detail = client.get("/api/jobs/2")
    assert res_detail.json()["status"] == "COMPLETED"

def test_payment_problem_report(client, test_db):
    job = models.Job(
        job_reference="JOB-003",
        customer_id=1,
        status="PAYMENT_PENDING",
        current_step="PAYMENT_PENDING"
    )
    test_db.add(job)
    test_db.commit()
    job_id = job.id

    res = client.post(f"/api/jobs/{job_id}/payment/problem", json={
        "problem_type": "MANUAL_INTERVENTION",
        "details": "Gateway rejected transaction due to bank timeout"
    })
    assert res.status_code == 200

    res_detail = client.get(f"/api/jobs/{job_id}")
    assert res_detail.json()["status"] == "MANUAL_INTERVENTION"

def test_customers_api(client):
    res = client.get("/api/customers/")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["customer_code"] == "CUST-001"

    res_detail = client.get("/api/customers/1")
    assert res_detail.status_code == 200
    assert res_detail.json()["customer_code"] == "CUST-001"
    assert len(res_detail.json()["jobs"]) >= 1

def test_system_health_and_audit(client):
    res_health = client.get("/api/system/health")
    assert res_health.status_code == 200
    assert res_health.json()["components"]["api"] == "ONLINE"

    res_audit = client.get("/api/system/audit")
    assert res_audit.status_code == 200
    assert "items" in res_audit.json()
