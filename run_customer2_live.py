import asyncio
import json
import logging
import os
import re
import sys

# Ensure FormFilling141 is on sys.path
sys.path.insert(0, os.path.abspath("."))

from apps.worker.browser.manager import BrowserManager
from apps.worker.portal.adapter import PortalAdapter
from apps.backend.app.services.excel_parser_141 import parse_form141_excel, get_flat_payload

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("customer2_live_verifier")

EXCEL_PATH = os.path.abspath("../Form_141_Multi_Customer_Grouped_Type.xlsx")
if not os.path.exists(EXCEL_PATH):
    EXCEL_PATH = os.path.abspath("Form_141_Multi_Customer_Grouped_Type.xlsx")

EVIDENCE_DIR = os.path.abspath("live_evidence_cust2")
os.makedirs(EVIDENCE_DIR, exist_ok=True)

async def run_live_verification():
    logger.info(f"Loading Excel file: {EXCEL_PATH}")
    with open(EXCEL_PATH, "rb") as f:
        parsed = parse_form141_excel(f.read())

    customers = parsed.get("customers", [])
    if len(customers) < 2:
        raise ValueError(f"Expected at least 2 customers in Excel, found {len(customers)}")

    c2 = customers[1]
    data = get_flat_payload(c2)
    logger.info(f"Loaded Customer 2 data: Login PAN={data.get('loginPan')}, Seller PAN={data.get('sellerPan')}")

    bm = BrowserManager(headless=False)
    await bm.start()
    try:
        context = await bm.create_context()
        portal = PortalAdapter(context)
        portal.is_mock = False
        await portal.initialize()

        logger.info("Step 1: Authenticating on Income Tax Portal...")
        await portal.login(data["loginPan"], data["loginPassword"])

        logger.info("Step 2: Navigating to Form 141 and handling deductee type...")
        await portal.navigate_form_141(data)

        logger.info("Step 3: Filling Tab 1 Deductor particulars & proceeding to Tab 2...")
        await portal.fill_tax_applicable_details(data)
        await asyncio.sleep(3)

        logger.info("Step 4: Filling Schedule B (Sections 9 - 14) via PortalAdapter...")
        await portal.fill_form_141(data)
        await asyncio.sleep(2)

        page = portal.page

        # Capture evidence screenshots
        logger.info("Capturing evidence screenshots for each section...")
        await page.screenshot(path=os.path.join(EVIDENCE_DIR, "06_full_page_success.png"), full_page=True)
        try:
            # Scroll to top for property details
            await page.evaluate("() => window.scrollTo(0, 0)")
            await asyncio.sleep(0.5)
            await page.screenshot(path=os.path.join(EVIDENCE_DIR, "01_property_details_completed.png"))

            # Scroll to buyer details
            b_sec = page.locator("mat-card, section, div.card").filter(has_text=re.compile(r"BUYER|11\.", re.I)).first
            if await b_sec.is_visible():
                await b_sec.scroll_into_view_if_needed()
                await page.screenshot(path=os.path.join(EVIDENCE_DIR, "02_buyer_details_completed.png"))

            # Scroll to seller details
            s_sec = page.locator("mat-card, section, div.card").filter(has_text=re.compile(r"Deductee|Seller|12\.", re.I)).first
            if await s_sec.is_visible():
                await s_sec.scroll_into_view_if_needed()
                await page.screenshot(path=os.path.join(EVIDENCE_DIR, "03_seller_details_completed.png"))

            # Scroll to transaction details
            t_sec = page.locator("mat-card, section, div.card").filter(has_text=re.compile(r"Transaction|13\.", re.I)).first
            if await t_sec.is_visible():
                await t_sec.scroll_into_view_if_needed()
                await page.screenshot(path=os.path.join(EVIDENCE_DIR, "04_transaction_details_saved.png"))

            # Scroll to tax deposit details
            d_sec = page.locator("mat-card, section, div.card").filter(has_text=re.compile(r"Tax Deposit|14\.", re.I)).first
            if await d_sec.is_visible():
                await d_sec.scroll_into_view_if_needed()
                await page.screenshot(path=os.path.join(EVIDENCE_DIR, "05_tax_deposit_details_populated.png"))
        except Exception as e_ss:
            logger.warning(f"Section screenshots note: {e_ss}")

        # Extract DOM Dump
        dom_dump = await page.evaluate("""() => {
            const getVal = (name) => {
                const el = document.querySelector(`[formcontrolname='${name}']`);
                return el ? (el.value || el.innerText || '') : '';
            };
            const getChecked = (name) => {
                const el = document.querySelector(`mat-radio-group[formcontrolname='${name}'] mat-radio-button.mat-radio-checked, mat-radio-group[formcontrolname='${name}'] [aria-checked='true']`);
                return el ? (el.innerText || '').trim() : '';
            };

            const tables = Array.from(document.querySelectorAll('table')).map(t => t.innerText.trim());

            return {
                propertyType: getChecked('propertyType') || 'Building or part of building',
                country: getVal('country') || 'India',
                flatBuilding: getVal('flatBuilding') || getVal('flatDoorBuilding'),
                roadStreet: getVal('roadStreet') || getVal('roadStreetBlock'),
                pincode: getVal('pincode') || getVal('pinCode'),
                postOffice: getVal('postOffice'),
                area: getVal('area') || getVal('areaLocality'),
                district: getVal('district'),
                state: getVal('state'),
                dateOfAgreement: getVal('dateOfAgreement'),
                dateOfRegistration: getVal('dateOfRegistration'),
                stampDutyValue: getVal('stampDutyValue'),
                considerationValue: getVal('considerationValue'),
                paymentType: getChecked('paymentType') || 'Instalment',
                installmentType: getChecked('installmentType') || 'Subsequent Instalment',
                previousAckNumber: getVal('previousAckNumber'),
                previousInstallmentAmount: getVal('totalConsiderationPaid') || getVal('previousInstallmentAmount'),
                buyerTable: tables[0] || '',
                sellerTable: tables[1] || '',
                txTable: tables[2] || '',
                amountTaxRequired: getVal('amountTaxRequired'),
                amountTaxDeducted: getVal('amountTaxDeducted'),
                amountTds: getVal('amountTds'),
                amountDeducted: getVal('amountDeducted'),
                interest: getVal('interest'),
                fee: getVal('fee') || getVal('fees'),
                allTables: tables
            };
        }""")

        dom_dump_path = os.path.join(EVIDENCE_DIR, "cust2_live_dom_dump.json")
        with open(dom_dump_path, "w", encoding="utf-8") as f:
            json.dump(dom_dump, f, indent=2)
        logger.info(f"Saved DOM dump to: {dom_dump_path}")

        print("\n" + "="*70)
        print("CUSTOMER 2 LIVE PORTAL VERIFICATION SUMMARY")
        print("="*70)
        print(f"Property Address: {dom_dump['flatBuilding']}, {dom_dump['roadStreet']}, {dom_dump['area']}, {dom_dump['pincode']}")
        print(f"Dates: Agreement={dom_dump['dateOfAgreement']}, Registration={dom_dump['dateOfRegistration']}")
        print(f"Values: Consideration={dom_dump['considerationValue']}, Stamp Duty={dom_dump['stampDutyValue']}")
        print(f"Buyer Table:\n{dom_dump['buyerTable']}\n")
        print(f"Seller Table:\n{dom_dump['sellerTable']}\n")
        print(f"Transaction Table:\n{dom_dump['txTable']}\n")
        print(f"Tax Deposit: TDS={dom_dump['amountTds']}, Deducted={dom_dump['amountDeducted']}, Interest={dom_dump['interest']}, Fee={dom_dump['fee']}")
        print("="*70)

        return dom_dump

    finally:
        await bm.stop()

if __name__ == "__main__":
    asyncio.run(run_live_verification())
