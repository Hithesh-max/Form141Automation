import pytest
import os
import io
import json
from fastapi.testclient import TestClient
from apps.backend.app.main import app
from apps.backend.app.services.excel_parser_141 import parse_form141_excel, get_flat_payload
from apps.backend.app.services.validator import data_validator
from apps.backend.app.database.config import get_db

client = TestClient(app)

EXCEL_PATH = r"c:\Users\MAHE\Desktop\income-tax-antigravity\Form_141_Multi_Customer_Grouped_Type.xlsx"

def test_parse_form141_excel_with_real_file():
    assert os.path.exists(EXCEL_PATH), f"Excel file not found at {EXCEL_PATH}"
    with open(EXCEL_PATH, "rb") as f:
        file_bytes = f.read()

    parsed = parse_form141_excel(file_bytes)
    assert parsed["formType"] == "FORM_141"
    assert parsed["totalCustomers"] >= 1
    assert len(parsed["customers"]) >= 1

    cust1 = parsed["customers"][0]
    assert cust1["customerIndex"] == 1
    assert cust1["customerLabel"] == "Customer 1"

    # Check sections exist
    assert "login" in cust1
    assert "basicDetails" in cust1
    assert "immovablePropertyDetails" in cust1
    assert "buyerDeductorDetails" in cust1
    assert "sellerDeducteeDetails" in cust1
    assert "transactionDetails" in cust1
    assert "taxDepositDetails" in cust1
    assert "paymentDetails" in cust1

    # Check flat payload conversion
    flat = get_flat_payload(cust1)
    assert "_fieldMetadata" in flat
    assert "_loginPan" in flat
    assert "_loginPassword" in flat
    assert "deductorPan" in flat
    assert "sellerPan" in flat


def test_validator_form141_customer():
    # Valid customer
    valid_customer = {
        "customerIndex": 1,
        "login": {
            "loginPan": {"value": "ABCDE1234F", "fetchType": "Manual", "fieldLabel": "Login PAN"},
            "loginPassword": {"value": "Secret@123", "fetchType": "Manual", "fieldLabel": "Login Password"}
        },
        "basicDetails": {
            "deductorPan": {"value": "ABCDE1234F", "fetchType": "Manual", "fieldLabel": "Deductor PAN"},
            "deducteeType": {"value": "Company", "fetchType": "Select", "fieldLabel": "Deductee Type"},
            "residentialStatus": {"value": "Resident", "fetchType": "Select", "fieldLabel": "Residential Status"},
            "taxYear": {"value": "2024", "fetchType": "Select", "fieldLabel": "Tax Year"},
            "monthOfDeduction": {"value": "April", "fetchType": "Select", "fieldLabel": "Month of Deduction"},
            "natureOfTransaction": {"value": "Purchase of Land", "fetchType": "Select", "fieldLabel": "Nature of Transaction"}
        },
        "immovablePropertyDetails": {
            "propertyType": {"value": "Land", "fetchType": "Select", "fieldLabel": "Type of Immovable Property"},
            "flatDoorBuilding": {"value": "101", "fetchType": "Manual", "fieldLabel": "Flat / Door / Building"},
            "pinCode": {"value": "560001", "fetchType": "Manual", "fieldLabel": "PIN Code"},
            "stampDutyValue": {"value": "5000000", "fetchType": "Manual", "fieldLabel": "Total Stamp Duty Value of Property"},
            "saleConsideration": {"value": "5500000", "fetchType": "Manual", "fieldLabel": "Total Sale Consideration in respect of the Property"},
            "paymentLumpsumOrInstalment": {"value": "Lumpsum", "fetchType": "Select", "fieldLabel": "Type of Payment: Lumpsum or Instalments"}
        },
        "buyerDeductorDetails": {
            "buyerPan": {"value": "ABCDE1234F", "fetchType": "Manual", "fieldLabel": "Buyer's PAN"},
            "buyerName": {"value": "John Doe", "fetchType": "Manual", "fieldLabel": "Buyer's Name"},
            "buyerProportion": {"value": "100", "fetchType": "Manual", "fieldLabel": "Buyer's Proportion"}
        },
        "sellerDeducteeDetails": {
            "sellerPan": {"value": "XYZPK9876M", "fetchType": "Manual", "fieldLabel": "Seller's PAN"},
            "sellerProportion": {"value": "100", "fetchType": "Manual", "fieldLabel": "Seller's Proportion"}
        },
        "transactionDetails": {
            "deducteePan": {"value": "XYZPK9876M", "fetchType": "Manual", "fieldLabel": "PAN of the Deductee"},
            "amountPaidPresent": {"value": "5500000", "fetchType": "Manual", "fieldLabel": "Amount Paid/Credited in Present Transaction"},
            "dateOfPayment": {"value": "2024-04-15", "fetchType": "Manual", "fieldLabel": "Date of Payment/Credit"},
            "section395Applicable": {"value": "No", "fetchType": "Select", "fieldLabel": "Whether Section 395(1) Applicable"},
            "dateOfDeduction": {"value": "2024-04-15", "fetchType": "Manual", "fieldLabel": "Date of Deduction"}
        },
        "taxDepositDetails": {
            "interest": {"value": "0", "fetchType": "Manual", "fieldLabel": "Interest"},
            "fees": {"value": "0", "fetchType": "Manual", "fieldLabel": "Fees"}
        },
        "paymentDetails": {
            "typeOfPayment": {"value": "Net Banking", "fetchType": "Select", "fieldLabel": "Type of Payment"}
        }
    }

    res = data_validator.validate_form141_customer(valid_customer, 1)
    assert res["status"] == "READY"
    assert len(res["errors"]) == 0

    # Invalid PAN check
    invalid_cust = json.loads(json.dumps(valid_customer))
    invalid_cust["login"]["loginPan"]["value"] = "INVALID_PAN"
    res_err = data_validator.validate_form141_customer(invalid_cust, 1)
    assert res_err["status"] in ("ERROR", "INVALID")
    assert any(e["field"] == "loginPan" for e in res_err["errors"])


def test_form141_preview_api_endpoint():
    with open(EXCEL_PATH, "rb") as f:
        file_bytes = f.read()

    response = client.post(
        "/api/import/form141/preview",
        files={"file": ("Form_141_Multi_Customer_Grouped_Type.xlsx", io.BytesIO(file_bytes), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["totalCustomers"] >= 1
    assert "readyCount" in data
    assert "warningCount" in data
    assert "errorCount" in data
    assert len(data["customers"]) >= 1


def test_form141_confirm_api_endpoint(client):
    with open(EXCEL_PATH, "rb") as f:
        file_bytes = f.read()

    response = client.post(
        "/api/import/form141/confirm",
        files={"file": ("Form_141_Multi_Customer_Grouped_Type.xlsx", io.BytesIO(file_bytes), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"selectedIndices": json.dumps([1])}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["jobs_created"] == 1
    assert data["selectedCount"] == 1
