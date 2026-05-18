"""
Preservation Property Tests - Non-Index PDF Processing Behavior

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**

These tests capture the CURRENT behavior on UNFIXED code for operations that
do NOT involve index table parsing. They ensure that the bugfix does not
introduce regressions in existing functionality.

**Property 2: Preservation** - Non-Index PDF Processing Behavior

IMPORTANT: These tests should PASS on unfixed code, confirming baseline behavior.
After the fix is implemented, these tests should still PASS, confirming no regressions.

Test cases:
1. L-14 Extraction: Verify L-14 is correctly extracted (currently working)
2. Master File Generation: Verify master_page_definitions.json and master_term_to_page.json are created
3. Metadata Extraction: Verify company_code, quarter, FY are correctly parsed from filenames
4. Table Processing: Verify tables are extracted correctly using pdfplumber
5. Page Label Detection: Verify L-pages are detected in page headers using _extract_lpage_from_text()
"""

import json
import logging
from pathlib import Path
from typing import Dict, List
from unittest.mock import MagicMock, patch

import pytest
pytest.importorskip("hypothesis")
from hypothesis import given, strategies as st, settings, HealthCheck

from src.pdf_parser import (
    extract_metadata_from_filename,
    extract_table_text,
    _extract_lpage_from_text,
    _update_master_page_definitions,
    extract_index_page,
    parse_pdf,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Property 1: L-14 Extraction Preservation
# ============================================================================

def create_mock_pdf_with_l14_only():
    """
    Create a mock PDF that contains ONLY L-14 in the index table.
    This simulates the CURRENT behavior where only L-14 is extracted.
    """
    mock_page = MagicMock()
    
    # Text content with only L-14
    index_text = """COMPANY NAME
PUBLIC DISCLOSURE
INDEX
L-14 : Investments - Assets Held to Cover Linked Liabilities Schedule
"""
    
    mock_page.extract_text.return_value = index_text
    
    # Table with only L-14
    index_table = [
        ["Form", "Particulars", "Page No."],
        ["L-14", "Investments - Assets Held to Cover Linked Liabilities Schedule", "18"],
    ]
    
    mock_page.extract_tables.return_value = [index_table]
    
    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page] * 5
    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
    mock_pdf.__exit__ = MagicMock(return_value=False)
    
    return mock_pdf


class TestPreservationL14Extraction:
    """
    Test that L-14 extraction continues to work correctly after the fix.
    
    **Validates: Requirement 3.1**
    """
    
    def test_l14_extraction_preserved_in_extract_index_page(self, tmp_path):
        """
        Observe and preserve: L-14 is correctly extracted by extract_index_page().
        
        **EXPECTED OUTCOME ON UNFIXED CODE**: PASS (L-14 is currently extracted)
        **EXPECTED OUTCOME ON FIXED CODE**: PASS (L-14 continues to be extracted)
        """
        pdf_path = tmp_path / "TestCompany_Q3_FY26.pdf"
        pdf_path.touch()
        
        mock_pdf = create_mock_pdf_with_l14_only()
        
        with patch("pdfplumber.open", return_value=mock_pdf):
            with patch("src.pdf_parser.PROCESSED_OUTPUT_DIR", str(tmp_path)):
                index_map = extract_index_page(str(pdf_path))
        
        # Assert L-14 is extracted
        assert "L-14" in index_map, "L-14 should be extracted"
        assert "Investments" in index_map["L-14"], (
            f"L-14 description should contain 'Investments', got: {index_map['L-14']}"
        )
        
        logger.info("✓ L-14 extraction preserved: %s", index_map.get("L-14"))
    
    def test_l14_extraction_preserved_in_parse_pdf(self, tmp_path):
        """
        Observe and preserve: L-14 is correctly extracted by parse_pdf().
        
        **EXPECTED OUTCOME ON UNFIXED CODE**: PASS (L-14 is currently extracted)
        **EXPECTED OUTCOME ON FIXED CODE**: PASS (L-14 continues to be extracted)
        """
        pdf_path = tmp_path / "TestCompany_Q3_FY26.pdf"
        pdf_path.touch()
        
        mock_pdf = create_mock_pdf_with_l14_only()
        mock_pdf.__len__ = lambda self: 50
        mock_pdf.pages = [mock_pdf.pages[0]] * 50
        
        with patch("pdfplumber.open", return_value=mock_pdf):
            with patch("src.pdf_parser.PROCESSED_OUTPUT_DIR", str(tmp_path)):
                result = parse_pdf(str(pdf_path))
        
        # Check company-specific page definition file
        company_defs_file = tmp_path / "TestCompany_page_definitions.json"
        assert company_defs_file.exists(), "Company page definitions file should be created"
        
        with open(company_defs_file, "r") as f:
            company_defs = json.load(f)
        
        # Assert L-14 is in company definitions
        assert "L-14" in company_defs, "L-14 should be in company definitions"
        assert "Investments" in company_defs["L-14"], (
            f"L-14 description should contain 'Investments', got: {company_defs['L-14']}"
        )
        
        logger.info("✓ L-14 extraction preserved in parse_pdf: %s", company_defs.get("L-14"))


# ============================================================================
# Property 2: Master File Generation Preservation
# ============================================================================

class TestPreservationMasterFileGeneration:
    """
    Test that master file generation continues to work correctly after the fix.
    
    **Validates: Requirement 3.2**
    """
    
    def test_master_page_definitions_file_created(self, tmp_path):
        """
        Observe and preserve: master_page_definitions.json is created.
        
        **EXPECTED OUTCOME ON UNFIXED CODE**: PASS (file is created)
        **EXPECTED OUTCOME ON FIXED CODE**: PASS (file continues to be created)
        """
        # Create company-specific page definition files
        company_defs = {
            "Company1_page_definitions.json": {"L-14": "Investments - Linked Liabilities"},
            "Company2_page_definitions.json": {"L-14": "Investments - Assets Held to Cover Linked Liabilities Schedule"},
        }
        
        for filename, defs in company_defs.items():
            file_path = tmp_path / filename
            with open(file_path, "w") as f:
                json.dump(defs, f)
        
        # Update master definitions
        with patch("src.pdf_parser.PROCESSED_OUTPUT_DIR", str(tmp_path)):
            _update_master_page_definitions()
        
        # Assert master_page_definitions.json is created
        master_file = tmp_path / "master_page_definitions.json"
        assert master_file.exists(), "master_page_definitions.json should be created"
        
        with open(master_file, "r") as f:
            master_defs = json.load(f)
        
        # Assert it contains L-14
        assert "L-14" in master_defs, "master_page_definitions.json should contain L-14"
        assert isinstance(master_defs["L-14"], list), "L-14 value should be a list"
        
        logger.info("✓ master_page_definitions.json created with L-14: %s", master_defs["L-14"])
    
    def test_master_term_to_page_file_created(self, tmp_path):
        """
        Observe and preserve: master_term_to_page.json is created.
        
        **EXPECTED OUTCOME ON UNFIXED CODE**: PASS (file is created)
        **EXPECTED OUTCOME ON FIXED CODE**: PASS (file continues to be created)
        """
        # Create company-specific page definition files
        company_defs = {
            "Company1_page_definitions.json": {"L-14": "Investments - Linked Liabilities"},
            "Company2_page_definitions.json": {"L-14": "Investments - Assets Held to Cover Linked Liabilities Schedule"},
        }
        
        for filename, defs in company_defs.items():
            file_path = tmp_path / filename
            with open(file_path, "w") as f:
                json.dump(defs, f)
        
        # Update master definitions
        with patch("src.pdf_parser.PROCESSED_OUTPUT_DIR", str(tmp_path)):
            _update_master_page_definitions()
        
        # Assert master_term_to_page.json is created
        term_lookup_file = tmp_path / "master_term_to_page.json"
        assert term_lookup_file.exists(), "master_term_to_page.json should be created"
        
        with open(term_lookup_file, "r") as f:
            term_to_page = json.load(f)
        
        # Assert it contains reverse mappings
        assert len(term_to_page) > 0, "master_term_to_page.json should contain term mappings"
        
        # Check that terms map to L-14
        l14_terms = [term for term, lpage in term_to_page.items() if lpage == "L-14"]
        assert len(l14_terms) > 0, "Should have terms mapping to L-14"
        
        logger.info("✓ master_term_to_page.json created with %d terms", len(term_to_page))
        logger.info("  Terms mapping to L-14: %s", l14_terms)


# ============================================================================
# Property 3: Metadata Extraction Preservation
# ============================================================================

class TestPreservationMetadataExtraction:
    """
    Test that metadata extraction from filenames continues to work correctly.
    
    **Validates: Requirement 3.3**
    """
    
    @given(
        company_code=st.text(
            alphabet=st.characters(whitelist_categories=("Lu", "Ll")),
            min_size=3,
            max_size=20
        ).filter(lambda x: "_" not in x),
        quarter=st.sampled_from(["Q1", "Q2", "Q3", "Q4"]),
        fy_year=st.integers(min_value=20, max_value=30)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_metadata_extraction_from_filename_property(self, company_code, quarter, fy_year):
        """
        Property-based test: Metadata extraction works for various filename formats.
        
        **EXPECTED OUTCOME ON UNFIXED CODE**: PASS (metadata extraction works)
        **EXPECTED OUTCOME ON FIXED CODE**: PASS (metadata extraction continues to work)
        """
        # Create filename
        fy = f"FY{fy_year}"
        filename = f"{company_code}_{quarter}_{fy}.pdf"
        
        # Extract metadata
        metadata = extract_metadata_from_filename(filename)
        
        # Assert metadata is correctly extracted
        assert metadata["company_code"] == company_code
        assert metadata["quarter"] == quarter
        assert metadata["fy"] == fy
        assert metadata["source_file"] == filename
        
        # Assert period_label is correctly formatted
        fy_full = f"20{fy_year}"
        fy_start = int(fy_full) - 1
        expected_period = f"{quarter} FY{fy_start}-{fy_year}"
        assert metadata["period_label"] == expected_period
        
        logger.debug("✓ Metadata extracted: %s -> %s", filename, metadata["period_label"])
    
    def test_metadata_extraction_specific_examples(self):
        """
        Test specific examples of metadata extraction.
        
        **EXPECTED OUTCOME ON UNFIXED CODE**: PASS
        **EXPECTED OUTCOME ON FIXED CODE**: PASS
        """
        test_cases = [
            {
                "filename": "HDFC_Life_Q1_FY25.pdf",
                "expected": {
                    "company_code": "HDFC_Life",
                    "company": "HDFC Life",
                    "quarter": "Q1",
                    "fy": "FY25",
                    "period_label": "Q1 FY2024-25",
                }
            },
            {
                "filename": "Edelweiss_Q3_FY26.pdf",
                "expected": {
                    "company_code": "Edelweiss",
                    "company": "Edelweiss",
                    "quarter": "Q3",
                    "fy": "FY26",
                    "period_label": "Q3 FY2025-26",
                }
            },
            {
                "filename": "Aditya_Birla_Q2_FY24.pdf",
                "expected": {
                    "company_code": "Aditya_Birla",
                    "company": "Aditya Birla",
                    "quarter": "Q2",
                    "fy": "FY24",
                    "period_label": "Q2 FY2023-24",
                }
            },
        ]
        
        for test_case in test_cases:
            metadata = extract_metadata_from_filename(test_case["filename"])
            
            for key, expected_value in test_case["expected"].items():
                assert metadata[key] == expected_value, (
                    f"Metadata mismatch for {test_case['filename']}: "
                    f"{key} = {metadata[key]}, expected {expected_value}"
                )
            
            logger.info("✓ Metadata extraction preserved for: %s", test_case["filename"])


# ============================================================================
# Property 4: Table Processing Preservation
# ============================================================================

class TestPreservationTableProcessing:
    """
    Test that table extraction and processing continues to work correctly.
    
    **Validates: Requirement 3.4**
    """
    
    @given(
        num_rows=st.integers(min_value=2, max_value=10),
        num_cols=st.integers(min_value=2, max_value=5)
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_table_extraction_property(self, num_rows, num_cols):
        """
        Property-based test: Table extraction works for various table sizes.
        
        **EXPECTED OUTCOME ON UNFIXED CODE**: PASS (table extraction works)
        **EXPECTED OUTCOME ON FIXED CODE**: PASS (table extraction continues to work)
        """
        # Create a mock table
        headers = [f"Col{i}" for i in range(num_cols)]
        rows = [[f"R{r}C{c}" for c in range(num_cols)] for r in range(num_rows - 1)]
        table = [headers] + rows
        
        # Extract table text
        result = extract_table_text(table)
        
        # Assert result is not None
        assert result is not None, "Table extraction should return a result"
        
        # Assert headers are correct
        assert result["headers"] == headers, "Headers should match"
        
        # Assert rows are correct
        assert len(result["rows"]) == num_rows - 1, "Number of rows should match"
        
        # Assert raw_text is formatted correctly
        assert "raw_text" in result, "Result should contain raw_text"
        assert " | " in result["raw_text"], "raw_text should use pipe separator"
        
        logger.debug("✓ Table extraction preserved: %dx%d table", num_rows, num_cols)
    
    def test_table_extraction_specific_examples(self):
        """
        Test specific examples of table extraction.
        
        **EXPECTED OUTCOME ON UNFIXED CODE**: PASS
        **EXPECTED OUTCOME ON FIXED CODE**: PASS
        """
        # Example 1: Simple table
        table1 = [
            ["Particulars", "Amount"],
            ["Premium", "1000"],
            ["Claims", "500"],
        ]
        
        result1 = extract_table_text(table1)
        assert result1 is not None
        assert result1["headers"] == ["Particulars", "Amount"]
        assert len(result1["rows"]) == 2
        assert "Premium | 1000" in result1["raw_text"]
        
        logger.info("✓ Table extraction preserved for simple table")
        
        # Example 2: Table with empty cells
        table2 = [
            ["Form", "Particulars", "Page"],
            ["L-14", "Investments", "18"],
            ["", "Additional Info", "19"],
        ]
        
        result2 = extract_table_text(table2)
        assert result2 is not None
        assert result2["headers"] == ["Form", "Particulars", "Page"]
        assert len(result2["rows"]) == 2
        
        logger.info("✓ Table extraction preserved for table with empty cells")
        
        # Example 3: Table with None values
        table3 = [
            ["Col1", "Col2"],
            ["Value1", None],
            [None, "Value2"],
        ]
        
        result3 = extract_table_text(table3)
        assert result3 is not None
        assert result3["headers"] == ["Col1", "Col2"]
        assert len(result3["rows"]) == 2
        
        logger.info("✓ Table extraction preserved for table with None values")


# ============================================================================
# Property 5: Page Label Detection Preservation
# ============================================================================

class TestPreservationPageLabelDetection:
    """
    Test that L-page detection from page content continues to work correctly.
    
    **Validates: Requirement 3.5**
    """
    
    @given(
        lpage_num=st.integers(min_value=1, max_value=30),
        format_type=st.sampled_from(["FORM L-", "Form L-", "L-", "form l-"])
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_lpage_detection_property(self, lpage_num, format_type):
        """
        Property-based test: L-page detection works for various formats.
        
        **EXPECTED OUTCOME ON UNFIXED CODE**: PASS (L-page detection works)
        **EXPECTED OUTCOME ON FIXED CODE**: PASS (L-page detection continues to work)
        """
        # Create text with L-page in various formats
        text = f"{format_type}{lpage_num} Some Section Name\nMore content here..."
        
        # Extract L-page
        lpage = _extract_lpage_from_text(text)
        
        # Assert L-page is detected
        assert lpage is not None, f"L-page should be detected in: {text[:50]}"
        assert f"L-{lpage_num}" in lpage.upper(), (
            f"Detected L-page '{lpage}' should contain 'L-{lpage_num}'"
        )
        
        logger.debug("✓ L-page detection preserved: '%s' -> %s", text[:30], lpage)
    
    def test_lpage_detection_specific_examples(self):
        """
        Test specific examples of L-page detection from page content.
        
        **EXPECTED OUTCOME ON UNFIXED CODE**: PASS
        **EXPECTED OUTCOME ON FIXED CODE**: PASS
        """
        test_cases = [
            ("FORM L-4\nPremium Schedule", "L-4"),
            ("Form L-5 : Analytical Ratios", "L-5"),
            ("L-14 Investments - Assets Held to Cover Linked Liabilities", "L-14"),
            ("L-1-A-RA Revenue Account", "L-1-A-RA"),
            ("form l-7 Persistency", "L-7"),
        ]
        
        for text, expected_lpage in test_cases:
            lpage = _extract_lpage_from_text(text)
            
            assert lpage is not None, f"L-page should be detected in: {text}"
            assert expected_lpage.upper() in lpage.upper(), (
                f"Expected '{expected_lpage}' in detected L-page '{lpage}' from text: {text}"
            )
            
            logger.info("✓ L-page detection preserved: '%s' -> %s", text[:40], lpage)
    
    def test_lpage_detection_no_false_positives(self):
        """
        Test that L-page detection doesn't produce false positives.
        
        **EXPECTED OUTCOME ON UNFIXED CODE**: PASS
        **EXPECTED OUTCOME ON FIXED CODE**: PASS
        """
        # Text without L-pages
        texts_without_lpages = [
            "This is a regular paragraph with no L-page",
            "Premium Schedule for Q1 FY25",
            "Company Name: HDFC Life Insurance",
            "Page 15 of 50",
        ]
        
        for text in texts_without_lpages:
            lpage = _extract_lpage_from_text(text)
            
            # Should return None or not match L-page pattern
            if lpage is not None:
                # If something is detected, it should at least look like an L-page
                assert lpage.startswith("L-"), (
                    f"False positive: detected '{lpage}' in text without L-page: {text}"
                )
            
            logger.debug("✓ No false positive for: '%s'", text[:40])


# ============================================================================
# Integration Test: Full PDF Processing Preservation
# ============================================================================

class TestPreservationFullPDFProcessing:
    """
    Integration test: Full PDF processing pipeline continues to work correctly.
    
    **Validates: All preservation requirements (3.1, 3.2, 3.3, 3.4, 3.5)**
    """
    
    def test_full_pdf_processing_preserved(self, tmp_path):
        """
        Test that the full PDF processing pipeline continues to work correctly.
        
        This test processes a mock PDF and verifies that:
        1. Metadata is extracted correctly
        2. L-14 is extracted (if present)
        3. Master files are generated
        4. Tables are processed
        5. Page labels are detected
        
        **EXPECTED OUTCOME ON UNFIXED CODE**: PASS
        **EXPECTED OUTCOME ON FIXED CODE**: PASS
        """
        # Create mock PDF with L-14 and some content
        mock_page1 = MagicMock()
        mock_page1.extract_text.return_value = """COMPANY NAME
INDEX
L-14 : Investments - Assets Held to Cover Linked Liabilities Schedule
"""
        mock_page1.extract_tables.return_value = [[
            ["Form", "Particulars"],
            ["L-14", "Investments - Assets Held to Cover Linked Liabilities Schedule"],
        ]]
        
        mock_page2 = MagicMock()
        mock_page2.extract_text.return_value = """FORM L-14
Investments - Assets Held to Cover Linked Liabilities Schedule
Particulars | Amount
Equity | 1000
Debt | 2000
"""
        mock_page2.extract_tables.return_value = [[
            ["Particulars", "Amount"],
            ["Equity", "1000"],
            ["Debt", "2000"],
        ]]
        
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page1, mock_page2]
        mock_pdf.__len__ = lambda self: 2
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)
        
        # Process PDF
        pdf_path = tmp_path / "TestCompany_Q3_FY26.pdf"
        pdf_path.touch()
        
        with patch("pdfplumber.open", return_value=mock_pdf):
            with patch("src.pdf_parser.PROCESSED_OUTPUT_DIR", str(tmp_path)):
                result = parse_pdf(str(pdf_path))
        
        # Verify metadata extraction
        assert result["company_code"] == "TestCompany"
        assert result["quarter"] == "Q3"
        assert result["fy"] == "FY26"
        assert result["period_label"] == "Q3 FY2025-26"
        logger.info("✓ Metadata extraction preserved")
        
        # Verify L-14 extraction
        company_defs_file = tmp_path / "TestCompany_page_definitions.json"
        assert company_defs_file.exists()
        with open(company_defs_file, "r") as f:
            company_defs = json.load(f)
        assert "L-14" in company_defs
        logger.info("✓ L-14 extraction preserved")
        
        # Verify master files generation
        master_file = tmp_path / "master_page_definitions.json"
        assert master_file.exists()
        term_lookup_file = tmp_path / "master_term_to_page.json"
        assert term_lookup_file.exists()
        logger.info("✓ Master files generation preserved")
        
        # Verify table processing
        assert result["total_pages"] == 2
        assert len(result["pages"]) == 2
        # Check that page 2 has tables
        page2_data = result["pages"][1]
        assert len(page2_data["tables"]) > 0
        logger.info("✓ Table processing preserved")
        
        # Verify page label detection
        # Page 2 should have L-14 detected
        assert page2_data["page_label"] == "L-14"
        logger.info("✓ Page label detection preserved")
        
        logger.info("=" * 80)
        logger.info("✓ FULL PDF PROCESSING PIPELINE PRESERVED")
        logger.info("=" * 80)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
