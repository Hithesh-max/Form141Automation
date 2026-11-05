import io
import re
from datetime import datetime, date
import openpyxl
from openpyxl.utils import get_column_letter

FIELD_KEY_MAP = {
    "Login PAN": "loginPan",
    "Login Password": "loginPassword",
    "Applicable Act": "applicableAct",
    "Deductor PAN": "deductorPan",
    "Deductee Type": "deducteeType",
    "Residential Status of the Deductee(s)": "residentialStatus",
    "Deductor Name": "deductorName",
    "Deductor Mobile": "deductorMobile",
    "Deductor Email": "deductorEmail",
    "Deductor Address": "deductorAddress",
    "Deductor Country": "deductorCountry",
    "Tax Year of Transaction": "taxYear",
    "Month of Deduction": "monthOfDeduction",
    "Nature of Transaction in respect of Purchase of Property": "natureOfTransaction",
    "Type of Immovable Property": "propertyType",
    "Flat / Door / Building": "flatDoorBuilding",
    "Road / Street / Block / Sector": "roadStreetBlock",
    "PIN Code": "pinCode",
    "Post Office": "postOffice",
    "Area / Locality": "areaLocality",
    "District": "district",
    "State": "state",
    "Country": "country",
    "Date of Agreement / Booking": "dateOfAgreement",
    "Date of Registration (If available)": "dateOfRegistration",
    "Total Stamp Duty Value of Property": "stampDutyValue",
    "Total Sale Consideration in respect of the Property": "saleConsideration",
    "Type of Payment: Lumpsum or Instalments": "paymentLumpsumOrInstalment",
    "Installment Type": "installmentType",
    "Previous Acknowledgement Number": "previousAckNumber",
    "Total Consideration Paid/Credited in Previous Installment(s)": "previousInstallmentAmount",
    "Buyer's PAN": "buyerPan",
    "Buyer's Name": "buyerName",
    "Buyer's Proportion of Total Sale Consideration (%)": "buyerProportion",
    "Seller's PAN": "sellerPan",
    "Seller's Name": "sellerName",
    "Seller's Contact No.": "sellerContact",
    "Seller's Proportion of Total Sale Consideration (%)": "sellerProportion",
    "PAN of the Deductee": "deducteePan",
    "Name of Deductee": "deducteeName",
    "Proportionate Amount of Stamp Duty Value": "proportionateStampDuty",
    "Total Amount Paid/Credited in Previous Installment(s), if any": "previousInstallmentAmountTransaction",
    "Amount Paid/Credited in Present Transaction": "amountPaidPresent",
    "Amount on which Tax is liable to be deducted": "taxLiableAmount",
    "Date of Payment/Credit": "dateOfPayment",
    "Whether Section 395(1) Applicable": "section395Applicable",
    "Certificate Number": "certificateNumber",
    "Rate at which Tax Deducted (%)": "tdsRate",
    "Amount of Tax Deducted at Source": "tdsAmount",
    "Date of Deduction": "dateOfDeduction",
    "Amount on which TDS to be deducted": "tdsBaseAmount",
    "Amount Deducted": "amountDeducted",
    "Interest": "interest",
    "Fees": "fees",
    "Type of Payment": "typeOfPayment"
}

SECTION_KEY_MAP = {
    "LOGIN": "login",
    "BASIC DETAILS": "basicDetails",
    "IMMOVABLE PROPERTY DETAILS": "immovablePropertyDetails",
    "BUYER / DEDUCTOR DETAILS": "buyerDeductorDetails",
    "SELLER / DEDUCTEE DETAILS": "sellerDeducteeDetails",
    "TRANSACTION DETAILS": "transactionDetails",
    "TAX DEPOSIT DETAILS": "taxDepositDetails",
    "PAYMENT DETAILS": "paymentDetails"
}

def to_camel_case(text: str) -> str:
    """
    Converts an unknown field label into a camelCase string.
    Removes special characters, lowers the first word, and capitalizes subsequent words.
    """
    if not text:
        return ""
    # Remove special characters, keep alphanumeric and spaces
    clean_text = re.sub(r'[^a-zA-Z0-9\s]', '', text)
    words = clean_text.strip().split()
    if not words:
        return "unknownField"
    
    # Lowercase first word, capitalize subsequent words
    return words[0].lower() + ''.join(word.capitalize() for word in words[1:])

def format_value(val):
    """
    Formats the value read from Excel preserving types and conventions.
    - None or empty string -> ""
    - numeric 0 -> "0"
    - float that is integer (e.g. 6000000.0) -> "6000000"
    - datetime/date -> ISO date string (YYYY-MM-DD)
    - float/int -> string
    - string date e.g. "2026-08-01 00:00:00" -> "2026-08-01"
    - string -> string (stripped)
    """
    if val is None:
        return ""
    if isinstance(val, (datetime, date)):
        return val.strftime("%Y-%m-%d")
    if isinstance(val, bool):
        return str(val)
    if isinstance(val, (int, float)):
        if val == 0:
            return "0"
        if isinstance(val, float) and val.is_integer():
            return str(int(val))
        return str(val)
    s = str(val).strip()
    date_match = re.match(r'^(\d{4}-\d{2}-\d{2})', s)
    if date_match and len(s) > 10:
        return date_match.group(1)
    return s

def parse_form141_excel(file_bytes: bytes) -> dict:
    """
    Parses a Form 141 Multi Customer Excel file from raw bytes.
    Detects worksheet automatically by scanning for TYPE, Form 141 Field, and Fetch Type headers.
    Dynamically scans customer columns from Column D onward, ignoring completely empty customer columns.
    Forward-fills TYPE section headings and preserves exact row order and field labels.
    Redacts sensitive passwords at the parser boundary.
    """
    try:
        # data_only=True reads cell values instead of formulas
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    except Exception as e:
        raise ValueError(f"Failed to load Excel file: {str(e)}")

    target_sheet = None
    header_row_idx = None
    col_type_idx = None
    col_field_idx = None
    col_fetch_idx = None

    # 1. Auto-detect worksheet containing: TYPE, Form 141 Field, and Fetch Type
    for name in wb.sheetnames:
        candidate_sheet = wb[name]
        candidate_rows = list(candidate_sheet.iter_rows(values_only=True))
        for r_idx, row in enumerate(candidate_rows[:25]):
            if not row:
                continue
            row_strs = [str(c).strip().upper() if c is not None else "" for c in row]
            has_type = any(s == "TYPE" for s in row_strs)
            has_field = any("FIELD" in s for s in row_strs)
            has_fetch = any("FETCH" in s for s in row_strs)
            if has_type and has_field:
                target_sheet = candidate_sheet
                rows = candidate_rows
                header_row_idx = r_idx
                for c_idx, s in enumerate(row_strs):
                    if s == "TYPE" and col_type_idx is None:
                        col_type_idx = c_idx
                    elif "FIELD" in s and col_field_idx is None:
                        col_field_idx = c_idx
                    elif "FETCH" in s and col_fetch_idx is None:
                        col_fetch_idx = c_idx
                break
        if target_sheet is not None:
            break

    if target_sheet is None:
        # Fallback to active sheet
        target_sheet = wb.active
        rows = list(target_sheet.iter_rows(values_only=True))
        if not rows:
            raise ValueError("Excel sheet is empty")
        for r_idx, row in enumerate(rows[:25]):
            if not row:
                continue
            row_strs = [str(c).strip().upper() if c is not None else "" for c in row]
            if any(s == "TYPE" for s in row_strs) and any("FIELD" in s for s in row_strs):
                header_row_idx = r_idx
                for c_idx, s in enumerate(row_strs):
                    if s == "TYPE" and col_type_idx is None:
                        col_type_idx = c_idx
                    elif "FIELD" in s and col_field_idx is None:
                        col_field_idx = c_idx
                    elif "FETCH" in s and col_fetch_idx is None:
                        col_fetch_idx = c_idx
                break

    if header_row_idx is None:
        header_row_idx = 0
        col_type_idx = 0
        col_field_idx = 1
        col_fetch_idx = 2

    headers = rows[header_row_idx]
    if col_type_idx is None: col_type_idx = 0
    if col_field_idx is None: col_field_idx = 1
    if col_fetch_idx is None: col_fetch_idx = 2

    metadata_col_indices = {col_type_idx, col_field_idx, col_fetch_idx}
    min_customer_col = max(metadata_col_indices) + 1

    # 2. Dynamically detect candidate customer columns from Column D onward
    candidate_customer_columns = []
    for i in range(min_customer_col, len(headers)):
        header = headers[i]
        col_letter = get_column_letter(i + 1)
        label = str(header).strip() if header is not None else f"Customer {len(candidate_customer_columns) + 1}"
        candidate_customer_columns.append((i, col_letter, label))

    if not candidate_customer_columns:
        raise ValueError(f"No customer/filing columns detected from Column D onward in row {header_row_idx + 1}")

    # 3. Filter out completely empty customer columns across all data rows
    data_rows = rows[header_row_idx + 1:]
    active_customers = []
    for col_idx, col_letter, label in candidate_customer_columns:
        has_data = any(
            col_idx < len(row) and row[col_idx] is not None and str(row[col_idx]).strip() != ""
            for row in data_rows
        )
        if has_data:
            active_customers.append((col_idx, col_letter, label))

    final_customers = active_customers if active_customers else candidate_customer_columns
    total_customers = len(final_customers)

    # 4. Initialize structure for each active customer
    customers = []
    for idx, (col_idx, col_letter, label) in enumerate(final_customers, start=1):
        customer_data = {
            "customerIndex": idx,
            "customerLabel": label,
            "customer_index": idx,
            "customer_label": label,
            "source_column": col_letter,
            "fields": [],
            "values": {},
            "rawValues": {}
        }
        for section_val in SECTION_KEY_MAP.values():
            customer_data[section_val] = {}
        customers.append(customer_data)

    fields = []
    current_section = None
    type_headings = []
    type_field_counts = {}

    # 5. Loop through field rows preserving order, TYPE forward-filling, and row numbers
    for r_i, row in enumerate(data_rows):
        if not any(row):  # skip entirely empty rows
            continue

        original_row_num = header_row_idx + 2 + r_i

        raw_type = row[col_type_idx] if col_type_idx < len(row) else None
        raw_field = row[col_field_idx] if col_field_idx < len(row) else None
        raw_fetch_type = row[col_fetch_idx] if col_fetch_idx < len(row) else None

        # Forward fill the TYPE column
        if raw_type is not None and str(raw_type).strip():
            current_section = str(raw_type).strip()

        if not current_section:
            continue

        if raw_field is None or not str(raw_field).strip():
            continue

        field_label = str(raw_field).strip()
        fetch_type = str(raw_fetch_type).strip() if raw_fetch_type is not None else ""

        if current_section not in type_headings:
            type_headings.append(current_section)
            type_field_counts[current_section] = 0
        type_field_counts[current_section] += 1

        # Map section and field keys
        section_key = SECTION_KEY_MAP.get(current_section.upper(), to_camel_case(current_section))
        field_key = FIELD_KEY_MAP.get(field_label, to_camel_case(field_label))
        is_sensitive = "password" in field_label.lower() or field_key == "loginPassword"

        fields.append({
            "type": current_section,
            "sectionKey": section_key,
            "fieldLabel": field_label,
            "fieldKey": field_key,
            "fetchType": fetch_type,
            "original_row_number": original_row_num,
            "is_sensitive": is_sensitive
        })

        for cust_idx, (col_idx, col_letter, cust_label) in enumerate(final_customers):
            # Strict customer isolation: only read row[col_idx]
            val = row[col_idx] if col_idx < len(row) else None
            has_val = val is not None and str(val).strip() != ""
            formatted_val = format_value(val) if has_val else ""

            if is_sensitive:
                safe_val = None
                display_val = "••••••••" if has_val else "Not provided"
            elif has_val:
                if isinstance(val, (int, float)):
                    if val == 0:
                        safe_val = 0
                    elif isinstance(val, float) and val.is_integer():
                        safe_val = int(val)
                    else:
                        safe_val = val
                elif isinstance(val, (datetime, date)):
                    safe_val = val.strftime("%Y-%m-%d")
                else:
                    safe_val = formatted_val
                display_val = str(safe_val)
            else:
                safe_val = None
                ft_lower = fetch_type.lower()
                if "fetch" in ft_lower:
                    display_val = "Pending portal autofetch"
                elif "calc" in ft_lower:
                    display_val = "Pending calculation"
                elif "select" in ft_lower:
                    display_val = "Not selected"
                elif "conditional" in ft_lower:
                    display_val = "Not applicable unless condition is selected"
                else:
                    display_val = "Not provided"

            field_item = {
                "type": current_section,
                "form141_field": field_label,
                "fetch_type": fetch_type,
                "customer_index": cust_idx + 1,
                "customer_label": cust_label,
                "source_column": col_letter,
                "original_row_number": original_row_num,
                "value": safe_val,
                "display_value": display_val,
                "is_sensitive": is_sensitive
            }

            customers[cust_idx]["fields"].append(field_item)

            # Ensure section exists for internal pipeline compatibility
            if section_key not in customers[cust_idx]:
                customers[cust_idx][section_key] = {}

            customers[cust_idx][section_key][field_key] = {
                "value": formatted_val,
                "fetchType": fetch_type,
                "fieldLabel": field_label
            }
            customers[cust_idx]["values"][field_key] = formatted_val
            customers[cust_idx]["rawValues"][field_key] = val

    return {
        "formType": "FORM_141",
        "worksheet": target_sheet.title,
        "totalCustomers": total_customers,
        "customers": customers,
        "fields": fields,
        "type_headings": type_headings,
        "type_field_counts": type_field_counts
    }



def get_flat_payload(customer_dict: dict) -> dict:
    """
    Flattens a single customer's sections into a single dict.
    Returns:
        A dict with camelCase keys and raw values, plus
        _loginPan, _loginPassword, and _fieldMetadata.
    """
    flat_payload = {}
    metadata = {}
    
    # Iterate through all section keys
    for key, value in customer_dict.items():
        if isinstance(value, dict) and key not in ["customerIndex", "customerLabel"]:
            # Process each field within the section
            for field_key, field_data in value.items():
                if isinstance(field_data, dict) and "value" in field_data:
                    flat_payload[field_key] = field_data["value"]
                    metadata[field_key] = field_data.get("fetchType", "")
                    
                    # Add credentials with underscore prefix
                    if field_key == "loginPan":
                        flat_payload["_loginPan"] = field_data["value"]
                    elif field_key == "loginPassword":
                        flat_payload["_loginPassword"] = field_data["value"]

    # In Form 141, Deductor IS Buyer. Provide clean fallbacks if omitted
    # If deductorPan is missing or marked Fetch, prioritize _loginPan if available
    if flat_payload.get("_loginPan"):
        if not flat_payload.get("deductorPan") or metadata.get("deductorPan") in ("Fetch", "Fetch/Select", ""):
            flat_payload["deductorPan"] = flat_payload["_loginPan"]
    if not flat_payload.get("buyerPan"):
        flat_payload["buyerPan"] = flat_payload.get("deductorPan") or flat_payload.get("_loginPan", "")
    # Deductee IS Seller
    if not flat_payload.get("deducteePan"):
        flat_payload["deducteePan"] = flat_payload.get("sellerPan") or flat_payload.get("panOfTheDeductee") or flat_payload.get("sellersPan") or ""
    if not flat_payload.get("sellerPan"):
        flat_payload["sellerPan"] = flat_payload.get("deducteePan") or flat_payload.get("panOfTheDeductee") or ""

    # Field aliases for Angular portal formcontrolname compatibility
    if not flat_payload.get("flatBuilding"):
        flat_payload["flatBuilding"] = flat_payload.get("flatDoorBuilding", "")
    if not flat_payload.get("flatDoorBuilding"):
        flat_payload["flatDoorBuilding"] = flat_payload.get("flatBuilding", "")
    if not flat_payload.get("roadStreet"):
        flat_payload["roadStreet"] = flat_payload.get("roadStreetBlock", "")
    if not flat_payload.get("roadStreetBlock"):
        flat_payload["roadStreetBlock"] = flat_payload.get("roadStreet", "")
    if not flat_payload.get("pincode"):
        flat_payload["pincode"] = flat_payload.get("pinCode", "")
    if not flat_payload.get("pinCode"):
        flat_payload["pinCode"] = flat_payload.get("pincode", "")
    if not flat_payload.get("area"):
        flat_payload["area"] = flat_payload.get("areaLocality", "")
    if not flat_payload.get("areaLocality"):
        flat_payload["areaLocality"] = flat_payload.get("area", "")
    if not flat_payload.get("stampDuty"):
        flat_payload["stampDuty"] = flat_payload.get("stampDutyValue", "")
    if not flat_payload.get("stampDutyValue"):
        flat_payload["stampDutyValue"] = flat_payload.get("stampDuty", "")

    # For Subsequent / Last instalments, Row 32 routes to Row 43 (Transaction Details Column D)
    if not flat_payload.get("previousInstallmentAmountTransaction"):
        flat_payload["previousInstallmentAmountTransaction"] = flat_payload.get("previousInstallmentAmount", "")
    if not flat_payload.get("previousInstallmentAmount"):
        flat_payload["previousInstallmentAmount"] = flat_payload.get("previousInstallmentAmountTransaction", "")

    # Share & proportion defaults
    if not flat_payload.get("buyerShare"):
        flat_payload["buyerShare"] = flat_payload.get("buyerProportion", "100")
    if not flat_payload.get("buyerProportion"):
        flat_payload["buyerProportion"] = flat_payload.get("buyerShare", "100")
    if not flat_payload.get("sellerShare"):
        flat_payload["sellerShare"] = flat_payload.get("sellerProportion", "100")
    if not flat_payload.get("sellerProportion"):
        flat_payload["sellerProportion"] = flat_payload.get("sellerShare", "100")

    # TDS Rate normalization: preserve raw value while providing percentage representation
    raw_rate = flat_payload.get("tdsRate")
    if raw_rate is not None and str(raw_rate).strip() != "":
        try:
            rate_num = float(str(raw_rate).replace("%", "").strip())
            if rate_num <= 0.05 and rate_num > 0:
                # E.g. 0.01 representing 1%
                flat_payload["tdsRatePercent"] = str(int(round(rate_num * 100))) if (rate_num * 100).is_integer() else str(round(rate_num * 100, 2))
            else:
                flat_payload["tdsRatePercent"] = str(int(rate_num)) if rate_num.is_integer() else str(rate_num)
        except Exception:
            flat_payload["tdsRatePercent"] = str(raw_rate)
    else:
        flat_payload["tdsRatePercent"] = "1"

    # If tdsAmount is not explicitly in Excel (e.g. fetchType 'Calculate' or blank),
    # calculate ONLY if explicit valid rate or applicable tax data exists.
    # DO NOT hardcode a universal 1% rate. Preserve None / Pending / Requires Review.
    if not flat_payload.get("tdsAmount") or str(flat_payload.get("tdsAmount")).strip() in ("", "None"):
        try:
            base_str = flat_payload.get("amountPaidPresent") or flat_payload.get("saleConsideration")
            rate_str = flat_payload.get("tdsRate")
            
            if rate_str is not None and str(rate_str).strip() != "":
                clean_rate = float(str(rate_str).replace("%", "").strip())
                eff_rate = clean_rate / 100.0 if clean_rate > 1.0 else clean_rate
                if base_str is not None and str(base_str).strip() != "":
                    clean_base = float(str(base_str).replace(",", "").replace("₹", "").strip())
                    flat_payload["tdsAmount"] = str(round(clean_base * eff_rate, 2))
                else:
                    flat_payload["tdsAmount"] = "Requires Review"
            else:
                # No rate provided - check if lower deduction certificate (Section 395/197) is indicated
                sec395 = flat_payload.get("section395Applicable")
                if sec395 and str(sec395).strip().lower() == "yes":
                    flat_payload["tdsAmount"] = "Requires Review"
                else:
                    flat_payload["tdsAmount"] = "Pending"
        except Exception:
            flat_payload["tdsAmount"] = "Requires Review"

    # Proportionate Stamp Duty Value calculation for Schedule B when fetchType is Calculate
    if not flat_payload.get("proportionateStampDuty") or str(flat_payload.get("proportionateStampDuty")).strip() in ("", "None"):
        try:
            sdv_str = flat_payload.get("stampDutyValue") or flat_payload.get("stampDuty")
            if sdv_str:
                sdv_clean = float(str(sdv_str).replace(",", "").replace("₹", "").strip())
                b_share = float(str(flat_payload.get("buyerProportion", "100")).replace("%", "").strip()) / 100.0
                s_share = float(str(flat_payload.get("sellerProportion", "100")).replace("%", "").strip()) / 100.0
                flat_payload["proportionateStampDuty"] = str(int(round(sdv_clean * b_share * s_share)))
        except Exception:
            pass

    # Tax deposit and liable amount mappings
    amt_present = flat_payload.get("amountPaidPresent") or flat_payload.get("saleConsideration")
    if amt_present:
        if not flat_payload.get("taxLiableAmount"):
            flat_payload["taxLiableAmount"] = amt_present
        if not flat_payload.get("tdsBaseAmount"):
            flat_payload["tdsBaseAmount"] = amt_present

    clean_tds_val = flat_payload.get("tdsAmount")
    if clean_tds_val and clean_tds_val not in ("Pending", "Requires Review"):
        if not flat_payload.get("amountDeducted"):
            flat_payload["amountDeducted"] = clean_tds_val

    if "fees" in flat_payload and "fee" not in flat_payload:
        flat_payload["fee"] = flat_payload["fees"]

    flat_payload["_fieldMetadata"] = metadata
    return flat_payload
