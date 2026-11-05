import pytest
from apps.backend.app.api.import_data import compute_form141_logical_filing_identity
from apps.backend.app.api.jobs import mask_pan, get_job_detail
from apps.backend.app.database import models
from apps.worker.portal.adapter import (
    PortalAuthFailedException,
    AuthInterventionRequiredException,
    mask_pan as adapter_mask_pan
)

def test_form141_pan_only_duplicate_identity_rule():
    """
    Verifies that the duplicate key is strictly:
    normalized_deductor_pan + "|" + normalized_deductee_pan
    Two records are duplicates if and only if both normalized PANs match.
    Customer names, labels, amounts, and other fields must never be used.
    """
    record_1 = {
        "deductorPan": "AWQPM0067K",
        "deducteePan": "AAAPB1234C",
        "buyerName": "Customer 1",
        "saleConsideration": 5000000.0,
        "taxYear": "2026-27"
    }
    
    # Same PANs, but completely different buyerName, amounts, taxYear
    record_2 = {
        "deductorPan": "awqpm0067k ",
        "deducteePan": " aaapb1234c",
        "buyerName": "Different Name Completely",
        "saleConsideration": 90000000.0,
        "taxYear": "2027-28"
    }
    
    id1 = compute_form141_logical_filing_identity(record_1)
    id2 = compute_form141_logical_filing_identity(record_2)
    
    assert id1["canonical_key"] == "AWQPM0067K|AAAPB1234C"
    assert id2["canonical_key"] == "AWQPM0067K|AAAPB1234C"
    assert id1["identity_hash"] == id2["identity_hash"], "Exact same normalized PAN pair must be identified as duplicates!"

def test_form141_different_deductor_pans_are_not_duplicates():
    """Two records are different if they have different deductor PANs."""
    rec_a = {
        "deductorPan": "AWQPM0067K",
        "deducteePan": "AAAPB1234C",
        "buyerName": "Same Name"
    }
    rec_b = {
        "deductorPan": "AWQPM0067G",
        "deducteePan": "AAAPB1234C",
        "buyerName": "Same Name"
    }
    
    id_a = compute_form141_logical_filing_identity(rec_a)
    id_b = compute_form141_logical_filing_identity(rec_b)
    
    assert id_a["canonical_key"] != id_b["canonical_key"]
    assert id_a["identity_hash"] != id_b["identity_hash"]

def test_form141_different_deductee_pans_are_not_duplicates():
    """Two records are different if they have different deductee PANs."""
    rec_a = {
        "deductorPan": "AWQPM0067K",
        "deducteePan": "AAAPB1234C",
        "buyerName": "Same Name"
    }
    rec_b = {
        "deductorPan": "AWQPM0067K",
        "deducteePan": "BBBPB5678D",
        "buyerName": "Same Name"
    }
    
    id_a = compute_form141_logical_filing_identity(rec_a)
    id_b = compute_form141_logical_filing_identity(rec_b)
    
    assert id_a["canonical_key"] != id_b["canonical_key"]
    assert id_a["identity_hash"] != id_b["identity_hash"]

def test_pan_masking():
    """Verifies that PANs are safely masked across both backend and worker."""
    assert mask_pan("AWQPM0067K") == "AWQPM****K"
    assert mask_pan("ABCDE1234F") == "ABCDE****F"
    assert mask_pan("") == "N/A"
    
    assert adapter_mask_pan("AWQPM0067K") == "AW*****7K"
    assert adapter_mask_pan("ABCDE1234F") == "AB*****4F"
    assert adapter_mask_pan("") == "N/A"

def test_credential_redaction_in_job_detail(test_db):
    """Verifies that passwords are never returned in plaintext in job detail response."""
    cust = models.Customer(customer_code="CUST-SEC", name="Security Test Client")
    test_db.add(cust)
    test_db.flush()
    
    job = models.Job(
        job_reference="JOB-SEC-01",
        customer_id=cust.id,
        status="QUEUED",
        data_payload={
            "deductorPan": "AWQPM0067K",
            "_loginPan": "AWQPM0067K",
            "_loginPassword": "super_secret_password_123",
            "saleConsideration": 5000000.0
        }
    )
    test_db.add(job)
    test_db.commit()
    
    detail = get_job_detail(job.id, test_db)
    payload = detail["data_payload"]
    assert payload["_loginPassword"] == "••••••••", "Password must be redacted in API response!"
    assert "super_secret_password_123" not in str(detail)

def test_auth_exception_types():
    """Verifies distinct exception types for rejected auth vs human challenges."""
    fail_ex = PortalAuthFailedException("Request is not authenticated", error_code="PORTAL_AUTH_FAILED")
    assert fail_ex.error_code == "PORTAL_AUTH_FAILED"
    assert isinstance(fail_ex, Exception)
    
    int_ex = AuthInterventionRequiredException("OTP required", challenge_type="OTP")
    assert int_ex.challenge_type == "OTP"
    assert isinstance(int_ex, Exception)
