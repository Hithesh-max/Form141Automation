import pytest
from apps.backend.app.services.validator import data_validator, PAN_REGEX

def test_pan_regex_valid():
    valid_pans = [
        "ABCDE1234F",
        "BNZPA8765K",
        "AAAAA0000A",
        "ZZZZZ9999Z"
    ]
    for pan in valid_pans:
        is_valid, err = data_validator.validate_pan(pan)
        assert is_valid is True
        assert err is None

def test_pan_regex_invalid():
    invalid_pans = [
        "",
        "12345ABCDE",
        "ABCD1234F",    # 4 letters
        "ABCDEF1234F",  # 6 letters
        "ABCDE12345",   # ends in digit
        "ABCDE123F",    # 3 digits
        None,
        "nan"
    ]
    for pan in invalid_pans:
        is_valid, err = data_validator.validate_pan(pan)
        assert is_valid is False
        assert err is not None

def test_validate_amount():
    valid, _, num = data_validator.validate_amount("1500.50")
    assert valid is True
    assert num == 1500.50

    valid, _, num = data_validator.validate_amount("₹1,50,000")
    assert valid is True
    assert num == 150000.0

    valid, err, _ = data_validator.validate_amount("-500")
    assert valid is False
    assert "greater than or equal to" in err

    valid, err, _ = data_validator.validate_amount("invalid_number")
    assert valid is False

def test_validate_date():
    valid, _, clean = data_validator.validate_date("2026-03-15")
    assert valid is True
    assert clean == "2026-03-15"

    valid, _, clean = data_validator.validate_date("15/03/2026")
    assert valid is True
    assert clean == "2026-03-15"

    valid, err, _ = data_validator.validate_date("not-a-date")
    assert valid is False

def test_validate_dataset_mixed():
    records = [
        {"ClientCode": "C001", "PAN": "ABCDE1234F", "Amount": "50000", "TDS": "500"},
        {"ClientCode": "C002", "PAN": "INVALID_PAN", "Amount": "20000", "TDS": "200"},
        {"ClientCode": "C003", "PAN": "", "Amount": "10000", "TDS": "100"},
        {"ClientCode": "C004", "PAN": "XYZAB5678M", "Amount": "-100", "TDS": "0"},
        {"ClientCode": "C001", "PAN": "ABCDE1234F", "Amount": "30000", "TDS": "300"},  # Duplicate
    ]

    result = data_validator.validate_dataset(records)
    assert result["total_rows"] == 5
    # C001 (row 1) and C001 duplicate (row 5) have valid PAN format, though duplicate generates warning.
    # C002 has invalid PAN -> error
    # C003 has missing PAN -> error
    # C004 has negative amount -> error
    assert result["error_count"] >= 3
    assert result["duplicate_count"] >= 1
    assert result["valid_count"] == 2
