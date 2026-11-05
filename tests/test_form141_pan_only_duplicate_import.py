import pytest
import io
import json
import openpyxl
from fastapi.testclient import TestClient
from apps.backend.app.main import app
from apps.backend.app.database import models
from apps.backend.app.database.config import SessionLocal

client = TestClient(app)

def create_in_memory_form141_workbook(customers_data):
    """
    Creates an in-memory Form 141 multi-customer Excel workbook.
    customers_data: list of dicts, each specifying:
      login_pan, login_pwd, deductor_pan, buyer_name, seller_pan, deductee_pan, amount
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Form 141 Multi Customer"

    # Row 1: Headers
    headers = ["TYPE", "Form 141 Field", "Fetch Type"]
    for i in range(len(customers_data)):
        headers.append(f"Customer {i + 1}")
    ws.append(headers)

    # Standard rows
    rows_def = [
        ("LOGIN", "Login PAN", "Manual", "login_pan"),
        (None, "Login Password", "Manual", "login_pwd"),
        ("BASIC DETAILS", "Applicable Act", "Manual", lambda d: "Income-tax Act, 2025"),
        (None, "Deductee Type", "Select", lambda d: "Non-Corporate deductee(s)"),
        (None, "Residential Status of the Deductee(s)", "Select", lambda d: "Resident"),
        (None, "Deductor PAN", "Fetch", "deductor_pan"),
        (None, "Tax Year of Transaction", "Select", lambda d: "2026-27"),
        (None, "Month of Deduction", "Select", lambda d: "AUG-2026"),
        (None, "Nature of Transaction in respect of Purchase of Property", "Select", lambda d: "Schedule B."),
        ("IMMOVABLE PROPERTY DETAILS", "Type of Immovable Property", "Select", lambda d: "Building"),
        (None, "Flat / Door / Building", "Manual", lambda d: "Flat 101"),
        (None, "PIN Code", "Manual", lambda d: "400606"),
        (None, "Total Stamp Duty Value of Property", "Manual", lambda d: 5000000),
        (None, "Total Sale Consideration in respect of the Property", "Manual", "amount"),
        (None, "Type of Payment: Lumpsum or Instalments", "Select", lambda d: "Lumpsum"),
        ("BUYER / DEDUCTOR DETAILS", "Buyer's PAN", "Manual", "deductor_pan"),
        (None, "Buyer's Name", "Manual", "buyer_name"),
        (None, "Buyer's Proportion of Total Sale Consideration (%)", "Manual", lambda d: 100),
        ("SELLER / DEDUCTEE DETAILS", "Seller's PAN", "Manual", "seller_pan"),
        (None, "Seller's Name", "Fetch", lambda d: "Seller Name"),
        (None, "Seller's Proportion of Total Sale Consideration (%)", "Manual", lambda d: 100),
        ("TRANSACTION DETAILS", "PAN of the Deductee", "Manual", "deductee_pan"),
        (None, "Amount Paid/Credited in Present Transaction", "Manual", "amount"),
        (None, "Date of Payment/Credit", "Manual", lambda d: "2026-08-28"),
        (None, "Whether Section 395(1) Applicable", "Select", lambda d: "No"),
        (None, "Rate at which Tax Deducted (%)", "Validate", lambda d: 0.01),
        (None, "Date of Deduction", "Manual", lambda d: "2026-08-28"),
        ("TAX DEPOSIT DETAILS", "Interest", "Manual", lambda d: 0),
        (None, "Fees", "Manual", lambda d: 0),
        ("PAYMENT DETAILS", "Type of Payment", "Select", lambda d: "Net Banking")
    ]

    for type_val, field_name, fetch_type, key_or_fn in rows_def:
        row = [type_val, field_name, fetch_type]
        for c in customers_data:
            if callable(key_or_fn):
                val = key_or_fn(c)
            else:
                val = c.get(key_or_fn, "")
            row.append(val)
        ws.append(row)

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()

def test_import_three_customers_with_different_pans_persists_three_filings(client, test_db):
    """
    Verifies that importing 3 customers with different PANs:
    - Customer 1: Deductor AWQPM0067K, Deductee AAAPB1234C, Buyer Name: 'SOUMYA S'
    - Customer 2: Deductor AWQPM0067K, Deductee BBBPB5678D, Buyer Name: 'SOUMYA S' (same buyer name!)
    - Customer 3: Deductor AWQPM0067K, Deductee CCCPB9012E, Buyer Name: 'SOUMYA S' (same buyer name!)
    All 3 filings MUST be imported and displayed in Section A because duplicate detection
    is strictly based on PAN values, never on customer/buyer names.
    """
    three_customers = [
        {
            "login_pan": "AWQPM0067K",
            "login_pwd": "Password@1",
            "deductor_pan": "AWQPM0067K",
            "buyer_name": "SOUMYA S",
            "seller_pan": "AAAPB1234C",
            "deductee_pan": "AAAPB1234C",
            "amount": 5000000
        },
        {
            "login_pan": "AWQPM0067K",
            "login_pwd": "Password@1",
            "deductor_pan": "AWQPM0067K",
            "buyer_name": "SOUMYA S",  # SAME buyer name!
            "seller_pan": "BBBPB5678D",
            "deductee_pan": "BBBPB5678D",
            "amount": 6000000
        },
        {
            "login_pan": "AWQPM0067K",
            "login_pwd": "Password@1",
            "deductor_pan": "AWQPM0067K",
            "buyer_name": "SOUMYA S",  # SAME buyer name!
            "seller_pan": "CCCPB9012E",
            "deductee_pan": "CCCPB9012E",
            "amount": 7000000
        }
    ]

    file_bytes = create_in_memory_form141_workbook(three_customers)

    # 1. Preview
    preview_res = client.post(
        "/api/import/form141/preview",
        files={"file": ("three_customers.xlsx", io.BytesIO(file_bytes), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )
    assert preview_res.status_code == 200
    preview_data = preview_res.json()
    assert preview_data["totalCustomers"] == 3
    assert preview_data["duplicate_count"] == 0, "All 3 customers have distinct PAN pairs, so duplicate_count must be 0!"

    # 2. Confirm Import
    confirm_res = client.post(
        "/api/import/form141/confirm",
        files={"file": ("three_customers.xlsx", io.BytesIO(file_bytes), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )
    assert confirm_res.status_code == 200
    confirm_data = confirm_res.json()
    assert confirm_data["filings_created"] == 3, f"Expected 3 filings created, got {confirm_data['filings_created']}"
    assert len(confirm_data["logical_filing_ids"]) == 3
    assert len(set(confirm_data["logical_filing_ids"])) == 3, "All 3 logical filing IDs must be distinct!"

    # 3. Verify GET /api/form141/filings returns all 3 filings
    filings_res = client.get("/api/form141/filings")
    assert filings_res.status_code == 200
    all_filings = filings_res.json()["filings"]
    
    # Filter by this import
    import_id = confirm_data["import_id"]
    imported_lfs = [f for f in all_filings if f["import_id"] == import_id]
    assert len(imported_lfs) == 3, f"Section A must display all 3 filings, got {len(imported_lfs)}"
    
    # Verify each filing has distinct deductee PAN
    deductee_pans = [f["deductee_pan"] for f in imported_lfs]
    assert len(set(deductee_pans)) == 3, "All 3 filings must reflect their distinct deductee PANs!"

def test_duplicate_pan_pair_within_file_is_detected_and_deduplicated(client, test_db):
    """
    Verifies that if two customers in the same file have the EXACT same PAN pair:
    - Customer 1: Deductor AWQPM0067K, Deductee AAAPB1234C, Buyer Name: 'Buyer Alpha'
    - Customer 2: Deductor AWQPM0067K, Deductee AAAPB1234C, Buyer Name: 'Buyer Beta' (different name!)
    - Customer 3: Deductor AWQPM0067K, Deductee CCCPB9012E, Buyer Name: 'Buyer Gamma'
    Customer 2 is recognized as duplicate of Customer 1 because duplicate key is:
    normalized_deductor_pan + "|" + normalized_deductee_pan
    Names must NEVER be used to bypass duplicate detection.
    """
    customers = [
        {
            "login_pan": "AWQPM0067K",
            "login_pwd": "Password@1",
            "deductor_pan": "AWQPM0067K",
            "buyer_name": "Buyer Alpha",
            "seller_pan": "AAAPB1234C",
            "deductee_pan": "AAAPB1234C",
            "amount": 5000000
        },
        {
            "login_pan": "AWQPM0067K",
            "login_pwd": "Password@1",
            "deductor_pan": "AWQPM0067K",
            "buyer_name": "Buyer Beta (Different Name)",  # Different name, but SAME PANs!
            "seller_pan": "AAAPB1234C",
            "deductee_pan": "AAAPB1234C",
            "amount": 5000000
        },
        {
            "login_pan": "AWQPM0067K",
            "login_pwd": "Password@1",
            "deductor_pan": "AWQPM0067K",
            "buyer_name": "Buyer Gamma",
            "seller_pan": "CCCPB9012E",
            "deductee_pan": "CCCPB9012E",
            "amount": 7000000
        }
    ]

    file_bytes = create_in_memory_form141_workbook(customers)

    # 1. Preview detects duplicate PAN pair
    preview_res = client.post(
        "/api/import/form141/preview",
        files={"file": ("batch_with_duplicate.xlsx", io.BytesIO(file_bytes), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )
    assert preview_res.status_code == 200
    preview_data = preview_res.json()
    assert preview_data["totalCustomers"] == 3
    assert preview_data["duplicate_count"] == 1, "Duplicate PAN pair must be detected in preview!"

    # 2. Confirm import collapses the duplicate into 2 distinct filings
    confirm_res = client.post(
        "/api/import/form141/confirm",
        files={"file": ("batch_with_duplicate.xlsx", io.BytesIO(file_bytes), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )
    assert confirm_res.status_code == 200
    confirm_data = confirm_res.json()
    assert confirm_data["filings_created"] == 2, f"Expected 2 distinct filings, got {confirm_data['filings_created']}"
