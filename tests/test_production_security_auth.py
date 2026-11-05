import pytest
import os
import time
from fastapi.testclient import TestClient
from apps.backend.app.main import app
from apps.backend.app.database import models
from apps.backend.app.api.auth import create_access_token, decode_access_token, hash_password, verify_password


def test_password_hashing():
    pwd = "StrongSecurePassword!2026"
    stored = hash_password(pwd)
    assert verify_password(pwd, stored) is True
    assert verify_password("WrongPassword", stored) is False


def test_token_issuance_and_decoding():
    token = create_access_token(user_id=42, username="audit_admin", role="ADMIN", expires_in=60)
    assert token is not None
    assert "." in token

    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == 42
    assert decoded["username"] == "audit_admin"
    assert decoded["role"] == "ADMIN"
    assert decoded["exp"] > int(time.time())


def test_token_expiration():
    token = create_access_token(user_id=42, username="exp_user", role="EMPLOYEE", expires_in=-10)
    decoded = decode_access_token(token)
    assert decoded is None


def test_tampered_token_rejected():
    token = create_access_token(user_id=42, username="safe_user", role="EMPLOYEE", expires_in=300)
    payload_part, sig_part = token.split(".", 1)
    tampered = f"{payload_part}modified.{sig_part}"
    assert decode_access_token(tampered) is None


def test_login_flow_with_valid_and_invalid_credentials(client: TestClient, test_db):
    user = models.User(
        username="test_operator",
        password_hash=hash_password("operator_pass_123"),
        role="EMPLOYEE",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()

    # 1. Invalid credentials
    res_bad = client.post("/api/auth/login", json={"username": "test_operator", "password": "wrong_pass"})
    assert res_bad.status_code == 401

    # 2. Valid credentials
    res_good = client.post("/api/auth/login", json={"username": "test_operator", "password": "operator_pass_123"})
    assert res_good.status_code == 200
    data = res_good.json()
    assert "access_token" in data
    assert data["user"]["username"] == "test_operator"
    assert data["user"]["role"] == "EMPLOYEE"

    # 3. Use access token on /me
    token = data["access_token"]
    res_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_me.status_code == 200
    assert res_me.json()["username"] == "test_operator"


def test_invalid_bearer_token_rejection(client: TestClient):
    res = client.get("/api/auth/me", headers={"Authorization": "Bearer forged.invalid.token"})
    assert res.status_code == 401
    assert "Invalid" in res.json()["detail"] or "Authentication" in res.json()["detail"]


def test_review_and_payment_state_machine_transition(client: TestClient, test_db):
    """
    Validates the strict flow:
    REVIEW_REQUIRED -> REVIEW_CONFIRMED -> PAYMENT_PENDING -> PAYMENT_CONFIRMED -> COMPLETED
    """
    user = models.User(
        username="officer",
        password_hash=hash_password("officer_pass"),
        role="ADMIN",
        is_active=True
    )
    test_db.add(user)
    test_db.flush()

    token = create_access_token(user.id, user.username, user.role)
    auth_headers = {"Authorization": f"Bearer {token}"}

    customer = models.Customer(customer_code="CUST-SEC-01", name="Security Client")
    test_db.add(customer)
    test_db.flush()

    job = models.Job(
        job_reference="JOB-SEC-001",
        customer_id=customer.id,
        status="REVIEW_REQUIRED",
        current_step="REVIEW_REQUIRED"
    )
    test_db.add(job)
    test_db.commit()

    # 1. Confirm Review
    res_rev = client.post(f"/api/jobs/{job.id}/review/confirm", headers=auth_headers)
    assert res_rev.status_code == 200
    assert res_rev.json()["success"] is True

    test_db.refresh(job)
    assert job.status == "PAYMENT_PENDING"
    assert job.current_step == "REVIEW_CONFIRMED"

    # 2. Confirm Payment
    res_pay = client.post(f"/api/jobs/{job.id}/payment/confirm", headers=auth_headers)
    assert res_pay.status_code == 200

    test_db.refresh(job)
    assert job.status == "COMPLETED"
    assert job.current_step == "PAYMENT_CONFIRMED"
    assert job.completed_at is not None
