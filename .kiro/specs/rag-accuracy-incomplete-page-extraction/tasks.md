# Implementation Plan

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Incomplete L-Page Extraction from Index Table
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists
  - **Scoped PBT Approach**: For deterministic bugs, scope the property to the concrete failing case(s) to ensure reproducibility
  - Test that `extract_index_page()` and `parse_pdf()` extract ALL L-pages (L-1 through L-30+) from the IRDAI index table, not just L-14
  - Test with actual company PDFs that contain full index tables with multiple L-page entries
  - Assert that extracted index_map contains L-4 (Premium Schedule), L-1 (Revenue Account), L-2 (Balance Sheet), and other L-pages beyond L-14
  - Assert that master_page_definitions.json contains more than just L-14 after processing all PDFs
  - Test query retrieval: assert that querying "premium for all companies" returns results from all 6 companies
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bug exists)
  - Document counterexamples found:
    - Which L-pages are missing from extracted index_map (expected: only L-14 present)
    - How many companies return results for "premium" query (expected: 3-4 instead of 6)
    - Contents of master_page_definitions.json (expected: only L-14)
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Non-Index PDF Processing Behavior
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code for non-buggy inputs (operations that don't involve index table parsing)
  - Write property-based tests capturing observed behavior patterns from Preservation Requirements
  - Property-based testing generates many test cases for stronger guarantees
  - Test cases to observe and preserve:
    1. **L-14 Extraction**: Observe that L-14 is correctly extracted on unfixed code, write test to verify this continues
    2. **Master File Generation**: Observe that master_page_definitions.json and master_term_to_page.json are created, write test to verify this continues
    3. **Metadata Extraction**: Observe that company_code, quarter, FY are correctly parsed from filenames, write test to verify this continues
    4. **Table Processing**: Observe that tables are extracted correctly using pdfplumber, write test to verify this continues
    5. **Page Label Detection**: Observe that L-pages are detected in page headers using `_extract_lpage_from_text()`, write test to verify this continues
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 3. Fix for incomplete L-page extraction from IRDAI index table

  - [x] 3.1 Implement the fix in src/pdf_parser.py
    - **Improve Regex Pattern Matching**:
      - Modify `_LPAGE_LABEL_RE` to handle leading whitespace: change from `r'^(L-\d+)\s*[:\-]?\s*(.*)'` to `r'\s*(L-\d+)\s*[:\-]?\s*(.*)'` (remove `^` anchor)
      - Ensure pattern handles L-pages with suffixes like "L-1-A-RA"
      - Consider adding a second pattern for table cells if needed
    - **Enhance Table Parsing Logic in extract_index_page()**:
      - Check ALL columns in each row for L-page patterns, not just column 0
      - When L-page is found in column N, look for description in columns N+1, N+2, etc.
      - Handle cases where description spans multiple columns (join with spaces)
      - Continue processing all rows even after finding matches (don't break early)
      - Remove restrictive checks like `len(row) < 2` that skip valid rows
    - **Enhance Table Parsing Logic in parse_pdf()**:
      - Apply same improvements as extract_index_page()
      - Check all cells for L-page pattern, not just cell0
      - Handle cases where description is in cell0 after L-page
      - Handle cases where description is in any subsequent cell
    - **Add Multi-Line Handling**:
      - When processing text lines, if a line matches L-page pattern but has no description, check the next line
      - Implement lookahead: `if m and not m.group(2).strip() and i+1 < len(lines): section = lines[i+1].strip()`
    - **Expand Index Detection**:
      - Increase pages scanned from 2 to 5 in `parse_pdf()` (already 5 in `extract_index_page()`)
      - Make `has_index_keywords` check more comprehensive: add keywords like 'form', 'schedule', 'particulars'
    - **Add Logging and Debugging**:
      - Log each L-page as it's extracted: `logger.debug("Extracted %s: %s", label, section)`
      - Log total count at end: `logger.info("Extracted %d L-pages from index", len(index_map))`
    - **Robust Cell Processing**:
      - Handle None values and empty strings carefully
      - Strip whitespace and normalize formatting before regex matching
      - Handle cases where cell contains multiple lines (split and check each line)
    - _Bug_Condition: isBugCondition(input) where input.containsLPages(['L-1', 'L-2', 'L-3', 'L-4', ..., 'L-13', 'L-15', ..., 'L-30']) AND extractedLPages(input) = ['L-14'] AND NOT allLPagesExtracted(input)_
    - _Expected_Behavior: For any PDF index table that contains multiple L-page entries (L-1 through L-30+), the fixed extraction functions SHALL extract all L-page mappings present in the index, not just L-14. The extracted index_map SHALL contain all L-pages with their corresponding section names, regardless of formatting variations._
    - _Preservation: All inputs that do NOT involve the IRDAI index table parsing should be completely unaffected by this fix. This includes: PDF parsing for non-index pages, text block extraction, company name extraction, page-by-page processing, JSON output generation, L-14 extraction, master file generation, metadata extraction, table processing, and page label detection._
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 3.1, 3.2, 3.3, 3.4, 3.5_

  - [x] 3.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Complete L-Page Extraction from Index Table
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 1
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - Verify that:
      - `extract_index_page()` and `parse_pdf()` now extract all L-pages (L-1 through L-30+)
      - Extracted index_map contains L-4, L-1, L-2, and other L-pages beyond L-14
      - master_page_definitions.json contains all unique L-page mappings from all companies
      - Query for "premium for all companies" returns results from all 6 companies
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [x] 3.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Non-Index PDF Processing Behavior
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm all preservation tests still pass after fix:
      - L-14 extraction continues to work correctly
      - Master file generation creates both master_page_definitions.json and master_term_to_page.json
      - Metadata extraction correctly parses company_code, quarter, FY
      - Table processing extracts tables correctly using pdfplumber
      - Page label detection identifies L-pages in page headers using `_extract_lpage_from_text()`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 4. Checkpoint - Ensure all tests pass
  - Run all tests (bug condition exploration test + preservation tests)
  - Verify all tests pass
  - Test with actual company PDFs to confirm:
    - All 6 companies have complete page definition files with all L-pages
    - master_page_definitions.json contains all L-pages from all companies
    - Queries for financial terms return results from all 6 companies
  - Ask the user if questions arise
