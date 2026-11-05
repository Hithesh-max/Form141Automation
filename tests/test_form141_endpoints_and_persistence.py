import pytest
import io
from apps.backend.app.database import models
from apps.backend.app.auth.encryption import encrypt_data

EXCEL_PATH = r"c:\Users\MAHE\Desktop\income-tax-antigravity\Form_141_Multi_Customer_Grouped_Type.xlsx"

def test_form141_import_and_persistence_endpoints(client, test_db):
    """
    Validates:
    1. Uploading/confirming Form 141 workbook persists Form141Import and Form141LogicalFiling records.
    2. GET /api/form141/imports returns batch imports.
    3. GET /api/form141/imports/{id}/filings returns customer columns.
    4. GET /api/form141/filings returns all logical filings.
    5. GET /api/form141/active-lock reflects lock status.
    6. POST /api/form141/filings/{id}/start starts the chosen filing and locks others.
    """
    with open(EXCEL_PATH, "rb") as f:
        file_bytes = f.read()

    # Confirm import
    confirm_res = client.post(
        "/api/import/form141/confirm",
        files={"file": ("Form_141_Multi_Customer_Grouped_Type.xlsx", io.BytesIO(file_bytes), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )
    assert confirm_res.status_code == 200
    confirm_data = confirm_res.json()
    assert confirm_data["jobs_created"] >= 1

    # 1. Test GET /api/form141/imports
    imports_res = client.get("/api/form141/imports")
    assert imports_res.status_code == 200
    imports_data = imports_res.json()
    assert "imports" in imports_data
    assert len(imports_data["imports"]) >= 1
    import_rec = imports_data["imports"][0]
    assert import_rec["filename"] == "Form_141_Multi_Customer_Grouped_Type.xlsx"
    import_id = import_rec["id"]

    # 2. Test GET /api/form141/imports/{import_id}/filings
    imp_filings_res = client.get(f"/api/form141/imports/{import_id}/filings")
    assert imp_filings_res.status_code == 200
    imp_filings_data = imp_filings_res.json()
    assert "filings" in imp_filings_data
    assert len(imp_filings_data["filings"]) >= 1
    first_lf = imp_filings_data["filings"][0]
    assert "logical_filing_id" in first_lf
    assert "customer_label" in first_lf
    assert first_lf["status"] in ["READY", "VALIDATION_REQUIRED"]

    # 3. Test GET /api/form141/filings
    all_filings_res = client.get("/api/form141/filings")
    assert all_filings_res.status_code == 200
    all_filings = all_filings_res.json()["filings"]
    assert len(all_filings) >= 1

    # 4. Test GET /api/form141/active-lock initially
    lock_res = client.get("/api/form141/active-lock")
    assert lock_res.status_code == 200
    assert lock_res.json()["can_start"] is True

    # 5. Start first filing via POST /api/form141/filings/{id}/start
    target_id = first_lf["logical_filing_id"]
    start_res = client.post(f"/api/form141/filings/{target_id}/start")
    assert start_res.status_code == 200
    start_data = start_res.json()
    assert start_data["success"] is True
    assert start_data["status"] == "QUEUED"

    # 6. Check lock status is now active
    lock_res2 = client.get("/api/form141/active-lock")
    assert lock_res2.status_code == 200
    assert lock_res2.json()["has_active_job"] is True
    assert lock_res2.json()["can_start"] is False

    # 7. Attempting to start any filing now returns 409 Conflict
    conflict_res = client.post(f"/api/form141/filings/{target_id}/start")
    assert conflict_res.status_code in [400, 409]

    if len(all_filings) > 1:
        second_id = all_filings[1]["logical_filing_id"]
        conflict_res2 = client.post(f"/api/form141/filings/{second_id}/start")
        assert conflict_res2.status_code == 409
        assert "CONCURRENCY_LOCK_ACTIVE" in str(conflict_res2.json())

    # 8. Test /api/form141/active alias
    alias_res = client.get("/api/form141/active")
    assert alias_res.status_code == 200
    assert alias_res.json()["has_active_job"] is True

    # 9. Test /api/form141/kpi-summary
    kpi_res = client.get("/api/form141/kpi-summary")
    assert kpi_res.status_code == 200
    kpi_data = kpi_res.json()
    assert "total_filings" in kpi_data
    assert kpi_data["total_filings"] >= 1
    assert kpi_data["in_progress"] >= 1

    # 10. Test GET /api/form141/filings/{id} detail drawer endpoint
    detail_res = client.get(f"/api/form141/filings/{target_id}")
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert detail_data["logical_filing_id"] == target_id
    assert detail_data["total_attempts"] >= 1
    assert len(detail_data["attempts"]) >= 1
    assert detail_data["attempts"][0]["status"] == "QUEUED"
    assert "source_file" in detail_data

