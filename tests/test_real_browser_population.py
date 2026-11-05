import pytest
import os
import asyncio
from apps.worker.browser.manager import BrowserManager
from apps.worker.portal.adapter import PortalAdapter
from apps.backend.app.services.excel_parser_141 import parse_form141_excel, get_flat_payload

@pytest.mark.asyncio
async def test_real_browser_dom_population_verification():
    """
    Executes a real browser test using the actual imported Excel file:
    Form_141_Multi_Customer_Grouped_Type.xlsx
    
    Verifies field-by-field population:
    - Property Address: PARK A G123, POKHRAN ROAD NO 1, 400606, Jekegram S.O, Thane, THANE, MAHARASHTRA, INDIA
    - Property Dates: 2026-08-01, 2026-08-01
    - Consideration: Stamp Duty 6000000, Sale Consideration 7000000
    - Installments: Instalment, Subsequent Instalment, AB12345678, 1000000
    - Buyer: SOUMYA S, 100%
    - Seller: AAAPB1234C, SUNIL SHARMA, 100%
    - Transaction: 500000, 2026-08-28, 0.01 rate, 5000 TDS
    - Tax Deposit: Amount TDS 500000, Amount Deducted 5000, Interest 0, Fee 0
    """
    excel_path = r"C:\Users\MAHE\Downloads\income-tax\income-tax-antigravity-vps\Form_141_Multi_Customer_Grouped_Type.xlsx"
    with open(excel_path, "rb") as f:
        file_bytes = f.read()

    parsed = parse_form141_excel(file_bytes)
    customer1 = parsed["customers"][0]
    actual_filing_data = get_flat_payload(customer1)

    os.environ["PORTAL_MODE"] = "mock"

    browser_manager = BrowserManager(headless=True)
    await browser_manager.start()

    try:
        context = await browser_manager.create_context()
        portal = PortalAdapter(context)
        await portal.initialize()

        # Step 1: Particulars of Deductor
        await portal.fill_tax_applicable_details(actual_filing_data)

        # Step 2: Form 141 Schedule B & Transaction Details
        await portal.fill_form_141(actual_filing_data)

        # Verify populated DOM
        is_populated = await portal.verify_form_populated(actual_filing_data)
        assert is_populated is True, "Form 141 fields failed DOM verification!"

        await context.close()
        print("Real browser DOM population verification with actual Excel file PASSED!")
    finally:
        await browser_manager.stop()

if __name__ == "__main__":
    asyncio.run(test_real_browser_dom_population_verification())
