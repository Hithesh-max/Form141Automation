import pytest
import os
import re
from apps.backend.app.services.excel_parser_141 import parse_form141_excel, get_flat_payload
from apps.worker.browser.manager import BrowserManager
from apps.worker.portal.adapter import PortalAdapter, PortalStateUnexpectedException

EXCEL_PATH = (
    os.path.join(os.getcwd(), "Form_141_Multi_Customer_Grouped_Type.xlsx")
    if os.path.exists("Form_141_Multi_Customer_Grouped_Type.xlsx")
    else os.path.join(os.path.dirname(__file__), "..", "..", "Form_141_Multi_Customer_Grouped_Type.xlsx")
)


def test_multicustomer_excel_parsing_schedule_b():
    """
    Verifies that parse_form141_excel extracts all Schedule B fields correctly
    for Customer 1 and Customer 2 from the Excel workbook, including fallbacks and normalization.
    """
    assert os.path.exists(EXCEL_PATH), f"Excel file not found at {EXCEL_PATH}"
    with open(EXCEL_PATH, "rb") as f:
        data_bytes = f.read()

    result = parse_form141_excel(data_bytes)
    assert result["worksheet"] == "Form 141 Multi Customer"
    assert result["totalCustomers"] >= 2

    # Customer 1 Checks (from Excel Column D)
    c1 = result["customers"][0]
    payload1 = get_flat_payload(c1)

    assert payload1.get("loginPan") == "AWQPM0067K"
    assert "Schedule B" in payload1.get("natureOfTransaction")
    assert payload1.get("propertyType") == "Building or part of building"
    assert payload1.get("flatBuilding") == "PARK A G123"
    assert payload1.get("roadStreet") == "POKHRAN ROAD NO 1"
    assert payload1.get("pincode") == "400606"
    assert payload1.get("postOffice") == "Jekegram S.O"
    assert payload1.get("area") == "Thane"
    assert payload1.get("district") == "THANE"
    assert payload1.get("state") == "MAHARASHTRA"
    assert payload1.get("dateOfAgreement") == "2026-08-01"
    assert payload1.get("dateOfRegistration") == "2026-08-01"
    assert payload1.get("saleConsideration") == "7000000"
    assert payload1.get("stampDutyValue") == "6000000"
    assert payload1.get("buyerPan") == "AWQPM0067K"
    assert payload1.get("buyerProportion") == "100"
    assert payload1.get("sellerPan") == "AAAPB1234C"
    assert payload1.get("sellerName") == "SUNIL SHARMA"
    assert payload1.get("sellerProportion") == "100"
    # Fallback from Row 32 to Row 43 (Column D Previous Installment Amount)
    assert payload1.get("previousInstallmentAmountTransaction") == "1000000"
    assert payload1.get("amountPaidPresent") == "500000"
    # Rate normalized from 0.01 to 1%
    assert payload1.get("tdsRatePercent") == "1"
    assert float(payload1.get("tdsAmount")) == 5000.0

    # Customer 2 Checks (from Excel Column E)
    c2 = result["customers"][1]
    payload2 = get_flat_payload(c2)
    assert payload2.get("loginPan") == "CMKPD4877Q"
    assert payload2.get("buyerPan") == "CMKPD4877Q"
    assert payload2.get("sellerPan") == "AAAPB1234C"
    assert payload2.get("propertyType") == "Building or part of building"
    assert payload2.get("pincode") == "400606"
    assert payload2.get("saleConsideration") == "7000000"
    assert payload2.get("tdsRatePercent") == "1"
    assert float(payload2.get("tdsAmount")) == 5000.0


@pytest.mark.asyncio
async def test_dependent_address_dropdown_sequencing():
    """
    Verifies that _fill_pin_postoffice_area executes the dependent sequence:
    PIN -> blur -> wait -> Post Office -> Area -> District & State, and verifies in DOM.
    """
    browser_manager = BrowserManager(headless=True)
    await browser_manager.start()
    try:
        context = await browser_manager.create_context()
        portal = PortalAdapter(context)
        await portal.initialize()
        portal.is_mock = False

        await portal.page.set_content("""
        <html><body>
          <input formcontrolname="pincode" />
          <mat-select formcontrolname="postOffice"><span class="mat-select-value-text">Select PO</span></mat-select>
          <mat-select formcontrolname="area"><span class="mat-select-value-text">Select Area</span></mat-select>
          <mat-select formcontrolname="district"><span class="mat-select-value-text">Select District</span></mat-select>
          <input formcontrolname="state" />
        </body></html>
        """)

        data = {
            "pincode": "560037",
            "postOffice": "Marathahalli PO",
            "area": "Marathahalli",
            "district": "Bengaluru Urban",
            "state": "KARNATAKA"
        }

        await portal._fill_pin_postoffice_area(
            pincode=data["pincode"],
            post_office=data["postOffice"],
            area=data["area"],
            district=data["district"],
            state=data["state"],
            raw_data=data
        )

        pin_dom = await portal.page.locator("input[formcontrolname='pincode']").input_value()
        po_dom = await portal.page.locator("mat-select[formcontrolname='postOffice']").inner_text()
        area_dom = await portal.page.locator("mat-select[formcontrolname='area']").inner_text()
        state_dom = await portal.page.locator("input[formcontrolname='state']").input_value()

        assert pin_dom == "560037"
        assert "Marathahalli PO" in po_dom
        assert "Marathahalli" in area_dom
        assert state_dom == "KARNATAKA"

        await context.close()
    finally:
        await browser_manager.stop()


@pytest.mark.asyncio
async def test_section_11_buyer_share_modal():
    """
    Verifies Section 11 Buyer Share:
    Locates buyer row, edits proportion to 100%, saves, and confirms 100% in DOM.
    """
    browser_manager = BrowserManager(headless=True)
    await browser_manager.start()
    try:
        context = await browser_manager.create_context()
        portal = PortalAdapter(context)
        await portal.initialize()
        portal.is_mock = False

        await portal.page.set_content("""
        <html><body>
          <div id="section11-buyers">
            <h3>11. Buyer Details</h3>
            <table>
              <tbody>
                <tr>
                  <td><input type="checkbox" /></td>
                  <td>ABCDE1234F</td>
                  <td>John Doe</td>
                  <td id="cell-buyer-prop">0%</td>
                </tr>
              </tbody>
            </table>
            <button id="edit-buyer">Edit</button>
          </div>
        </body></html>
        """)

        data = {
            "buyerPan": "ABCDE1234F",
            "buyerProportion": "100"
        }

        await portal._handle_buyer_share_modal(data)

        buyer_txt = await portal.page.locator("#section11-buyers").inner_text()
        assert "100%" in buyer_txt
        assert "ABCDE1234F" in buyer_txt

        await context.close()
    finally:
        await browser_manager.stop()


@pytest.mark.asyncio
async def test_section_12_seller_details_modal_and_verification():
    """
    Verifies Section 12 Seller Details:
    Clicks section-scoped Add Details, inputs PAN, checks Name auto-population, sets Proportion (100%),
    and verifies row in DOM table.
    """
    browser_manager = BrowserManager(headless=True)
    await browser_manager.start()
    try:
        context = await browser_manager.create_context()
        portal = PortalAdapter(context)
        await portal.initialize()
        portal.is_mock = False

        await portal.page.set_content("""
        <html><body>
          <div id="section12-sellers">
            <h3>12. SELLER DETAILS</h3>
            <table id="tbl-sellers">
              <thead><tr><th>Sr</th><th>PAN</th><th>Name</th><th>Share</th></tr></thead>
              <tbody></tbody>
            </table>
            <button id="add-seller">+ Add Details</button>
          </div>
        </body></html>
        """)

        data = {
            "sellerPan": "XYZAB9876C",
            "sellerName": "Jane Smith",
            "sellerProportion": "100"
        }

        await portal._handle_seller_details_modal(data)

        seller_txt = await portal.page.locator("#section12-sellers").inner_text()
        assert "XYZAB9876C" in seller_txt
        assert "Jane Smith" in seller_txt
        assert "100%" in seller_txt

        await context.close()
    finally:
        await browser_manager.stop()


@pytest.mark.asyncio
async def test_section_13_transaction_details_columns_a_through_k():
    """
    Verifies Section 13 Transaction Details Columns A through K:
    Clicks section-scoped Add Details, selects seller PAN (A), name auto-population (B),
    proportionate SDV (C), previous installment amount (D), present amount (E),
    taxable amount (F), Section 395 No (G), Cert empty (H), rate 1% (I),
    TDS amount (J), deduction date (K), and verifies row in DOM table.
    """
    browser_manager = BrowserManager(headless=True)
    await browser_manager.start()
    try:
        context = await browser_manager.create_context()
        portal = PortalAdapter(context)
        await portal.initialize()
        portal.is_mock = False

        await portal.page.set_content("""
        <html><body>
          <div id="section13-transactions">
            <h3>13. TRANSACTION DETAILS</h3>
            <table id="tbl-transactions">
              <thead><tr><th>Sr</th><th>PAN</th><th>Name</th><th>Amount</th><th>Rate</th><th>TDS</th><th>Date</th></tr></thead>
              <tbody></tbody>
            </table>
            <button id="add-tx">+ Add Details</button>
          </div>
        </body></html>
        """)

        data = {
            "sellerPan": "XYZAB9876C",
            "sellerName": "Jane Smith",
            "stampDutyValue": "8500000",
            "previousInstallmentAmountTransaction": "1000000",
            "amountPaidPresent": "8500000",
            "tdsRatePercent": "1",
            "tdsAmount": "85000",
            "dateOfDeduction": "2026-06-01"
        }

        await portal._handle_transaction_details_modal(data)

        tx_txt = await portal.page.locator("#section13-transactions").inner_text()
        assert "XYZAB9876C" in tx_txt
        assert "8500000" in tx_txt
        assert "85000" in tx_txt
        assert "1%" in tx_txt

        await context.close()
    finally:
        await browser_manager.stop()


@pytest.mark.asyncio
async def test_section_14_tax_deposit_verification_and_fill():
    """
    Verifies Section 14 Tax Deposit Details:
    Populates both amountTds and amountDeducted, fills interest=0 and fee=0,
    and checks that 0 or blank amount raises validation failure.
    """
    browser_manager = BrowserManager(headless=True)
    await browser_manager.start()
    try:
        context = await browser_manager.create_context()
        portal = PortalAdapter(context)
        await portal.initialize()
        portal.is_mock = False

        await portal.page.set_content("""
        <html><body>
          <div id="section14-tax">
            <h3>14. Tax Deposit Details</h3>
            <input formcontrolname="amountTds" />
            <input formcontrolname="amountDeducted" />
            <input formcontrolname="interest" />
            <input formcontrolname="fee" />
          </div>
        </body></html>
        """)

        valid_data = {
            "amountPaidPresent": "8500000",
            "tdsAmount": "85000",
            "amountDeducted": "85000",
            "interest": "0",
            "fee": "0"
        }

        res = await portal._verify_and_fill_tax_deposit(valid_data)
        assert res is True

        tds_val = await portal.page.locator("input[formcontrolname='amountTds']").input_value()
        ded_val = await portal.page.locator("input[formcontrolname='amountDeducted']").input_value()
        int_val = await portal.page.locator("input[formcontrolname='interest']").input_value()
        fee_val = await portal.page.locator("input[formcontrolname='fee']").input_value()

        assert tds_val == "85000"
        assert ded_val == "85000"
        assert int_val == "0"
        assert fee_val == "0"

        # Now test failure case when TDS amount remains 0/blank in DOM despite transaction data
        await portal.page.set_content("""
        <html><body>
          <div id="section14-tax">
            <input formcontrolname="amountTds" value="0" readonly />
            <input formcontrolname="amountDeducted" value="0" readonly />
          </div>
        </body></html>
        """)
        bad_data = {
            "amountPaidPresent": "8500000",
            "tdsAmount": "85000",
            "amountDeducted": "85000"
        }
        res_bad = await portal._verify_and_fill_tax_deposit(bad_data)
        assert res_bad is False

        await context.close()
    finally:
        await browser_manager.stop()


@pytest.mark.asyncio
async def test_verification_helpers_and_diagnostic_logging():
    """
    Verifies that DOM verification helpers and log_diagnostic function as expected.
    """
    browser_manager = BrowserManager(headless=True)
    await browser_manager.start()
    try:
        context = await browser_manager.create_context()
        portal = PortalAdapter(context)
        await portal.initialize()
        portal.is_mock = False

        await portal.page.set_content("""
        <html><body>
          <input id="test-inp" value="8500000" />
          <input type="checkbox" id="test-chk" checked />
          <mat-select id="test-sel"><span class="mat-select-value-text">KARNATAKA</span></mat-select>
          <table id="test-tbl">
            <tbody><tr><td>XYZAB9876C</td><td>Jane Smith</td><td>100%</td></tr></tbody>
          </table>
        </body></html>
        """)

        # 1. verify_field_value
        assert await portal.verify_field_value("#test-inp", "8500000") is True
        assert await portal.verify_field_value("#test-inp", "9999999") is False

        # 2. verify_selected_option
        assert await portal.verify_selected_option("#test-sel", "KARNATAKA") is True
        assert await portal.verify_selected_option("#test-sel", "MAHARASHTRA") is False

        # 3. verify_checked
        assert await portal.verify_checked("#test-chk", True) is True
        assert await portal.verify_checked("#test-chk", False) is False

        # 4. verify_table_row
        assert await portal.verify_table_row("#test-tbl", ["XYZAB9876C", "Jane Smith", "100%"]) is True
        assert await portal.verify_table_row("#test-tbl", ["UNKNOWN_PAN"]) is False

        # 5. verify_calculated_value
        assert portal.verify_calculated_value(85000, 85000) is True
        assert portal.verify_calculated_value("85000", 85000.0) is True
        assert portal.verify_calculated_value("85000", 80000) is False

        # 6. log_diagnostic should not raise errors
        portal.log_diagnostic(
            field_name="Test Field",
            excel_val="100",
            parser_val="100",
            payload_val="100",
            adapter_val="100",
            locator_found=True,
            fill_status="SUCCESS",
            dom_after_fill="100",
            verify_status="PASS"
        )

        await context.close()
    finally:
        await browser_manager.stop()
