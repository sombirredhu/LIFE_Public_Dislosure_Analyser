"""
Tests for filename → company_code / quarter / FY extraction.
"""

import pytest
from src.pdf_parser import extract_metadata_from_filename


def test_simple_company():
    m = extract_metadata_from_filename("LIC_Q1_FY25.pdf")
    assert m["company_code"] == "LIC"
    assert m["quarter"] == "Q1"
    assert m["fy"] == "FY25"
    assert m["period_label"] == "Q1 FY2024-25"
    assert m["source_file"] == "LIC_Q1_FY25.pdf"


def test_compound_company_code():
    m = extract_metadata_from_filename("HDFC_Life_Q2_FY25.pdf")
    assert m["company_code"] == "HDFC_Life"
    assert m["company"] == "HDFC Life"
    assert m["quarter"] == "Q2"
    assert m["fy"] == "FY25"


def test_triple_part_company():
    m = extract_metadata_from_filename("Canara_HSBC_Q3_FY26.pdf")
    assert m["company_code"] == "Canara_HSBC"
    assert m["quarter"] == "Q3"
    assert m["fy"] == "FY26"
    assert m["period_label"] == "Q3 FY2025-26"


def test_all_quarters():
    for q in ["Q1", "Q2", "Q3", "Q4"]:
        m = extract_metadata_from_filename(f"LIC_{q}_FY25.pdf")
        assert m["quarter"] == q


def test_period_label_fy26():
    m = extract_metadata_from_filename("SBI_Life_Q1_FY26.pdf")
    assert m["period_label"] == "Q1 FY2025-26"


def test_invalid_filename_raises():
    with pytest.raises(ValueError):
        extract_metadata_from_filename("invalid_file.pdf")


def test_missing_quarter_raises():
    with pytest.raises(ValueError):
        extract_metadata_from_filename("HDFC_Life_FY25.pdf")


def test_path_input():
    m = extract_metadata_from_filename(r"data\pdfs\LIC_Q4_FY25.pdf")
    assert m["company_code"] == "LIC"
    assert m["quarter"] == "Q4"
