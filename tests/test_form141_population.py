import pytest
import os
import asyncio
from apps.worker.browser.manager import BrowserManager
from apps.worker.portal.adapter import PortalAdapter, PortalStateUnexpectedException
from apps.backend.app.services.excel_parser_141 import get_flat_payload

@pytest.mark.asyncio
async def test_form141_flat_payload_aliases():
    """Verifies that get_flat_payload produces normalized aliases for formcontrolnames."""
    customer = {
        "customerIndex": 1,
        "customerLabel": "Test Buyer",
        "immovablePropertyDetails": {
            "flatDoorBuilding": {"value": "Flat 101, Sun Towers", "fetchType": ""},
            "roadStreetBlock": {"value": "MG Road", "fetchType": ""},
            "pinCode": {"value": "400001", "fetchType": ""},
            "areaLocality": {"value": "Fort", "fetchType": ""}
        },
        "buyerDeductorDetails": {
            "buyerPan": {"value": "ABCDE1234F", "fetchType": ""},
            "buyerName": {"value": "Test Buyer", "fetchType": ""}
        }
    }
    flat = get_flat_payload(customer)
    assert flat["flatBuilding"] == "Flat 101, Sun Towers"
    assert flat["roadStreet"] == "MG Road"
    assert flat["pincode"] == "400001"
    assert flat["area"] == "Fort"


@pytest.mark.asyncio
async def test_form141_missing_required_data_raises_exception():
    """
    Verifies that if required fields (Date of Agreement, Sale Consideration, Buyer PAN, Seller PAN)
    are missing from filing data, fill_form_141 raises PortalStateUnexpectedException identifying the missing fields.
    """
    browser_manager = BrowserManager(headless=True)
    await browser_manager.start()
    try:
        context = await browser_manager.create_context()
        portal = PortalAdapter(context)
        await portal.initialize()
        portal.is_mock = False  # Test real logic check

        incomplete_data = {
            "natureOfTransaction": "Schedule B",
            "flatBuilding": "Door 5"
            # Missing dateOfAgreement, saleConsideration, buyerPan, sellerPan
        }

        with pytest.raises(PortalStateUnexpectedException) as exc_info:
            await portal.fill_form_141(incomplete_data)

        err = str(exc_info.value)
        assert "Form 141 cannot continue" in err
        assert "Date of Agreement" in err
        assert "Total Sale Consideration" in err
        assert "Buyer PAN" in err
        assert "Seller PAN" in err

        await context.close()
    finally:
        await browser_manager.stop()


@pytest.mark.asyncio
async def test_form141_population_with_complete_mock_dom():
    """
    Verifies that _fill_schedule_b correctly interacts with Angular formcontrolname inputs,
    dynamic dropdowns, modals, and tax deposit controls when complete data is present.
    """
    browser_manager = BrowserManager(headless=True)
    await browser_manager.start()
    try:
        context = await browser_manager.create_context()
        portal = PortalAdapter(context)
        await portal.initialize()
        portal.is_mock = False

        # Render a mock DOM simulating Form 141 Tab 2 page with Angular formcontrolnames
        await portal.page.set_content("""
        <html><body>
          <h1>Form 141 (Challan-cum-statement)</h1>
          <mat-radio-group formcontrolname="propertyType">
            <mat-radio-button>Land and building both</mat-radio-button>
          </mat-radio-group>
          <input formcontrolname="flatBuilding" />
          <input formcontrolname="roadStreet" />
          <input formcontrolname="country" />
          <input formcontrolname="pincode" />
          <mat-select formcontrolname="postOffice"><span class="mat-select-value-text">Select Post Office</span></mat-select>
          <mat-select formcontrolname="area"><span class="mat-select-value-text">Select Area</span></mat-select>
          <mat-select formcontrolname="district"><span class="mat-select-value-text">Select District</span></mat-select>
          <input formcontrolname="state" />

          <input formcontrolname="dateOfAgreement" />
          <input formcontrolname="dateOfRegistration" />
          <input formcontrolname="saleConsideration" />
          <input formcontrolname="stampDuty" />

          <div class="card">
            <h3>BUYER DETAILS</h3>
            <button id="edit-buyer">Edit</button>
          </div>
          <div class="card">
            <h3>SELLER DETAILS</h3>
            <button id="add-seller">Add Details</button>
          </div>
          <div class="card">
            <h3>13. Transaction details</h3>
            <button id="add-tx">Add Details</button>
          </div>

          <input formcontrolname="amountPaidCurrently" />
          <input formcontrolname="tdsRate" />
          <input formcontrolname="amountTds" />
          <input formcontrolname="amountDeducted" />
          <input formcontrolname="interest" />
          <input formcontrolname="fee" />
        </body></html>
        """)

        complete_data = {
            "natureOfTransaction": "Schedule B",
            "propertyType": "Land and building both",
            "flatBuilding": "Flat 4B, Apex Residency",
            "roadStreet": "Sector 14, Outer Ring Road",
            "country": "INDIA",
            "pincode": "560037",
            "postOffice": "Marathahalli PO",
            "area": "Marathahalli",
            "district": "Bengaluru Urban",
            "state": "KARNATAKA",
            "dateOfAgreement": "2026-05-15",
            "dateOfRegistration": "2026-06-01",
            "saleConsideration": "8500000",
            "stampDutyValue": "8500000",
            "buyerPan": "ABCDE1234F",
            "buyerName": "John Doe",
            "buyerProportion": "100",
            "sellerPan": "XYZAB9876C",
            "sellerName": "Jane Smith",
            "sellerProportion": "100",
            "amountPaidPresent": "8500000",
            "tdsRate": "1",
            "tdsAmount": "85000",
            "amountDeducted": "85000",
            "interest": "0",
            "fee": "0"
        }

        await portal.fill_form_141(complete_data)

        # Verify values populated in DOM
        flat_val = await portal.page.locator("input[formcontrolname='flatBuilding']").input_value()
        road_val = await portal.page.locator("input[formcontrolname='roadStreet']").input_value()
        pin_val = await portal.page.locator("input[formcontrolname='pincode']").input_value()
        date_val = await portal.page.locator("input[formcontrolname='dateOfAgreement']").input_value()
        sale_val = await portal.page.locator("input[formcontrolname='saleConsideration']").input_value()
        tds_val = await portal.page.locator("input[formcontrolname='amountTds']").input_value()

        assert flat_val == "Flat 4B, Apex Residency"
        assert road_val == "Sector 14, Outer Ring Road"
        assert pin_val == "560037"
        assert date_val in ("15/05/2026", "2026-05-15", "15-May-2026")
        assert sale_val == "8500000"
        assert tds_val == "85000"

        # Verify DOM populated check passes
        is_populated = await portal.verify_form_populated(complete_data)
        assert is_populated is True

        await context.close()
    finally:
        await browser_manager.stop()
