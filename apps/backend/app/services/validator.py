import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, date
import math
import openpyxl

PAN_REGEX = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")

class ValidationIssue:
    def __init__(self, row: int, field: str, code: str, message: str, severity: str = "error"):
        self.row = row
        self.field = field
        self.code = code
        self.message = message
        self.severity = severity

    def to_dict(self) -> Dict[str, Any]:
        return {
            "row": self.row,
            "field": self.field,
            "code": self.code,
            "message": self.message,
            "severity": self.severity
        }

class DataValidator:
    """
    Reusable validation engine for Form 141 filing records.
    Validates PAN formats, required fields, numeric constraints, date parsing,
    and batch duplicates with structured error and warning reporting.
    """

    def __init__(self, custom_rules: Optional[Dict[str, Any]] = None):
        self.custom_rules = custom_rules or {}

    @staticmethod
    def validate_pan(pan: Any) -> Tuple[bool, Optional[str]]:
        """Validates Indian Income Tax PAN format."""
        if not pan or str(pan).strip() == "" or str(pan).lower() == "nan":
            return False, "PAN is missing"
        pan_clean = str(pan).strip().upper()
        if not PAN_REGEX.match(pan_clean):
            return False, f"Invalid PAN format '{pan_clean}'. Must be 5 letters, 4 digits, 1 letter (e.g. ABCDE1234F)"
        return True, None

    @staticmethod
    def validate_amount(val: Any, field_name: str = "amount", min_val: float = 0.0) -> Tuple[bool, Optional[str], float]:
        """Validates that a numeric amount is non-negative and valid."""
        if val is None or str(val).strip() == "" or str(val).lower() == "nan":
            return True, None, 0.0
        try:
            cleaned = str(val).replace(",", "").replace("₹", "").replace("$", "").strip()
            num = float(cleaned)
            if math.isnan(num):
                return False, f"Invalid number for {field_name}", 0.0
            if num < min_val:
                return False, f"{field_name} must be greater than or equal to {min_val}", num
            return True, None, num
        except (ValueError, TypeError):
            return False, f"Invalid numeric value '{val}' for {field_name}", 0.0

    @staticmethod
    def validate_date(val: Any) -> Tuple[bool, Optional[str], Optional[str]]:
        """Attempts to parse a date string, datetime/date object, or Excel serial date."""
        if val is None or str(val).strip() == "" or str(val).lower() == "nan":
            return True, None, None
        
        if isinstance(val, (datetime, date)):
            return True, None, val.strftime("%Y-%m-%d")

        val_str = str(val).strip()

        # Handle numeric Excel serial date (e.g. 45200 or "45200" or 45200.0)
        try:
            num_val = float(val_str)
            # Excel serial dates reasonable range (10000 -> 1927, 80000 -> 2119)
            if 10000 <= num_val <= 90000:
                dt_serial = openpyxl.utils.datetime.from_excel(num_val)
                return True, None, dt_serial.strftime("%Y-%m-%d")
        except (ValueError, TypeError, OverflowError):
            pass

        formats = [
            "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d",
            "%Y-%m-%d %H:%M:%S", "%d-%m-%Y %H:%M:%S", "%d/%m/%Y %H:%M:%S",
            "%d.%m.%Y", "%Y.%m.%d"
        ]
        for fmt in formats:
            try:
                clean_str = val_str.split(" ")[0] if " " in val_str and fmt in ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"] else val_str
                dt = datetime.strptime(clean_str, fmt)
                return True, None, dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        return False, f"Invalid date format '{val_str}'. Supported: YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY", None

    def validate_dataset(self, records: List[Dict[str, Any]], column_mapping: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Validates a list of row dictionaries.
        column_mapping maps canonical fields (customer_code, pan, amount, tds_amount, name, etc.)
        to actual column names in the file.
        """
        mapping = column_mapping or {}
        errors: List[ValidationIssue] = []
        warnings: List[ValidationIssue] = []
        
        seen_customer_codes: set = set()
        seen_pans: set = set()
        duplicate_count = 0

        valid_rows: List[Dict[str, Any]] = []
        invalid_rows: List[Dict[str, Any]] = []

        for idx, row in enumerate(records, start=1):
            row_errors: List[ValidationIssue] = []
            row_warnings: List[ValidationIssue] = []

            # Extract fields via mapping or heuristic fallback
            col_cust_code = mapping.get("customer_code") or self._find_col(row, ["clientcode", "customercode", "customer_code", "client_code", "id", "customer id"])
            col_pan = mapping.get("pan") or self._find_col(row, ["pan", "taxpan", "seller's pan", "sellers_pan", "buyer_pan", "deductee_pan", "pan number"])
            col_amount = mapping.get("amount") or self._find_col(row, ["taxamount", "amount", "total amount", "consideration", "sale consideration"])
            col_tds = mapping.get("tds_amount") or self._find_col(row, ["tds", "tdsamount", "tds_amount", "tax deducted"])
            col_name = mapping.get("name") or self._find_col(row, ["name", "clientname", "customername", "customer_name", "party_name"])
            col_date = mapping.get("filing_date") or self._find_col(row, ["date", "filing_date", "agreement_date", "date_of_agreement"])

            raw_cust_code = str(row.get(col_cust_code, "")).strip() if col_cust_code and row.get(col_cust_code) is not None else ""
            raw_pan = str(row.get(col_pan, "")).strip() if col_pan and row.get(col_pan) is not None else ""
            raw_amount = row.get(col_amount) if col_amount else None
            raw_tds = row.get(col_tds) if col_tds else None
            raw_name = str(row.get(col_name, "")).strip() if col_name and row.get(col_name) is not None else ""
            raw_date = row.get(col_date) if col_date else None

            # 1. Validate PAN
            if not raw_pan or raw_pan.lower() == "nan":
                row_errors.append(ValidationIssue(idx, "pan", "MISSING_REQUIRED_FIELD", "PAN is required"))
            else:
                is_valid, msg = self.validate_pan(raw_pan)
                if not is_valid:
                    row_errors.append(ValidationIssue(idx, "pan", "INVALID_PAN_FORMAT", msg or "Invalid PAN"))

            # 2. Check duplicate PAN or Customer Code within batch
            norm_pan = raw_pan.upper() if raw_pan else ""
            if norm_pan and norm_pan != "NAN":
                if norm_pan in seen_pans:
                    duplicate_count += 1
                    row_warnings.append(ValidationIssue(idx, "pan", "DUPLICATE_PAN", f"Duplicate PAN '{norm_pan}' in upload batch", severity="warning"))
                seen_pans.add(norm_pan)

            if raw_cust_code and raw_cust_code != "nan":
                if raw_cust_code in seen_customer_codes:
                    row_warnings.append(ValidationIssue(idx, "customer_code", "DUPLICATE_CUSTOMER_CODE", f"Duplicate Customer Code '{raw_cust_code}'", severity="warning"))
                seen_customer_codes.add(raw_cust_code)

            # 3. Validate Amounts
            if raw_amount is not None and str(raw_amount).strip() != "" and str(raw_amount).lower() != "nan":
                is_valid, msg, clean_amount = self.validate_amount(raw_amount, "amount")
                if not is_valid:
                    row_errors.append(ValidationIssue(idx, "amount", "INVALID_AMOUNT", msg or "Invalid amount"))
            else:
                clean_amount = 0.0
                row_warnings.append(ValidationIssue(idx, "amount", "DEFAULT_AMOUNT", "Amount not specified, defaulting to 0.0", severity="warning"))

            if raw_tds is not None and str(raw_tds).strip() != "" and str(raw_tds).lower() != "nan":
                is_valid, msg, clean_tds = self.validate_amount(raw_tds, "tds_amount")
                if not is_valid:
                    row_errors.append(ValidationIssue(idx, "tds_amount", "INVALID_TDS_AMOUNT", msg or "Invalid TDS amount"))
            else:
                clean_tds = 0.0

            # 4. Validate Date
            clean_date = None
            if raw_date is not None and str(raw_date).strip() != "" and str(raw_date).lower() != "nan":
                is_valid, msg, clean_date = self.validate_date(raw_date)
                if not is_valid:
                    row_warnings.append(ValidationIssue(idx, "filing_date", "INVALID_DATE_FORMAT", msg or "Invalid date", severity="warning"))

            cleaned_data = {
                "row_index": idx,
                "customer_code": raw_cust_code,
                "pan": norm_pan,
                "name": raw_name or f"Client {norm_pan}",
                "amount": clean_amount,
                "tds_amount": clean_tds,
                "filing_date": clean_date,
                "raw_payload": row
            }

            errors.extend(row_errors)
            warnings.extend(row_warnings)

            if row_errors:
                invalid_rows.append({
                    "row_index": idx,
                    "data": cleaned_data,
                    "errors": [e.to_dict() for e in row_errors],
                    "warnings": [w.to_dict() for w in row_warnings]
                })
            else:
                valid_rows.append(cleaned_data)

        total_rows = len(records)
        valid_count = len(valid_rows)
        error_count = len(errors)
        warning_count = len(warnings)

        return {
            "total_rows": total_rows,
            "valid_count": valid_count,
            "invalid_count": len(invalid_rows),
            "error_count": error_count,
            "warning_count": warning_count,
            "duplicate_count": duplicate_count,
            "errors": [e.to_dict() for e in errors],
            "warnings": [w.to_dict() for w in warnings],
            "valid_rows": valid_rows,
            "invalid_rows": invalid_rows
        }

    def _find_col(self, row: Dict[str, Any], candidates: List[str]) -> Optional[str]:
        keys = list(row.keys())
        normalized_keys = {re.sub(r'[^a-z0-9]', '', str(k).lower()): k for k in keys}
        for cand in candidates:
            norm_cand = re.sub(r'[^a-z0-9]', '', cand.lower())
            if norm_cand in normalized_keys:
                return normalized_keys[norm_cand]
        return None

    @staticmethod
    def validate_proportion(val: Any, field_name: str = "proportion") -> Tuple[bool, Optional[str], float]:
        """Validates a percentage proportion (0-100)."""
        if val is None or str(val).strip() == "" or str(val).lower() == "nan":
            return True, None, 0.0
        try:
            cleaned = str(val).replace("%", "").replace(",", "").strip()
            num = float(cleaned)
            if math.isnan(num):
                return False, f"Invalid number for {field_name}", 0.0
            if num < 0 or num > 100:
                return False, f"{field_name} must be between 0 and 100", num
            return True, None, num
        except (ValueError, TypeError):
            return False, f"Invalid numeric value '{val}' for {field_name}", 0.0

    def validate_form141_customer(self, customer: Dict[str, Any], customer_index: int = 1) -> Dict[str, Any]:
        """
        Validates a single Form 141 customer record parsed from the multi-customer Excel.
        
        Each section is a dict of {fieldKey: {value, fetchType, fieldLabel}}.
        Fields with fetchType Fetch/Calculate are not required (portal auto-fills them).
        Conditional fields are only required when their condition applies.
        
        Returns: {status: READY|WARNING|ERROR, errors: [...], warnings: [...]}
        """
        errors: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []

        def _val(val: Any) -> str:
            """Normalize a value to string for checking."""
            if val is None:
                return ""
            return str(val).strip()

        def _is_empty(val: Any) -> bool:
            v = _val(val)
            return v == "" or v.lower() == "nan" or v.lower() == "none"

        def _get_field(section_key: str, field_key: str) -> Tuple[Any, str]:
            """Get field value and fetchType from a section."""
            section = customer.get(section_key, {})
            field = section.get(field_key, {})
            if isinstance(field, dict):
                return field.get("value"), field.get("fetchType", "Manual")
            return field, "Manual"

        def _add_error(section: str, field: str, code: str, message: str):
            errors.append({
                "customerIndex": customer_index,
                "section": section,
                "field": field,
                "code": code,
                "message": message,
                "severity": "error"
            })

        def _add_warning(section: str, field: str, code: str, message: str):
            warnings.append({
                "customerIndex": customer_index,
                "section": section,
                "field": field,
                "code": code,
                "message": message,
                "severity": "warning"
            })

        def _check_required(section_key: str, field_key: str, display_name: str):
            """Check if a required Manual/Select/Validate field has a value."""
            value, fetch_type = _get_field(section_key, field_key)
            # Fetch, Calculate fields are auto-populated by portal — not required in Excel
            if fetch_type in ("Fetch", "Calculate", "Fetch/Select"):
                return
            if _is_empty(value):
                _add_error(section_key, field_key, "MISSING_REQUIRED_FIELD",
                           f"{display_name} is required")

        def _check_pan(section_key: str, field_key: str, display_name: str):
            """Validate PAN format for a field (only if Manual and non-empty)."""
            value, fetch_type = _get_field(section_key, field_key)
            if fetch_type in ("Fetch", "Calculate"):
                return
            if _is_empty(value):
                return  # Required check is done separately
            is_valid, msg = self.validate_pan(value)
            if not is_valid:
                _add_error(section_key, field_key, "INVALID_PAN_FORMAT",
                           f"{display_name}: {msg}")

        def _check_date(section_key: str, field_key: str, display_name: str):
            """Validate date format for a field."""
            value, fetch_type = _get_field(section_key, field_key)
            if fetch_type in ("Fetch", "Calculate"):
                return
            if _is_empty(value):
                return
            is_valid, msg, _ = self.validate_date(value)
            if not is_valid:
                _add_warning(section_key, field_key, "INVALID_DATE_FORMAT",
                             f"{display_name}: {msg}")

        def _check_amount(section_key: str, field_key: str, display_name: str):
            """Validate numeric amount field."""
            value, fetch_type = _get_field(section_key, field_key)
            if fetch_type in ("Fetch", "Calculate"):
                return
            if _is_empty(value):
                return
            is_valid, msg, _ = self.validate_amount(value, display_name)
            if not is_valid:
                _add_error(section_key, field_key, "INVALID_AMOUNT", msg)

        def _check_proportion(section_key: str, field_key: str, display_name: str):
            """Validate proportion percentage (0-100)."""
            value, fetch_type = _get_field(section_key, field_key)
            if fetch_type in ("Fetch", "Calculate"):
                return
            if _is_empty(value):
                return
            is_valid, msg, _ = self.validate_proportion(value, display_name)
            if not is_valid:
                _add_error(section_key, field_key, "INVALID_PROPORTION", msg)

        # ── LOGIN ──────────────────────────────────────────────
        _check_required("login", "loginPan", "Login PAN")
        _check_pan("login", "loginPan", "Login PAN")

        # ── BASIC DETAILS ──────────────────────────────────────
        applicable_act_val, _ = _get_field("basicDetails", "applicableAct")
        if not _is_empty(applicable_act_val):
            # Applicable act is present
            pass

        deductor_pan_val, _ = _get_field("basicDetails", "deductorPan")
        login_pan_val, _ = _get_field("login", "loginPan")
        eff_deductor_pan = deductor_pan_val or login_pan_val
        if _is_empty(eff_deductor_pan):
            _add_error("basicDetails", "deductorPan", "MISSING_REQUIRED_FIELD", "Deductor PAN is required")
        else:
            is_valid, msg = self.validate_pan(eff_deductor_pan)
            if not is_valid:
                _add_error("basicDetails", "deductorPan", "INVALID_PAN_FORMAT", f"Deductor PAN: {msg}")

        _check_required("basicDetails", "deducteeType", "Deductee Type")
        deductee_type_val, _ = _get_field("basicDetails", "deducteeType")
        if not _is_empty(deductee_type_val):
            dt_clean = str(deductee_type_val).strip().lower()
            if not ("corporate" in dt_clean or "non-corporate" in dt_clean or "company" in dt_clean or "non-company" in dt_clean or "individual" in dt_clean or "huf" in dt_clean or "firm" in dt_clean):
                _add_error("basicDetails", "deducteeType", "INVALID_DEDUCTEE_TYPE",
                           "Deductee Type must be either 'Corporate' (Company) or 'Non-Corporate' (Individual/HUF/Firm)")

        _check_required("basicDetails", "residentialStatus", "Residential Status")
        res_status_val, _ = _get_field("basicDetails", "residentialStatus")
        if not _is_empty(res_status_val) and ("non-resident" in str(res_status_val).lower() or "nri" in str(res_status_val).lower()):
            _add_error("basicDetails", "residentialStatus", "NON_RESIDENT_NOT_ALLOWED",
                       "Form 141 applies only to Resident Deductees. Non-resident deductees require Form 27Q.")

        _check_required("basicDetails", "taxYear", "Tax Year of Transaction")
        _check_required("basicDetails", "monthOfDeduction", "Month of Deduction")
        _check_required("basicDetails", "natureOfTransaction", "Nature of Transaction")

        # ── IMMOVABLE PROPERTY DETAILS ─────────────────────────
        _check_required("immovablePropertyDetails", "propertyType", "Type of Immovable Property")
        _check_required("immovablePropertyDetails", "flatDoorBuilding", "Flat / Door / Building")
        _check_required("immovablePropertyDetails", "pinCode", "PIN Code")
        _check_required("immovablePropertyDetails", "stampDutyValue", "Total Stamp Duty Value")
        _check_amount("immovablePropertyDetails", "stampDutyValue", "Stamp Duty Value")
        _check_required("immovablePropertyDetails", "saleConsideration", "Total Sale Consideration")
        _check_amount("immovablePropertyDetails", "saleConsideration", "Sale Consideration")
        _check_date("immovablePropertyDetails", "dateOfAgreement", "Date of Agreement")
        _check_date("immovablePropertyDetails", "dateOfRegistration", "Date of Registration")
        _check_required("immovablePropertyDetails", "paymentLumpsumOrInstalment", "Payment Type (Lumpsum/Instalment)")

        # Conditional: Installment fields
        payment_type_val, _ = _get_field("immovablePropertyDetails", "paymentLumpsumOrInstalment")
        if not _is_empty(payment_type_val) and "instalment" in str(payment_type_val).lower():
            _check_required("immovablePropertyDetails", "installmentType", "Installment Type")
            _check_required("immovablePropertyDetails", "previousAckNumber", "Previous Acknowledgement Number")
            inst_type_val, _ = _get_field("immovablePropertyDetails", "installmentType")
            if not _is_empty(inst_type_val) and "last" in str(inst_type_val).lower():
                _check_required("immovablePropertyDetails", "previousInstallmentAmount",
                                "Previous Installment Amount")
                _check_amount("immovablePropertyDetails", "previousInstallmentAmount",
                              "Previous Installment Amount")

        # ── BUYER / DEDUCTOR DETAILS ───────────────────────────
        # In Form 141 (26QB), the Buyer IS the Deductor.
        buyer_pan_val, _ = _get_field("buyerDeductorDetails", "buyerPan")
        eff_buyer_pan = buyer_pan_val or eff_deductor_pan
        if _is_empty(eff_buyer_pan):
            _add_error("buyerDeductorDetails", "buyerPan", "MISSING_REQUIRED_FIELD", "Buyer's PAN is required")
        else:
            is_valid, msg = self.validate_pan(eff_buyer_pan)
            if not is_valid:
                _add_error("buyerDeductorDetails", "buyerPan", "INVALID_PAN_FORMAT", f"Buyer's PAN: {msg}")

        buyer_name_val, _ = _get_field("buyerDeductorDetails", "buyerName")
        if _is_empty(buyer_name_val):
            _add_warning("buyerDeductorDetails", "buyerName", "MISSING_BUYER_NAME", "Buyer's Name is recommended")
        _check_required("buyerDeductorDetails", "buyerProportion", "Buyer's Proportion")
        _check_proportion("buyerDeductorDetails", "buyerProportion", "Buyer's Proportion")

        # ── SELLER / DEDUCTEE DETAILS ──────────────────────────
        seller_pan_val, _ = _get_field("sellerDeducteeDetails", "sellerPan")
        deductee_pan_val, _ = _get_field("transactionDetails", "deducteePan")
        eff_seller_pan = seller_pan_val or deductee_pan_val
        if _is_empty(eff_seller_pan):
            _add_error("sellerDeducteeDetails", "sellerPan", "MISSING_REQUIRED_FIELD", "Seller's PAN is required")
        else:
            is_valid, msg = self.validate_pan(eff_seller_pan)
            if not is_valid:
                _add_error("sellerDeducteeDetails", "sellerPan", "INVALID_PAN_FORMAT", f"Seller's PAN: {msg}")
        _check_required("sellerDeducteeDetails", "sellerProportion", "Seller's Proportion")
        _check_proportion("sellerDeducteeDetails", "sellerProportion", "Seller's Proportion")

        # ── TRANSACTION DETAILS ────────────────────────────────
        if _is_empty(eff_seller_pan):
            _check_required("transactionDetails", "deducteePan", "PAN of the Deductee")
        else:
            is_valid, msg = self.validate_pan(eff_seller_pan)
            if not is_valid:
                _add_error("transactionDetails", "deducteePan", "INVALID_PAN_FORMAT", f"PAN of the Deductee: {msg}")
        _check_required("transactionDetails", "amountPaidPresent", "Amount Paid/Credited in Present Transaction")
        _check_amount("transactionDetails", "amountPaidPresent", "Amount Paid in Present Transaction")
        _check_required("transactionDetails", "dateOfPayment", "Date of Payment/Credit")
        _check_date("transactionDetails", "dateOfPayment", "Date of Payment/Credit")
        _check_required("transactionDetails", "section395Applicable", "Whether Section 395(1) Applicable")
        _check_date("transactionDetails", "dateOfDeduction", "Date of Deduction")

        # Conditional: Certificate Number required if Section 395(1) is Yes
        sec395_val, _ = _get_field("transactionDetails", "section395Applicable")
        if not _is_empty(sec395_val) and str(sec395_val).strip().lower() == "yes":
            _check_required("transactionDetails", "certificateNumber", "Certificate Number")

        # Validate TDS rate if provided
        tds_rate_val, tds_rate_fetch = _get_field("transactionDetails", "tdsRate")
        if tds_rate_fetch == "Validate" and not _is_empty(tds_rate_val):
            _check_proportion("transactionDetails", "tdsRate", "TDS Rate")

        # ── TAX DEPOSIT DETAILS ────────────────────────────────
        _check_amount("taxDepositDetails", "interest", "Interest")
        _check_amount("taxDepositDetails", "fees", "Fees")

        # ── PAYMENT DETAILS ───────────────────────────────────
        _check_required("paymentDetails", "typeOfPayment", "Type of Payment")

        # ── Determine status ───────────────────────────────────
        if errors:
            status = "INVALID"
        elif warnings:
            status = "VALIDATION_REQUIRED"
        else:
            status = "READY"

        return {
            "status": status,
            "errors": errors,
            "warnings": warnings
        }



data_validator = DataValidator()
