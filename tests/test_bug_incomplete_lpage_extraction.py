"""
Bug Condition Exploration Test - Incomplete L-Page Extraction

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5**

This test encodes the EXPECTED behavior (complete L-page extraction).
It MUST FAIL on unfixed code to confirm the bug exists.

CRITICAL: This test is EXPECTED TO FAIL on unfixed code - failure confirms the bug exists.
DO NOT attempt to fix the test or the code when it fails.

The test will validate the fix when it passes after implementation.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List
from unittest.mock import MagicMock, patch

import pytest

from src.pdf_parser import extract_index_page, parse_pdf

logger = logging.getLogger(__name__)


# Sample IRDAI index table data that should be extracted
# This represents what a real PDF index table contains
# Note: L-1-A-RA is a special case with suffix that may need separate handling
EXPECTED_LPAGE_MAPPINGS = {
    "L-1": "Revenue Account",
    "L-2": "Balance Sheet",
    "L-3": "Receipts and Payments Account",
    "L-4": "Premium Schedule",
    "L-5": "Analytical Ratios",
    "L-6": "Claims",
    "L-7": "Persistency",
    "L-8": "Solvency",
    "L-9": "Investments",
    "L-10": "Exposure",
    "L-11": "NPA Provisions",
    "L-12": "Fraud",
    "L-13": "Share Capital",
    "L-14": "Investments - Assets Held to Cover Linked Liabilities Schedule",
    "L-15": "Pattern of Investment",
    "L-16": "Non-Performing Assets",
    "L-17": "Shareholder Pattern",
}


def create_mock_pdf_with_index_table():
    """
    Create a mock PDF object that simulates a real PDF with an IRDAI index table.
    The index table contains multiple L-pages (L-1 through L-17+).
    
    This simulates the ACTUAL format found in real PDFs like Edelweiss_Q3_FY26.pdf:
    "Sr No Particulars Page No.
     1 L-1-A-RA Revenue Account 1
     2 L-2-A-PL Profit & Loss Account 5
     3 L-3-A-BS Balance Sheet 6
     4 L-4-Premium 7"
    
    The bug: Lines start with serial numbers, not L-pages, so the regex ^(L-\\d+) fails to match!
    """
    # Create mock page with index table
    mock_page = MagicMock()
    
    # Text content with ACTUAL format from real PDFs (with serial numbers)
    # This is the format that FAILS with the current regex
    index_text = """EDELWEISS LIFE INSURANCE COMPANY LIMITED
PUBLIC DISCLOSURE UP TO THE PERIOD ENDED 31 DECEMBER 2025
Sr No Particulars Page No.
1 L-1-A-RA Revenue Account 1
2 L-2-A-PL Profit & Loss Account 5
3 L-3-A-BS Balance Sheet 6
4 L-4-Premium 7
5 L-5-Commission 8
6 L-6 -Operating Expenses 9
7 L-7-Benefits Paid 11
8 L-8 & L-9-Share Capital & Pattern of Shareholding 12
9 L-10 & L11-Reserves and Surplus & Borrowings 15
10 L-12-Investment - Shareholders 16
11 L-13-Investment - Policyholders 17
12 L-14- Investment - Assets Held to cover Linked Liabilities 18
13 L-15-Loans 20
14 L-16-Fixed Assets 21
15 L-17-Cash and Bank Balance 22
"""
    
    mock_page.extract_text.return_value = index_text
    
    # Table data - this might also have the serial number format
    # Simulating how pdfplumber extracts the index table
    index_table = [
        ["Sr No", "Particulars", "Page No."],  # Header row
        ["1", "L-1-A-RA Revenue Account", "1"],
        ["2", "L-2-A-PL Profit & Loss Account", "5"],
        ["3", "L-3-A-BS Balance Sheet", "6"],
        ["4", "L-4-Premium", "7"],
        ["5", "L-5-Commission", "8"],
        ["6", "L-6 -Operating Expenses", "9"],
        ["7", "L-7-Benefits Paid", "11"],
        ["8", "L-8 & L-9-Share Capital & Pattern of Shareholding", "12"],
        ["9", "L-10 & L11-Reserves and Surplus & Borrowings", "15"],
        ["10", "L-12-Investment - Shareholders", "16"],
        ["11", "L-13-Investment - Policyholders", "17"],
        ["12", "L-14- Investment - Assets Held to cover Linked Liabilities", "18"],
        ["13", "L-15-Loans", "20"],
        ["14", "L-16-Fixed Assets", "21"],
        ["15", "L-17-Cash and Bank Balance", "22"],
    ]
    
    mock_page.extract_tables.return_value = [index_table]
    
    # Create mock PDF with multiple pages
    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page] * 5  # Simulate 5 pages (index is in first few pages)
    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
    mock_pdf.__exit__ = MagicMock(return_value=False)
    
    return mock_pdf


class TestBugConditionIncompleteLPageExtraction:
    """
    Bug Condition Exploration Tests
    
    These tests demonstrate the bug on UNFIXED code by asserting the EXPECTED behavior.
    When run on unfixed code, these tests will FAIL, confirming the bug exists.
    
    **Property 1: Bug Condition** - Incomplete L-Page Extraction from Index Table
    """
    
    def test_extract_index_page_extracts_all_lpages(self, tmp_path):
        """
        Test that extract_index_page() extracts ALL L-pages from the index table,
        not just L-14.
        
        **EXPECTED OUTCOME ON UNFIXED CODE**: FAIL
        - Only L-14 will be extracted
        - L-1 through L-13 and L-15+ will be missing
        
        **EXPECTED OUTCOME ON FIXED CODE**: PASS
        - All L-pages (L-1 through L-17+) will be extracted
        """
        # Create a mock PDF file path
        pdf_path = tmp_path / "TestCompany_Q3_FY26.pdf"
        pdf_path.touch()  # Create empty file
        
        # Mock pdfplumber.open to return our mock PDF with index table
        mock_pdf = create_mock_pdf_with_index_table()
        
        with patch("pdfplumber.open", return_value=mock_pdf):
            with patch("src.pdf_parser.PROCESSED_OUTPUT_DIR", str(tmp_path)):
                # Extract index from mock PDF
                index_map = extract_index_page(str(pdf_path))
        
        # ASSERTIONS - These encode the EXPECTED behavior
        # On unfixed code, these will FAIL because only L-14 is extracted
        
        # Assert that L-4 (Premium Schedule) is extracted
        assert "L-4" in index_map, (
            f"L-4 (Premium Schedule) not found in extracted index. "
            f"Only extracted: {list(index_map.keys())}"
        )
        assert index_map.get("L-4") == "Premium Schedule"
        
        # Assert that L-1 (Revenue Account) is extracted
        assert "L-1" in index_map, (
            f"L-1 (Revenue Account) not found in extracted index. "
            f"Only extracted: {list(index_map.keys())}"
        )
        assert index_map.get("L-1") == "Revenue Account"
        
        # Assert that L-2 (Balance Sheet) is extracted
        assert "L-2" in index_map, (
            f"L-2 (Balance Sheet) not found in extracted index. "
            f"Only extracted: {list(index_map.keys())}"
        )
        
        # Assert that L-14 is still extracted (preservation)
        assert "L-14" in index_map, "L-14 should still be extracted"
        
        # Assert that more than just L-14 is extracted
        assert len(index_map) > 1, (
            f"Expected multiple L-pages to be extracted, but only got {len(index_map)}: "
            f"{list(index_map.keys())}"
        )
        
        # Assert that at least 10 L-pages are extracted (reasonable threshold)
        assert len(index_map) >= 10, (
            f"Expected at least 10 L-pages to be extracted, but only got {len(index_map)}: "
            f"{list(index_map.keys())}"
        )
        
        # Log the counterexample for documentation
        logger.info("Extracted L-pages: %s", list(index_map.keys()))
        logger.info("Total L-pages extracted: %d", len(index_map))
        
        # Document which L-pages are missing (for bug analysis)
        expected_lpages = set(EXPECTED_LPAGE_MAPPINGS.keys())
        extracted_lpages = set(index_map.keys())
        missing_lpages = expected_lpages - extracted_lpages
        
        if missing_lpages:
            logger.warning("Missing L-pages: %s", sorted(missing_lpages))
            pytest.fail(
                f"Missing {len(missing_lpages)} L-pages from extraction: {sorted(missing_lpages)}"
            )
    
    def test_parse_pdf_extracts_complete_index_map(self, tmp_path):
        """
        Test that parse_pdf() captures all L-page mappings in the index_map,
        including L-4 (Premium), L-1 (Revenue Account), L-2 (Balance Sheet), etc.
        
        **EXPECTED OUTCOME ON UNFIXED CODE**: FAIL
        - Only L-14 will be in index_map
        - Company-specific page definition file will only contain L-14
        
        **EXPECTED OUTCOME ON FIXED CODE**: PASS
        - All L-pages will be in index_map
        - Company-specific page definition file will contain all L-pages
        """
        # Create a mock PDF file path
        pdf_path = tmp_path / "TestCompany_Q3_FY26.pdf"
        pdf_path.touch()
        
        # Mock pdfplumber.open to return our mock PDF with index table
        mock_pdf = create_mock_pdf_with_index_table()
        # Add more pages for full PDF simulation
        mock_pdf.__len__ = lambda self: 50
        mock_pdf.pages = [mock_pdf.pages[0]] * 50
        
        with patch("pdfplumber.open", return_value=mock_pdf):
            with patch("src.pdf_parser.PROCESSED_OUTPUT_DIR", str(tmp_path)):
                # Parse the PDF
                result = parse_pdf(str(pdf_path))
        
        # Check the company-specific page definition file
        company_defs_file = tmp_path / "TestCompany_page_definitions.json"
        assert company_defs_file.exists(), "Company page definitions file should be created"
        
        with open(company_defs_file, "r") as f:
            company_defs = json.load(f)
        
        # ASSERTIONS - These encode the EXPECTED behavior
        
        # Assert that L-4 (Premium) is in company definitions
        assert "L-4" in company_defs, (
            f"L-4 (Premium Schedule) not found in company definitions. "
            f"Only found: {list(company_defs.keys())}"
        )
        
        # Assert that L-1 (Revenue Account) is in company definitions
        assert "L-1" in company_defs, (
            f"L-1 (Revenue Account) not found in company definitions. "
            f"Only found: {list(company_defs.keys())}"
        )
        
        # Assert that L-2 (Balance Sheet) is in company definitions
        assert "L-2" in company_defs, (
            f"L-2 (Balance Sheet) not found in company definitions. "
            f"Only found: {list(company_defs.keys())}"
        )
        
        # Assert that more than just L-14 is extracted
        assert len(company_defs) > 1, (
            f"Expected multiple L-pages in company definitions, but only got {len(company_defs)}: "
            f"{list(company_defs.keys())}"
        )
        
        # Assert that at least 10 L-pages are in company definitions
        assert len(company_defs) >= 10, (
            f"Expected at least 10 L-pages in company definitions, but only got {len(company_defs)}: "
            f"{list(company_defs.keys())}"
        )
        
        # Log counterexample
        logger.info("Company definitions L-pages: %s", list(company_defs.keys()))
        logger.info("Total L-pages in company definitions: %d", len(company_defs))
    
    def test_master_page_definitions_contains_all_lpages(self, tmp_path):
        """
        Test that master_page_definitions.json contains all L-pages from all companies,
        not just L-14.
        
        **EXPECTED OUTCOME ON UNFIXED CODE**: FAIL
        - master_page_definitions.json will only contain {"L-14": [...]}
        
        **EXPECTED OUTCOME ON FIXED CODE**: PASS
        - master_page_definitions.json will contain L-1 through L-17+
        """
        # Create mock PDFs for multiple companies
        companies = ["Company1", "Company2", "Company3"]
        
        for company in companies:
            pdf_path = tmp_path / f"{company}_Q3_FY26.pdf"
            pdf_path.touch()
            
            mock_pdf = create_mock_pdf_with_index_table()
            mock_pdf.__len__ = lambda self: 50
            mock_pdf.pages = [mock_pdf.pages[0]] * 50
            
            with patch("pdfplumber.open", return_value=mock_pdf):
                with patch("src.pdf_parser.PROCESSED_OUTPUT_DIR", str(tmp_path)):
                    parse_pdf(str(pdf_path))
        
        # Check master_page_definitions.json
        master_file = tmp_path / "master_page_definitions.json"
        assert master_file.exists(), "Master page definitions file should be created"
        
        with open(master_file, "r") as f:
            master_defs = json.load(f)
        
        # ASSERTIONS - These encode the EXPECTED behavior
        
        # Assert that master definitions contain more than just L-14
        assert len(master_defs) > 1, (
            f"Expected multiple L-pages in master definitions, but only got {len(master_defs)}: "
            f"{list(master_defs.keys())}"
        )
        
        # Assert that L-4 (Premium) is in master definitions
        assert "L-4" in master_defs, (
            f"L-4 (Premium Schedule) not found in master definitions. "
            f"Only found: {list(master_defs.keys())}"
        )
        
        # Assert that L-1 (Revenue Account) is in master definitions
        assert "L-1" in master_defs, (
            f"L-1 (Revenue Account) not found in master definitions. "
            f"Only found: {list(master_defs.keys())}"
        )
        
        # Assert that at least 10 L-pages are in master definitions
        assert len(master_defs) >= 10, (
            f"Expected at least 10 L-pages in master definitions, but only got {len(master_defs)}: "
            f"{list(master_defs.keys())}"
        )
        
        # Log counterexample
        logger.info("Master definitions L-pages: %s", list(master_defs.keys()))
        logger.info("Total L-pages in master definitions: %d", len(master_defs))
        
        # Document the bug: only L-14 is present
        if len(master_defs) == 1 and "L-14" in master_defs:
            pytest.fail(
                "BUG CONFIRMED: master_page_definitions.json only contains L-14. "
                "Expected all L-pages (L-1 through L-17+) to be extracted."
            )
    
    def test_lpage_extraction_with_formatting_variations(self, tmp_path):
        """
        Test that L-page extraction handles various formatting variations:
        - With/without colons
        - With/without descriptions
        - Multi-line entries
        - Different column positions in tables
        
        **EXPECTED OUTCOME ON UNFIXED CODE**: FAIL
        - Formatting variations will cause extraction to miss L-pages
        
        **EXPECTED OUTCOME ON FIXED CODE**: PASS
        - All formatting variations will be handled correctly
        """
        # Create mock page with various formatting variations
        mock_page = MagicMock()
        
        # Text with various formats - include index keywords
        text_with_variations = """LIST OF WEBSITE DISCLOSURE
INDEX OF SCHEDULES

L-1: Revenue Account
L-2 Balance Sheet
L-3 : Receipts and Payments Account
L-4:Premium Schedule
L-5  Analytical Ratios
"""
        
        mock_page.extract_text.return_value = text_with_variations
        
        # Table with L-pages in different column positions
        table_variations = [
            ["Form", "Particulars"],
            ["L-6", "Claims"],
            ["L-7", "", "Persistency"],  # Description in column 2
            ["", "L-8", "Solvency"],  # L-page in column 1
            ["L-9 : Investments", ""],  # L-page and description in column 0
        ]
        
        mock_page.extract_tables.return_value = [table_variations]
        
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page] * 5
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)
        
        pdf_path = tmp_path / "TestCompany_Q3_FY26.pdf"
        pdf_path.touch()
        
        with patch("pdfplumber.open", return_value=mock_pdf):
            with patch("src.pdf_parser.PROCESSED_OUTPUT_DIR", str(tmp_path)):
                index_map = extract_index_page(str(pdf_path))
        
        # ASSERTIONS - All formatting variations should be handled
        
        # L-1 with colon and space
        assert "L-1" in index_map, f"L-1 (with colon) not extracted. Got: {list(index_map.keys())}"
        
        # L-2 without colon
        assert "L-2" in index_map, f"L-2 (without colon) not extracted. Got: {list(index_map.keys())}"
        
        # L-3 with colon and space
        assert "L-3" in index_map, f"L-3 (with colon and space) not extracted. Got: {list(index_map.keys())}"
        
        # L-4 with colon, no space
        assert "L-4" in index_map, f"L-4 (with colon, no space) not extracted. Got: {list(index_map.keys())}"
        
        # L-5 with multiple spaces
        assert "L-5" in index_map, f"L-5 (with multiple spaces) not extracted. Got: {list(index_map.keys())}"
        
        # L-6 from table
        assert "L-6" in index_map, f"L-6 (from table) not extracted. Got: {list(index_map.keys())}"
        
        # Assert at least 6 L-pages extracted
        assert len(index_map) >= 6, (
            f"Expected at least 6 L-pages with various formats, but only got {len(index_map)}: "
            f"{list(index_map.keys())}"
        )
        
        logger.info("Extracted L-pages with formatting variations: %s", list(index_map.keys()))


# Counterexample documentation
def test_document_current_bug_state():
    """
    Document the current state of the bug by checking actual processed files.
    This test reads the real master_page_definitions.json to document what's currently extracted.
    
    This test is informational and will PASS even on unfixed code.
    It's used to document the counterexample for the bug report.
    """
    from src.config import PROCESSED_OUTPUT_DIR
    
    master_file = Path(PROCESSED_OUTPUT_DIR) / "master_page_definitions.json"
    
    if master_file.exists():
        with open(master_file, "r") as f:
            master_defs = json.load(f)
        
        logger.info("=" * 80)
        logger.info("CURRENT BUG STATE DOCUMENTATION")
        logger.info("=" * 80)
        logger.info("Master page definitions file: %s", master_file)
        logger.info("L-pages currently extracted: %s", list(master_defs.keys()))
        logger.info("Total L-pages: %d", len(master_defs))
        logger.info("=" * 80)
        
        if len(master_defs) == 1 and "L-14" in master_defs:
            logger.warning("BUG CONFIRMED: Only L-14 is extracted!")
            logger.warning("Expected: L-1 through L-30+ should be extracted")
        
        # Check company-specific files
        processed_dir = Path(PROCESSED_OUTPUT_DIR)
        company_files = list(processed_dir.glob("*_page_definitions.json"))
        
        logger.info("Company-specific page definition files found: %d", len(company_files))
        for company_file in company_files:
            with open(company_file, "r") as f:
                company_defs = json.load(f)
            logger.info("  %s: %d L-pages - %s", 
                       company_file.name, 
                       len(company_defs), 
                       list(company_defs.keys()))
    else:
        logger.warning("Master page definitions file not found: %s", master_file)
        logger.warning("Run PDF processing first to generate the file")
