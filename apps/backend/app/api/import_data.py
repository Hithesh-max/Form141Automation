from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form, Body
from sqlalchemy import func
from sqlalchemy.orm import Session
from apps.backend.app.database.config import get_db
from apps.backend.app.database import models
from apps.backend.app.services.queue_manager import queue_manager
from apps.backend.app.services.validator import data_validator
from apps.backend.app.auth.encryption import encrypt_data, decrypt_data
from datetime import datetime, timezone
import pandas as pd
import openpyxl
import io
import json
import uuid
import hashlib
import logging
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/import", tags=["Import"])

def is_form141_excel(contents: bytes) -> bool:
    """Checks if the uploaded file is a Form 141 Multi-Customer vertical template."""
    try:
        wb = openpyxl.load_workbook(io.BytesIO(contents), data_only=True)
        for name in wb.sheetnames:
            if "form 141" in name.lower():
                return True
        ws = wb.active
        c1 = str(ws.cell(row=1, column=1).value or "").strip().upper()
        c2 = str(ws.cell(row=1, column=2).value or "").strip().lower()
        if c1 == "TYPE" and "field" in c2:
            return True
        return False
    except Exception:
        return False

def extract_form141_normalized_pans(flat_payload: dict) -> Tuple[str, str]:
    """
    Extracts and normalizes deductor PAN and deductee PAN from Form 141 payload.
    Duplicate identity key rule: normalized_deductor_pan + "|" + normalized_deductee_pan
    where:
      normalized_deductor_pan = deductor_pan.strip().upper()
      normalized_deductee_pan = deductee_pan.strip().upper()
    Two records are duplicates if and only if both normalized PANs match.
    Two records are different if they have different deductor PANs or different deductee PANs.
    Customer names, labels, column headers, amounts, or any other fields are never used.
    """
    deductor = (
        flat_payload.get("_loginPan")
        or flat_payload.get("deductorPan")
        or flat_payload.get("buyerPan")
        or flat_payload.get("buyersPan")
        or flat_payload.get("loginPan")
        or flat_payload.get("panOfDeductor")
        or flat_payload.get("panOfBuyer")
        or ""
    )
    deductee = (
        flat_payload.get("deducteePan")
        or flat_payload.get("sellerPan")
        or flat_payload.get("panOfTheDeductee")
        or flat_payload.get("panOfDeductee")
        or flat_payload.get("panOfSeller")
        or flat_payload.get("sellersPan")
        or flat_payload.get("landlordPan")
        or flat_payload.get("contractorPan")
        or ""
    )
    norm_deductor = str(deductor or "").strip().upper()
    norm_deductee = str(deductee or "").strip().upper()
    return norm_deductor, norm_deductee

def build_form141_preview(contents: bytes, filename: str) -> dict:
    """Parses Form 141 multi-customer file and returns structured preview."""
    from apps.backend.app.services.excel_parser_141 import parse_form141_excel, get_flat_payload
    parsed = parse_form141_excel(contents)

    customers_preview = []
    ready_count = 0
    warning_count = 0
    error_count = 0
    all_errors = []
    all_warnings = []
    seen_pan_pairs = set()
    duplicate_count = 0

    for customer in parsed["customers"]:
        flat = get_flat_payload(customer)
        norm_deductor, norm_deductee = extract_form141_normalized_pans(flat)
        pan_key = f"{norm_deductor}|{norm_deductee}"

        validation = data_validator.validate_form141_customer(
            customer, customer.get("customerIndex", 0)
        )

        if norm_deductor and norm_deductee:
            if pan_key in seen_pan_pairs:
                duplicate_count += 1
                validation["warnings"].append({
                    "customerIndex": customer.get("customerIndex", 1),
                    "section": "pan",
                    "field": "deductorPan",
                    "code": "DUPLICATE_PAN_PAIR",
                    "message": f"Duplicate filing PAN pair '{pan_key}' in import batch",
                    "severity": "warning"
                })
            else:
                seen_pan_pairs.add(pan_key)

        status = validation["status"]
        if status == "READY":
            ready_count += 1
        elif status == "WARNING":
            warning_count += 1
        else:
            error_count += 1

        for e in validation["errors"]:
            all_errors.append({
                "row": customer.get("customerIndex", 1),
                "field": e.get("field", ""),
                "code": e.get("code", ""),
                "message": f"[{customer.get('customerLabel')} - {e.get('section')}] {e.get('message')}",
                "severity": "error"
            })
        for w in validation["warnings"]:
            all_warnings.append({
                "row": customer.get("customerIndex", 1),
                "field": w.get("field", ""),
                "code": w.get("code", ""),
                "message": f"[{customer.get('customerLabel')} - {w.get('section')}] {w.get('message')}",
                "severity": "warning"
            })

        sections = {}
        for key in ["basicDetails", "immovablePropertyDetails", "buyerDeductorDetails",
                    "sellerDeducteeDetails", "transactionDetails", "taxDepositDetails",
                    "paymentDetails"]:
            sections[key] = customer.get(key, {})

        # Include login section with password masked for preview
        login_data = customer.get("login", {})
        login_display = {}
        for field_key, field_val in login_data.items():
            if isinstance(field_val, dict):
                display_val = dict(field_val)
                if "password" in field_key.lower():
                    display_val["value"] = "••••••••" if field_val.get("value") else ""
                login_display[field_key] = display_val
        sections["login"] = login_display

        # Redact password in values dict for preview
        safe_values = dict(customer.get("values", {}))
        for k in list(safe_values.keys()):
            if "password" in k.lower():
                safe_values[k] = "••••••••" if safe_values[k] else ""

        customers_preview.append({
            "customerIndex": customer.get("customerIndex"),
            "customerLabel": customer.get("customerLabel"),
            "customer_index": customer.get("customer_index") or customer.get("customerIndex"),
            "customer_label": customer.get("customer_label") or customer.get("customerLabel"),
            "source_column": customer.get("source_column"),
            "status": status,
            "errors": validation["errors"],
            "warnings": validation["warnings"],
            "sections": sections,
            "values": safe_values,
            "fields": customer.get("fields", [])
        })

    return {
        "is_form141": True,
        "filename": filename,
        "worksheet": parsed.get("worksheet"),
        "columns": ["TYPE", "Form 141 Field", "Fetch Type"] + [c["customerLabel"] for c in customers_preview],
        "fields": parsed.get("fields", []),
        "total_rows": parsed["totalCustomers"],
        "totalCustomers": parsed["totalCustomers"],
        "valid_count": ready_count,
        "readyCount": ready_count,
        "warningCount": warning_count,
        "errorCount": error_count,
        "error_count": error_count,
        "warning_count": warning_count,
        "duplicate_count": duplicate_count,
        "duplicateCount": duplicate_count,
        "errors": all_errors[:50],
        "warnings": all_warnings[:50],
        "preview": customers_preview[:10],
        "customers": customers_preview,
        "type_headings": parsed.get("type_headings", []),
        "type_field_counts": parsed.get("type_field_counts", {}),
        "diagnostics": {
            "worksheet": parsed.get("worksheet"),
            "total_customers": parsed.get("totalCustomers"),
            "customer_columns": [c.get("source_column") for c in customers_preview],
            "customer_labels": [c.get("customerLabel") for c in customers_preview],
            "type_headings": parsed.get("type_headings", []),
            "type_field_counts": parsed.get("type_field_counts", {}),
            "total_extracted_fields": len(parsed.get("fields", []))
        },
        "suggested_mapping": {
            "format": "Form 141 Multi-Customer Grouped Template",
            "template": "Form 141 (8 Sections, 54 Fields)",
            "customers_detected": str(parsed["totalCustomers"])
        }
    }

def compute_form141_logical_filing_identity(flat_payload: dict, customer_id: Optional[int] = None) -> dict:
    """
    Computes canonical Form 141 logical filing identity based strictly on PAN values.
    
    Exact duplicate key rule:
    normalized_deductor_pan + "|" + normalized_deductee_pan
    
    Where:
    - normalized_deductor_pan = deductor_pan.strip().upper()
    - normalized_deductee_pan = deductee_pan.strip().upper()
    
    Two records are duplicates if and only if both normalized PANs match.
    Two records are different if:
    - They have different deductor PANs, or
    - They have different deductee PANs.
    Customer names, labels, column headers, amounts, or any other fields are never used.
    """
    norm_deductor, norm_deductee = extract_form141_normalized_pans(flat_payload)
    canonical_key = f"{norm_deductor}|{norm_deductee}"
    identity_hash = hashlib.sha256(canonical_key.encode("utf-8")).hexdigest()[:16]

    raw_amt = flat_payload.get("amountPaidPresent") or flat_payload.get("saleConsideration") or 0.0
    try:
        clean_amt = float(str(raw_amt).replace(",", "").replace("₹", "").strip() or 0.0)
    except (ValueError, TypeError):
        clean_amt = 0.0

    return {
        "canonical_key": canonical_key,
        "identity_hash": identity_hash,
        "deductor_pan": norm_deductor,
        "deductee_pan": norm_deductee,
        "tax_year": str(flat_payload.get("taxYear") or "").strip().upper(),
        "month": str(flat_payload.get("monthOfDeduction") or "").strip().upper(),
        "amount": clean_amt
    }


def execute_form141_confirm(
    contents: bytes, 
    selected_indices: Optional[List[int]], 
    db: Session, 
    filename: str,
    import_valid_only: bool = False
) -> dict:
    """Executes import confirmation for Form 141 multi-customer file."""
    from apps.backend.app.services.excel_parser_141 import parse_form141_excel, get_flat_payload
    parsed = parse_form141_excel(contents)

    # Persist batch import metadata
    form141_imp = models.Form141Import(
        filename=filename,
        total_customers=parsed["totalCustomers"],
        status="IMPORTED"
    )
    db.add(form141_imp)
    db.flush()

    seen_in_batch = {}
    filings_created = []
    duplicate_filings_count = 0

    for customer in parsed["customers"]:
        customer_index = customer.get("customerIndex")
        if selected_indices is not None and len(selected_indices) > 0 and customer_index not in selected_indices:
            continue

        flat = get_flat_payload(customer)

        norm_deductor_pan, norm_deductee_pan = extract_form141_normalized_pans(flat)
        duplicate_key = f"{norm_deductor_pan}|{norm_deductee_pan}"

        login_password = flat.get("_loginPassword", "")
        buyer_name = flat.get("buyerName", "").strip()
        customer_label = buyer_name or customer.get("customerLabel", f"Customer {customer_index}")
        sale_consideration = flat.get("saleConsideration", "0")
        tds_amount = flat.get("tdsAmount")
        # Validate amounts
        _, _, amount_num = data_validator.validate_amount(sale_consideration, "saleConsideration")
        
        # Preserve genuine 0 vs None / Pending / Requires Review
        tds_num = None
        if tds_amount is not None and str(tds_amount).strip() not in ("", "Pending", "Requires Review", "None"):
            try:
                clean_tds_str = str(tds_amount).replace(",", "").replace("₹", "").strip()
                tds_num = float(clean_tds_str)
            except (ValueError, TypeError):
                tds_num = None

        if login_password:
            flat["_loginPassword"] = encrypt_data(login_password)

        customer_code = f"F141-{uuid.uuid4().hex[:6].upper()}"
        pan_to_store = norm_deductor_pan

        existing_customer = None
        if pan_to_store:
            all_customers = db.query(models.Customer).all()
            for c in all_customers:
                if c.pan_encrypted:
                    try:
                        if decrypt_data(c.pan_encrypted).upper() == pan_to_store:
                            existing_customer = c
                            break
                    except Exception:
                        pass

        if existing_customer:
            db_customer = existing_customer
        else:
            db_customer = models.Customer(
                customer_code=customer_code,
                name=customer_label,
                pan_encrypted=encrypt_data(pan_to_store) if pan_to_store else ""
            )
            db.add(db_customer)
            db.flush()

        # Compute normalized canonical Form 141 logical filing identity (PAN ONLY)
        logical_identity = compute_form141_logical_filing_identity(flat, db_customer.id)
        flat["_logicalFilingKey"] = logical_identity["canonical_key"]
        flat["_logicalFilingHash"] = logical_identity["identity_hash"]

        # Validate Form 141 customer fields
        cust_validation = data_validator.validate_form141_customer(customer, customer_index or 1)
        initial_status = cust_validation.get("status", "READY")
        if cust_validation.get("errors"):
            initial_status = "INVALID"
        elif cust_validation.get("warnings"):
            initial_status = "VALIDATION_REQUIRED"
        elif initial_status not in ["READY", "VALIDATION_REQUIRED", "INVALID"]:
            initial_status = "READY"

        if import_valid_only and initial_status == "INVALID":
            logger.info(f"Skipping invalid Form 141 customer {customer_label} due to import_valid_only=True")
            continue

        # Check if logical filing already exists for this PAN pair (DUPLICATE DETECTION: PAN ONLY)
        # Duplicate identity rule: normalized_deductor_pan + "|" + normalized_deductee_pan
        # Two records are duplicates if and only if both normalized PANs match.
        # Two records are different if they have different deductor PANs or different deductee PANs.
        # Customer names, labels, column headers, amounts, etc. are NEVER used to declare duplicates.
        existing_lf = None
        if norm_deductor_pan and norm_deductee_pan:
            if duplicate_key in seen_in_batch:
                existing_lf = seen_in_batch[duplicate_key]
                duplicate_filings_count += 1
            else:
                existing_lf = (
                    db.query(models.Form141LogicalFiling)
                    .filter(
                        func.upper(func.trim(models.Form141LogicalFiling.deductor_pan)) == norm_deductor_pan,
                        func.upper(func.trim(models.Form141LogicalFiling.deductee_pan)) == norm_deductee_pan
                    )
                    .first()
                )

        if existing_lf:
            # Update existing logical filing metadata without overwriting its job history
            existing_lf.import_id = form141_imp.id
            existing_lf.customer_label = customer_label
            existing_lf.deductor_pan = norm_deductor_pan
            existing_lf.deductee_pan = norm_deductee_pan
            existing_lf.amount = amount_num
            existing_lf.tds_amount = tds_num
            existing_lf.field_values = flat
            existing_lf.field_metadata = customer.get("fields")
            existing_lf.validation_errors = cust_validation.get("errors", [])
            existing_lf.validation_warnings = cust_validation.get("warnings", [])
            existing_lf.updated_at = datetime.now(timezone.utc)
            # If no job was ever started, sync status and step
            if existing_lf.job_id is None:
                existing_lf.status = initial_status
                existing_lf.current_step = "NOT STARTED"
            persisted_lf = existing_lf
            if persisted_lf not in filings_created:
                filings_created.append(persisted_lf)
        else:
            # Generate stable logical filing ID (e.g. LF-001)
            lf_base_id = f"LF-{customer_index:03d}" if customer_index else f"LF-{uuid.uuid4().hex[:4].upper()}"
            existing_lf_check = db.query(models.Form141LogicalFiling).filter(models.Form141LogicalFiling.logical_filing_id == lf_base_id).first()
            if existing_lf_check:
                logical_filing_id = f"{lf_base_id}-{form141_imp.id}"
            else:
                logical_filing_id = lf_base_id

            persisted_lf = models.Form141LogicalFiling(
                import_id=form141_imp.id,
                logical_filing_id=logical_filing_id,
                customer_label=customer_label,
                column_index=customer_index or 1,
                deductor_pan=norm_deductor_pan,
                deductee_pan=norm_deductee_pan,
                amount=amount_num,
                tds_amount=tds_num,
                status=initial_status,
                current_step="NOT STARTED",
                validation_errors=cust_validation.get("errors", []),
                validation_warnings=cust_validation.get("warnings", []),
                field_values=flat,
                field_metadata=customer.get("fields"),
                job_id=None
            )
            db.add(persisted_lf)
            db.flush()
            filings_created.append(persisted_lf)

        if norm_deductor_pan and norm_deductee_pan:
            seen_in_batch[duplicate_key] = persisted_lf

    audit = models.AuditLog(
        action="IMPORT_FORM141_EXCEL",
        entity_type="FORM141_BATCH",
        entity_id=filename,
        metadata_json={
            "total_customers_in_file": parsed["totalCustomers"],
            "filings_created": len(filings_created)
        }
    )
    db.add(audit)
    db.commit()

    # Form 141 import is purely data-only:
    # ZERO execution jobs created at import time.
    # ZERO worker calls, ZERO browser opens, ZERO portal logins.
    ready_count = sum(1 for f in filings_created if f.status == "READY")
    warning_count = sum(1 for f in filings_created if f.status == "VALIDATION_REQUIRED")
    error_count = sum(1 for f in filings_created if f.status == "INVALID")

    return {
        "message": f"Successfully imported {len(filings_created)} Form 141 customer filings.",
        "import_id": form141_imp.id,
        "filings_created": len(filings_created),
        "jobs_created": len(filings_created),  # Backwards compatibility for UI toast/alert
        "job_ids": [],
        "logical_filing_ids": [f.logical_filing_id for f in filings_created],
        "customer_labels": [f.customer_label for f in filings_created],
        "validation_summary": {
            "total": parsed["totalCustomers"],
            "ready": ready_count,
            "warning": warning_count,
            "error": error_count
        },
        "totalCustomers": parsed["totalCustomers"],
        "selectedCount": len(filings_created)
    }


@router.post("/preview")
async def preview_import(
    file: UploadFile = File(...),
    mapping: Optional[str] = Form(None)
):
    """
    Parses uploaded Excel/CSV, auto-detects if it is a Form 141 Multi-Customer template
    or a flat CSV/Excel table, and runs validation engine returning validation preview stats.
    """
    if not file.filename.endswith(('.xlsx', '.csv', '.xls')):
        raise HTTPException(status_code=400, detail="Only .xlsx or .csv files are supported")
    
    try:
        contents = await file.read()

        # Check if file is Form 141 Multi-Customer template
        if file.filename.endswith(('.xlsx', '.xls')) and is_form141_excel(contents):
            return build_form141_preview(contents, file.filename)

        # Fallback to flat table CSV/Excel
        if file.filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(contents))
        else:
            df = pd.read_excel(io.BytesIO(contents))
            
        columns = [str(c) for c in df.columns.tolist()]
        records = df.fillna("").to_dict(orient="records")
        
        mapping_dict = json.loads(mapping) if mapping else {}
        
        # Run validation engine
        validation_result = data_validator.validate_dataset(records, column_mapping=mapping_dict)
        
        # Auto-detect suggested mapping
        dummy_row = records[0] if records else {}
        suggested_mapping = {
            "customer_code": data_validator._find_col(dummy_row, ["clientcode", "customercode", "customer_code", "client_code", "id"]) or "",
            "pan": data_validator._find_col(dummy_row, ["pan", "taxpan", "seller's pan", "sellers_pan", "buyer_pan", "deductee_pan", "pan number"]) or "",
            "amount": data_validator._find_col(dummy_row, ["taxamount", "amount", "total amount", "consideration", "sale consideration"]) or "",
            "tds_amount": data_validator._find_col(dummy_row, ["tds", "tdsamount", "tds_amount", "tax deducted"]) or "",
            "name": data_validator._find_col(dummy_row, ["name", "clientname", "customername", "customer_name", "party_name"]) or "",
            "filing_date": data_validator._find_col(dummy_row, ["date", "filing_date", "agreement_date", "date_of_agreement"]) or ""
        }

        return {
            "is_form141": False,
            "filename": file.filename,
            "columns": columns,
            "total_rows": validation_result["total_rows"],
            "valid_count": validation_result["valid_count"],
            "error_count": validation_result["error_count"],
            "warning_count": validation_result["warning_count"],
            "duplicate_count": validation_result["duplicate_count"],
            "errors": validation_result["errors"][:50],
            "warnings": validation_result["warnings"][:50],
            "preview": records[:10],
            "suggested_mapping": suggested_mapping
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading file: {str(e)}")


@router.post("/confirm")
async def confirm_import(
    file: UploadFile = File(...), 
    mapping: str = Form("{}"), 
    import_valid_only: bool = Form(True),
    selectedIndices: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Validates uploaded file and commits records to Database.
    Automatically handles both Form 141 Multi-Customer template and flat CSV/Excel formats.
    """
    try:
        contents = await file.read()

        # Handle Form 141 multi-customer file
        if file.filename.endswith(('.xlsx', '.xls')) and is_form141_excel(contents):
            indices = None
            if selectedIndices:
                try:
                    indices = json.loads(selectedIndices)
                except Exception:
                    pass
            return execute_form141_confirm(contents, indices, db, file.filename, import_valid_only=import_valid_only)

        mapping_dict = json.loads(mapping) if mapping else {}
        if file.filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(contents))
        else:
            df = pd.read_excel(io.BytesIO(contents))
            
        records = df.fillna("").to_dict(orient="records")
        validation_result = data_validator.validate_dataset(records, column_mapping=mapping_dict)
        
        target_rows = validation_result["valid_rows"]
        if not import_valid_only and validation_result["invalid_rows"]:
            for inv in validation_result["invalid_rows"]:
                target_rows.append(inv["data"])
                
        if not target_rows:
            return {
                "message": "No valid rows found to import.",
                "jobs_created": 0,
                "total_rows": validation_result["total_rows"],
                "valid_count": 0,
                "error_count": validation_result["error_count"],
                "errors": validation_result["errors"]
            }

        jobs_created = []
        jobs_to_enqueue = []
        for item in target_rows:
            customer_code = item["customer_code"]
            if not customer_code:
                customer_code = f"CUST-{uuid.uuid4().hex[:6].upper()}"
                
            pan = item["pan"]
            name = item["name"]
            amount = item["amount"]
            tds_amount = item["tds_amount"]
            raw_payload = item["raw_payload"]
            
            customer = db.query(models.Customer).filter(models.Customer.customer_code == customer_code).first()
            if not customer:
                customer = models.Customer(
                    customer_code=customer_code,
                    name=name,
                    pan_encrypted=encrypt_data(pan)
                )
                db.add(customer)
                db.flush()
            elif pan:
                customer.pan_encrypted = encrypt_data(pan)
                
            # Idempotency check for active jobs
            existing_active = db.query(models.Job).filter(
                models.Job.customer_id == customer.id,
                models.Job.status.in_(["QUEUED", "PROCESSING", "PAYMENT_PENDING"])
            ).first()
            if existing_active:
                logger.info(f"Duplicate import skipped for {customer_code}: active job {existing_active.job_reference} exists")
                if existing_active.status == "QUEUED":
                    jobs_to_enqueue.append(existing_active.id)
                continue

            filing = models.Filing(
                customer_id=customer.id,
                filing_reference=f"FIL-{uuid.uuid4().hex[:8].upper()}",
                amount=amount,
                tds_amount=tds_amount,
                status="IMPORTED"
            )
            db.add(filing)
            db.flush()
            
            job = models.Job(
                job_reference=f"JOB-{filing.id}-{uuid.uuid4().hex[:6].upper()}",
                customer_id=customer.id,
                filing_id=filing.id,
                status="READY",
                current_step="READY",
                data_payload=raw_payload,
                attempt_count=0
            )
            db.add(job)
            db.flush()
            
            event = models.JobEvent(
                job_id=job.id,
                event_type="JOB_CREATED",
                status="READY",
                message=f"Job created for {customer.customer_code} in READY status (Amount: ₹{amount})"
            )
            db.add(event)
            
            jobs_created.append(job.id)
            
        audit = models.AuditLog(
            action="IMPORT_EXCEL",
            entity_type="FILING_BATCH",
            entity_id=file.filename,
            metadata_json={
                "total_rows": validation_result["total_rows"],
                "valid_count": validation_result["valid_count"],
                "error_count": validation_result["error_count"],
                "jobs_created": len(jobs_created)
            }
        )
        db.add(audit)
        db.commit()
        
        # Jobs are imported in READY status and not auto-enqueued.
        # User triggers start explicitly from dashboard row or queue control.

        return {
            "message": f"Successfully imported {len(jobs_created)} filing jobs.",
            "jobs_created": len(jobs_created),
            "total_rows": validation_result["total_rows"],
            "valid_count": validation_result["valid_count"],
            "error_count": validation_result["error_count"],
            "warning_count": validation_result["warning_count"],
            "duplicate_count": validation_result["duplicate_count"],
            "rejected_count": len(validation_result["invalid_rows"])
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@router.post("/form141/preview")
async def preview_form141_import(
    file: UploadFile = File(...)
):
    """Parses a Form 141 Multi Customer Excel and returns preview."""
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Only .xlsx files are supported for Form 141 import")

    try:
        contents = await file.read()
        return build_form141_preview(contents, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error parsing Form 141 Excel: {str(e)}")


@router.post("/form141/confirm")
async def confirm_form141_import(
    file: UploadFile = File(...),
    selectedIndices: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Imports selected customers from a Form 141 Multi Customer Excel."""
    try:
        indices = None
        if selectedIndices and selectedIndices.strip() and selectedIndices.strip() != "[]":
            try:
                parsed_indices = json.loads(selectedIndices)
                if isinstance(parsed_indices, list) and len(parsed_indices) > 0:
                    indices = parsed_indices
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid selectedIndices format")

        contents = await file.read()
        return execute_form141_confirm(contents, indices, db, file.filename)
    except HTTPException:
        raise
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Form 141 import failed: {str(e)}")



@router.post("/form141/start")
def start_form141_job(
    job_id: int = Body(..., embed=True),
    db: Session = Depends(get_db)
):
    """
    Starts a single Form 141 filing job under strict single-filing concurrency lock (MAX_ACTIVE_FORM141_JOBS = 1).
    Returns HTTP 409 Conflict if another filing job is currently active.
    """
    from apps.backend.app.api.jobs import start_job
    return start_job(job_id=job_id, db=db)

