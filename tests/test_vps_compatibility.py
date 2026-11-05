import pytest
import time
from fastapi.testclient import TestClient
from apps.backend.app.main import app
from apps.backend.app.database import models
from apps.backend.app.services.browser_viewer_service import browser_viewer_service, BrowserViewerService


def test_browser_viewer_token_lifecycle():
    """Verify HMAC token generation, verification, and expiration."""
    service = BrowserViewerService(secret_key="test-secret-key-12345")
    
    # 1. Generate valid token
    token = service.generate_token(job_id=42, user_id=1, ttl_seconds=60)
    assert token is not None
    assert "." in token

    # 2. Verify token
    payload = service.verify_token(token, expected_job_id=42)
    assert payload is not None
    assert payload["job_id"] == 42
    assert payload["user_id"] == 1

    # 3. Verify wrong job_id fails
    wrong_job_payload = service.verify_token(token, expected_job_id=99)
    assert wrong_job_payload is None

    # 4. Verify tampered token fails
    parts = token.split(".")
    tampered = f"{parts[0]}xyz.{parts[1]}"
    assert service.verify_token(tampered, expected_job_id=42) is None

    # 5. Verify expired token fails
    expired_token = service.generate_token(job_id=42, user_id=1, ttl_seconds=-1)
    assert service.verify_token(expired_token, expected_job_id=42) is None


def test_viewer_endpoint_authorization(client: TestClient, test_db):
    """Verify viewer HTML endpoint enforces valid tokens."""
    # Create customer and job
    customer = models.Customer(customer_code="CUST-TEST", name="Test Customer")
    test_db.add(customer)
    test_db.flush()

    job = models.Job(
        job_reference="JOB-TEST-001",
        customer_id=customer.id,
        status="PAYMENT_PENDING"
    )
    test_db.add(job)
    test_db.commit()

    # 1. Access without token fails with 422
    res_no_token = client.get(f"/api/jobs/{job.id}/viewer")
    assert res_no_token.status_code == 422

    # 2. Access with invalid token returns 403
    res_bad_token = client.get(f"/api/jobs/{job.id}/viewer?token=invalid.token")
    assert res_bad_token.status_code == 403
    assert "Access Denied" in res_bad_token.text

    # 3. Access with valid token returns 200 HTML page with job details
    valid_token = browser_viewer_service.generate_token(job.id)
    res_valid = client.get(f"/api/jobs/{job.id}/viewer?token={valid_token}")
    assert res_valid.status_code == 200
    assert "JOB-TEST-001" in res_valid.text
    assert "Test Customer" in res_valid.text
    assert "CONFIDENTIAL TAX DATA" in res_valid.text


def test_review_confirm_endpoint(client: TestClient, test_db):
    """Verify review confirmation endpoint records audit and step."""
    customer = models.Customer(customer_code="CUST-REV", name="Review Client")
    test_db.add(customer)
    test_db.flush()

    job = models.Job(
        job_reference="JOB-REV-001",
        customer_id=customer.id,
        status="REVIEW_REQUIRED"
    )
    test_db.add(job)
    test_db.commit()

    # Confirm review
    res = client.post(f"/api/jobs/{job.id}/review/confirm")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True

    test_db.refresh(job)
    assert job.current_step == "REVIEW_CONFIRMED"

    # Audit log recorded
    audit = test_db.query(models.AuditLog).filter(
        models.AuditLog.action == "REVIEW_CONFIRMED",
        models.AuditLog.entity_id == "JOB-REV-001"
    ).first()
    assert audit is not None


def test_system_liveness_and_readiness_endpoints(client: TestClient):
    """Verify lightweight liveness and readiness probes for VPS container health checks."""
    res_live = client.get("/api/system/live")
    assert res_live.status_code == 200
    assert res_live.json()["status"] == "alive"

    res_ready = client.get("/api/system/ready")
    assert res_ready.status_code == 200
    assert res_ready.json()["status"] == "ready"
