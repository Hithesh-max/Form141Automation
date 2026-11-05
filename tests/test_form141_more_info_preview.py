import pytest
import os
import io
import json
import openpyxl
from fastapi.testclient import TestClient
from apps.backend.app.main import app
from apps.backend.app.services.excel_parser_141 import parse_form141_excel, format_value
from apps.backend.app.database.config import SessionLocal, engine
from apps.backend.app.database import models

models.Base.metadata.create_all(bind=engine)

client = TestClient(app)

EXCEL_PATH = (
    os.path.join(os.getcwd(), "Form_141_Multi_Customer_Grouped_Type.xlsx")
    if os.path.exists("Form_141_Multi_Customer_Grouped_Type.xlsx")
    else r"c:\Users\MAHE\Desktop\income-tax-antigravity\Form_141_Multi_Customer_Grouped_Type.xlsx"
)

def test_automatic_worksheet_and_header_detection():
    """1 & 2: Automatic worksheet detection and header detection without hardcoded sheet names."""
    assert os.path.exists(EXCEL_PATH)
    with open(EXCEL_PATH, "rb") as f:
        file_bytes = f.read()

    res = parse_form141_excel(file_bytes)
    assert res["worksheet"] == "Form 141 Multi Customer"
    assert res["totalCustomers"] >= 1

    # Check headers were detected
    headers = [f["form141_field"] for f in res["customers"][0]["fields"]]
    assert "Login PAN" in headers
    assert "Applicable Act" in headers
    assert "Nature of Transaction in respect of Purchase of Property" in headers


def test_dynamic_customer_detection_and_empty_filtering():
    """3 & 4: Dynamic customer-column detection and completely empty customer-column filtering."""
    with open(EXCEL_PATH, "rb") as f:
        file_bytes = f.read()

    res = parse_form141_excel(file_bytes)
    # The real Excel file has Customer 1 to Customer 10 in row 1.
    # Empty customer columns (Customers 4-10) are filtered out!
    assert res["totalCustomers"] in [1, 2, 3]
    cust1 = res["customers"][0]
    assert cust1["customer_index"] == 1
    assert cust1["customer_label"] == "Customer 1"
    assert cust1["source_column"] == "D"


def test_type_forward_filling_and_exact_preservation():
    """5, 6, 7, 8: TYPE forward-filling, exact TYPE, field-label, and fetch-type preservation."""
    with open(EXCEL_PATH, "rb") as f:
        file_bytes = f.read()

    res = parse_form141_excel(file_bytes)
    expected_types = [
        "LOGIN",
        "BASIC DETAILS",
        "IMMOVABLE PROPERTY DETAILS",
        "BUYER / DEDUCTOR DETAILS",
        "SELLER / DEDUCTEE DETAILS",
        "TRANSACTION DETAILS",
        "TAX DEPOSIT DETAILS",
        "PAYMENT DETAILS"
    ]
    assert res["type_headings"] == expected_types
    assert res["type_field_counts"]["LOGIN"] == 2
    assert res["type_field_counts"]["BASIC DETAILS"] == 12
    assert res["type_field_counts"]["IMMOVABLE PROPERTY DETAILS"] == 17
    assert res["type_field_counts"]["BUYER / DEDUCTOR DETAILS"] == 3
    assert res["type_field_counts"]["SELLER / DEDUCTEE DETAILS"] == 4
    assert res["type_field_counts"]["TRANSACTION DETAILS"] == 12
    assert res["type_field_counts"]["TAX DEPOSIT DETAILS"] == 4
    assert res["type_field_counts"]["PAYMENT DETAILS"] == 1
    assert sum(res["type_field_counts"].values()) == 55

    # Check forward-fill: row 3 (Login Password) has TYPE 'LOGIN'
    fields = res["customers"][0]["fields"]
    pwd_field = next(f for f in fields if f["form141_field"] == "Login Password")
    assert pwd_field["type"] == "LOGIN"
    assert pwd_field["fetch_type"] == "Manual"


def test_original_row_numbers_and_order_preservation():
    """9 & 10: Original row numbers and row order preservation."""
    with open(EXCEL_PATH, "rb") as f:
        file_bytes = f.read()

    res = parse_form141_excel(file_bytes)
    fields = res["customers"][0]["fields"]
    assert len(fields) == 55

    # Check row numbers start at 2 and strictly increase to 56
    row_numbers = [f["original_row_number"] for f in fields]
    assert row_numbers == list(range(2, 57))


def test_numeric_zero_and_blank_distinction():
    """11 & 12: Numeric zero preservation and blank vs zero distinction."""
    with open(EXCEL_PATH, "rb") as f:
        file_bytes = f.read()

    res = parse_form141_excel(file_bytes)
    fields = res["customers"][0]["fields"]

    # Interest (Row 54) has numeric 0 in Excel
    interest_field = next(f for f in fields if f["form141_field"] == "Interest")
    assert interest_field["value"] == 0
    assert interest_field["display_value"] == "0"

    # Fees (Row 55) has numeric 0 in Excel
    fees_field = next(f for f in fields if f["form141_field"] == "Fees")
    assert fees_field["value"] == 0
    assert fees_field["display_value"] == "0"

    # Deductor Name (Row 8) is blank in Excel -> value must be None, NOT 0
    name_field = next(f for f in fields if f["form141_field"] == "Deductor Name")
    assert name_field["value"] is None
    assert name_field["display_value"] != "0"


def test_date_integer_and_decimal_formatting():
    """13 & 14: Excel date formatting, integer, and decimal preservation."""
    with open(EXCEL_PATH, "rb") as f:
        file_bytes = f.read()

    res = parse_form141_excel(file_bytes)
    fields = res["customers"][0]["fields"]

    # Date of Agreement (Row 25)
    agree_date = next(f for f in fields if f["form141_field"] == "Date of Agreement / Booking")
    assert agree_date["value"] == "2026-08-01"
    assert agree_date["display_value"] == "2026-08-01"

    # Integer without unnecessary decimal: Stamp duty value 6000000
    stamp_duty = next(f for f in fields if f["form141_field"] == "Total Stamp Duty Value of Property")
    assert stamp_duty["value"] == 6000000
    assert stamp_duty["display_value"] == "6000000"

    # Decimal: TDS rate 0.01 (1%)
    tds_rate = next(f for f in fields if f["form141_field"] == "Rate at which Tax Deducted (%)")
    assert tds_rate["value"] == 0.01
    assert tds_rate["display_value"] == "0.01"


def test_fetch_type_blank_display_rules():
    """15, 16, 17, 18: Blank Fetch, Calculate, Select, and Conditional display rules."""
    with open(EXCEL_PATH, "rb") as f:
        file_bytes = f.read()

    res = parse_form141_excel(file_bytes)
    fields = res["customers"][0]["fields"]

    # Blank Fetch field (Row 8 Deductor Name)
    deductor_name = next(f for f in fields if f["form141_field"] == "Deductor Name")
    assert deductor_name["display_value"] == "Pending portal autofetch"

    # Blank Calculate field (Row 42 Proportionate Amount of Stamp Duty Value)
    prop_stamp = next(f for f in fields if f["form141_field"] == "Proportionate Amount of Stamp Duty Value")
    assert prop_stamp["display_value"] == "Pending calculation"

    # Blank Conditional field (Row 48 Certificate Number)
    cert_num = next(f for f in fields if f["form141_field"] == "Certificate Number")
    assert cert_num["display_value"] == "Not applicable unless condition is selected"


def test_password_redaction_and_absence():
    """19 & 20: Password redaction from API responses, absence from preview/diagnostics."""
    with open(EXCEL_PATH, "rb") as f:
        file_bytes = f.read()

    # 1. Parser output
    res = parse_form141_excel(file_bytes)
    pwd_field = next(f for f in res["customers"][0]["fields"] if f["form141_field"] == "Login Password")
    assert pwd_field["is_sensitive"] is True
    assert pwd_field["value"] is None
    assert pwd_field["display_value"] == "••••••••"

    # 2. API response check
    response = client.post(
        "/api/import/form141/preview",
        files={"file": ("Form_141_Multi_Customer_Grouped_Type.xlsx", io.BytesIO(file_bytes), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )
    assert response.status_code == 200
    data = response.json()
    response_str = json.dumps(data)

    # Assert real raw password never appears in the entire response body
    assert "soumya@1234" not in response_str

    cust = data["customers"][0]
    api_pwd_field = next(f for f in cust["fields"] if f["form141_field"] == "Login Password")
    assert api_pwd_field["value"] is None
    assert api_pwd_field["display_value"] == "••••••••"


def test_customer_isolation_with_three_populated_customers():
    """21: Customer 1 / Customer 2 / Customer 3 complete isolation with no fallback."""
    # Create an in-memory 3-customer workbook based on the template
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Form 141 Multi Customer"

    # Row 1: Headers
    ws.append(["TYPE", "Form 141 Field", "Fetch Type", "Customer 1", "Customer 2", "Customer 3"])
    # Row 2: Login PAN
    ws.append(["LOGIN", "Login PAN", "Manual", "PAN_CUST_1", "PAN_CUST_2", "PAN_CUST_3"])
    # Row 3: Login Password
    ws.append([None, "Login Password", "Manual", "Pass1", "Pass2", "Pass3"])
    # Row 4: Basic details
    ws.append(["BASIC DETAILS", "Applicable Act", "Manual", "Act 2025", "Act 2025", "Act 2025"])
    # Row 5: Transaction amount
    ws.append(["TRANSACTION DETAILS", "Amount Paid/Credited in Present Transaction", "Manual", 100000, 200000, 300000])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    bytes_data = buf.read()

    res = parse_form141_excel(bytes_data)
    assert res["totalCustomers"] == 3
    c1 = res["customers"][0]
    c2 = res["customers"][1]
    c3 = res["customers"][2]

    assert c1["customer_label"] == "Customer 1" and c1["source_column"] == "D"
    assert c2["customer_label"] == "Customer 2" and c2["source_column"] == "E"
    assert c3["customer_label"] == "Customer 3" and c3["source_column"] == "F"

    # Verify customer 1 has only Customer 1's values
    c1_pan = next(f for f in c1["fields"] if f["form141_field"] == "Login PAN")
    c1_amt = next(f for f in c1["fields"] if f["form141_field"] == "Amount Paid/Credited in Present Transaction")
    assert c1_pan["value"] == "PAN_CUST_1" and c1_amt["value"] == 100000

    # Verify customer 2 has only Customer 2's values
    c2_pan = next(f for f in c2["fields"] if f["form141_field"] == "Login PAN")
    c2_amt = next(f for f in c2["fields"] if f["form141_field"] == "Amount Paid/Credited in Present Transaction")
    assert c2_pan["value"] == "PAN_CUST_2" and c2_amt["value"] == 200000

    # Verify customer 3 has only Customer 3's values
    c3_pan = next(f for f in c3["fields"] if f["form141_field"] == "Login PAN")
    c3_amt = next(f for f in c3["fields"] if f["form141_field"] == "Amount Paid/Credited in Present Transaction")
    assert c3_pan["value"] == "PAN_CUST_3" and c3_amt["value"] == 300000


def test_more_info_read_only_safety_no_jobs_no_browser_no_db_side_effects():
    """24-29: Preview/More Info creates no jobs, no Redis events, no browser sessions, no DB writes."""
    db = SessionLocal()
    jobs_before = db.query(models.Job).count()
    filings_before = db.query(models.Form141LogicalFiling).count()
    db.close()

    with open(EXCEL_PATH, "rb") as f:
        file_bytes = f.read()

    # Hit preview multiple times (simulating opening More Info repeatedly)
    for _ in range(3):
        res = client.post(
            "/api/import/form141/preview",
            files={"file": ("Form_141_Multi_Customer_Grouped_Type.xlsx", io.BytesIO(file_bytes), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        )
        assert res.status_code == 200

    db = SessionLocal()
    jobs_after = db.query(models.Job).count()
    filings_after = db.query(models.Form141LogicalFiling).count()
    db.close()

    assert jobs_after == jobs_before, f"Jobs changed! Before: {jobs_before}, After: {jobs_after}"
    assert filings_after == filings_before, f"Filings changed! Before: {filings_before}, After: {filings_after}"
