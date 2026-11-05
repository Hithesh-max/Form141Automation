import pytest
from apps.backend.app.database import models
import pandas as pd
import io
import json

def create_sample_excel():
    df = pd.DataFrame({
        "CustomerCode": ["CUST01", "CUST02", "CUST03"],
        "Name": ["Rahul Kumar", "Priya Sharma", "Amit Patel"],
        "PAN": ["ABCDE1234F", "INVALIDPAN", "XYZAB5678M"],
        "Amount": [50000, 25000, 15000],
        "TDS": [500, 250, 150]
    })
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)
    return buf

def test_import_preview_endpoint(client):
    excel_buf = create_sample_excel()
    files = {
        "file": ("test_filings.xlsx", excel_buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    }
    response = client.post("/api/import/preview", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["total_rows"] == 3
    assert data["valid_count"] == 2
    assert data["error_count"] >= 1
    assert "suggested_mapping" in data
    assert data["suggested_mapping"]["pan"] == "PAN"

def test_import_confirm_endpoint(client, test_db):
    excel_buf = create_sample_excel()
    files = {
        "file": ("test_filings.xlsx", excel_buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    }
    mapping = {
        "customer_code": "CustomerCode",
        "name": "Name",
        "pan": "PAN",
        "amount": "Amount",
        "tds_amount": "TDS"
    }
    response = client.post(
        "/api/import/confirm",
        files=files,
        data={"mapping": json.dumps(mapping), "import_valid_only": "true"}
    )
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["jobs_created"] == 2
    assert res_data["rejected_count"] == 1

    # Verify rows in DB
    jobs = test_db.query(models.Job).all()
    assert len(jobs) == 2
    for j in jobs:
        assert j.status == "READY"
        assert j.current_step == "READY"
    customers = test_db.query(models.Customer).all()
    assert len(customers) == 2
    filings = test_db.query(models.Filing).all()
    assert len(filings) == 2
    audit_logs = test_db.query(models.AuditLog).all()
    assert len(audit_logs) >= 1
