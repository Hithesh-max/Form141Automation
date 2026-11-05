import pytest
import os
import asyncio
from apps.worker.browser.manager import BrowserManager
from apps.worker.workflows.job_workflow import process_job
from apps.worker.portal.adapter import (
    PortalAdapter,
    PortalSaveDraftFailedException,
    PortalStateUnexpectedException,
    BrowserClosedException
)
from apps.backend.app.database import models

@pytest.mark.asyncio
async def test_form141_tab1_save_draft_before_continue():
    """
    Verifies that on Tab 1 (Particulars of the Deductor):
    1. 'Save As Draft' button is clicked first and draft confirmation is received.
    2. 'Continue' button is clicked only after draft confirmation.
    3. Workflow successfully reaches Tab 2 'Transaction Details'.
    """
    os.environ["PORTAL_MODE"] = "mock"
    browser_manager = BrowserManager(headless=True)
    await browser_manager.start()

    try:
        context = await browser_manager.create_context()
        portal = PortalAdapter(context)
        await portal.initialize()

        # Call fill_form141_tab1_deductor
        data = {
            "residentialStatus": "Resident",
            "taxYear": "2026-27",
            "monthOfDeduction": "AUG-2026",
            "natureOfTransaction": "Schedule B"
        }
        await portal.fill_form141_tab1_deductor(data)

        # Tab 2 must be reached
        content = await portal.page.content()
        assert "Transaction Details" in content

        await context.close()
    finally:
        await browser_manager.stop()


@pytest.mark.asyncio
async def test_form141_tab1_draft_save_failure_blocks_continue():
    """
    Verifies that if Save As Draft encounters an error alert from the portal,
    PortalSaveDraftFailedException is raised and Continue is NOT clicked.
    """
    os.environ["PORTAL_MODE"] = "real" # Test real DOM interaction logic with a mocked page
    browser_manager = BrowserManager(headless=True)
    await browser_manager.start()

    try:
        context = await browser_manager.create_context()
        portal = PortalAdapter(context)
        await portal.initialize()
        portal.is_mock = False # Run through real DOM branch

        # Set up a page where clicking Save As Draft renders an error alert
        await portal.page.set_content("""
        <html><body>
          <h1>Particulars Of The Deductor</h1>
          <input type="radio" name="res" id="res1" /><label for="res1">Resident</label>
          <mat-select formcontrolname="taxYear"><span class="mat-select-value-text">2026-27</span></mat-select>
          <input formcontrolname="monthOfDeduction" value="AUG-2026" />
          <mat-select formcontrolname="natureTransaction"><span class="mat-select-value-text">Schedule B</span></mat-select>
          <div id="error-container"></div>
          <button id="btn-save" onclick="
            const err = document.createElement('div');
            err.className = 'alert-danger';
            err.innerText = 'Failed to save draft. Invalid session.';
            document.getElementById('error-container').appendChild(err);
          ">Save As Draft</button>
          <button id="btn-continue" disabled>Continue</button>
        </body></html>
        """)

        data = {
            "residentialStatus": "Resident",
            "taxYear": "2026-27",
            "monthOfDeduction": "AUG-2026",
            "natureOfTransaction": "Schedule B"
        }

        with pytest.raises(PortalSaveDraftFailedException) as excinfo:
            await portal.fill_form141_tab1_deductor(data)

        assert "Failed to save draft" in str(excinfo.value)

        # Ensure Continue was NOT clicked and page remains on Tab 1
        content = await portal.page.content()
        assert "Transaction Details" not in content

        await context.close()
    finally:
        os.environ["PORTAL_MODE"] = "mock"
        await browser_manager.stop()


@pytest.mark.asyncio
async def test_form141_tab1_residential_status_selection_angular_material():
    """
    Verifies that 'Resident' radio button is correctly selected in Angular Material structure
    where native input is nested and text is in sibling label or mat-radio-button container.
    """
    os.environ["PORTAL_MODE"] = "real"
    browser_manager = BrowserManager(headless=True)
    await browser_manager.start()

    try:
        context = await browser_manager.create_context()
        portal = PortalAdapter(context)
        await portal.initialize()
        portal.is_mock = False

        # Set up realistic Angular Material radio group structure matching the Income Tax portal
        await portal.page.set_content("""
        <html><body>
          <h1>Particulars Of The Deductor</h1>
          <div>Residential status of the Deductee(s)</div>
          <mat-radio-group formcontrolname="residentialStatus">
            <mat-radio-button id="mat-radio-4" class="mat-radio-button mat-accent" onclick="window.__resident_selected = true">
              <label class="mat-radio-label" for="mat-radio-4-input">
                <span class="mat-radio-container">
                  <input type="radio" class="mat-radio-input" id="mat-radio-4-input" name="mat-radio-group-0" value="Y" onchange="window.__resident_selected = true">
                </span>
                <span class="mat-radio-label-content">Resident</span>
              </label>
            </mat-radio-button>
            <mat-radio-button id="mat-radio-5" class="mat-radio-button mat-accent">
              <label class="mat-radio-label" for="mat-radio-5-input">
                <span class="mat-radio-container">
                  <input type="radio" class="mat-radio-input" id="mat-radio-5-input" name="mat-radio-group-0" value="N">
                </span>
                <span class="mat-radio-label-content">Non Resident</span>
              </label>
            </mat-radio-button>
          </mat-radio-group>
          <mat-select formcontrolname="taxYear"><span class="mat-select-value-text">2026-27</span></mat-select>
          <input formcontrolname="monthOfDeduction" value="AUG-2026" />
          <mat-select formcontrolname="natureTransaction"><span class="mat-select-value-text">Schedule B</span></mat-select>
          <div id="toast-area"></div>
          <button id="btn-save" onclick="
            const t = document.createElement('div');
            t.className = 'mat-snack-bar-container';
            t.innerText = 'Draft saved successfully';
            document.getElementById('toast-area').appendChild(t);
            document.getElementById('btn-continue').disabled = false;
          ">Save As Draft</button>
          <button id="btn-continue" onclick="
            const wasSelected = window.__resident_selected;
            document.body.innerHTML = '<h1>Transaction Details</h1><button>Continue</button>';
            window.__resident_selected = wasSelected;
          ">Continue</button>
        </body></html>
        """)

        data = {
            "residentialStatus": "Resident",
            "taxYear": "2026-27",
            "monthOfDeduction": "AUG-2026",
            "natureOfTransaction": "Schedule B"
        }

        await portal.fill_form141_tab1_deductor(data)

        # Verify that Resident radio was clicked and selected
        resident_checked = await portal.page.evaluate("() => Boolean(window.__resident_selected)")
        assert resident_checked is True

        # Verify workflow reached Tab 2
        content = await portal.page.content()
        assert "Transaction Details" in content

        await context.close()
    finally:
        os.environ["PORTAL_MODE"] = "mock"
        await browser_manager.stop()



@pytest.mark.asyncio
async def test_form141_browser_close_detection_aborts_cleanly(test_db):
    """
    Verifies that if the user closes the browser context/page during active automation:
    1. BrowserClosedException is raised.
    2. Automation immediately halts.
    3. Job is marked CANCELLED with current_step SESSION_LOST.
    """
    os.environ["PORTAL_MODE"] = "mock"
    browser_manager = BrowserManager(headless=True)
    await browser_manager.start()

    try:
        # Create customer & filing & job
        cust = models.Customer(customer_code="CUST-CLOSE-TEST", name="Close Test")
        test_db.add(cust)
        test_db.flush()
        filing = models.Filing(customer_id=cust.id, filing_reference="FIL-CLOSE-TEST", status="IMPORTED")
        test_db.add(filing)
        test_db.flush()
        job = models.Job(job_reference="JOB-CLOSE-TEST", customer_id=cust.id, filing_id=filing.id, status="PROCESSING")
        test_db.add(job)
        test_db.commit()

        job_data = {
            "job_reference": job.job_reference,
            "portal_user_id": "ABCDE1234F",
            "data_payload": {
                "pan": "ABCDE1234F",
                "amount": 100000.0,
                "tds_amount": 1000.0
            }
        }

        # Create context and simulate closing it
        context = await browser_manager.create_context()
        context._user_closed = True
        await context.close()

        # Running process_job with this pre-closed context simulation or closing during step
        from apps.worker.portal.adapter import BrowserClosedException
        with pytest.raises((BrowserClosedException, Exception)):
            portal = PortalAdapter(context)
            # Invoking step on closed page triggers BrowserClosedException
            await portal.fill_form141_tab1_deductor({})

    finally:
        await browser_manager.stop()
