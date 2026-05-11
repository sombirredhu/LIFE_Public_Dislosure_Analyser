# RAG Accuracy - Incomplete Page Extraction Bugfix Design

## Overview

The RAG system fails to return results from all 6 uploaded company PDFs because the `extract_index_page()` and `parse_pdf()` functions in `src/pdf_parser.py` only extract L-14 from the IRDAI index table, missing critical pages like L-4 (Premium), L-1 through L-13, and L-15 through L-30+. This incomplete extraction cascades through the system: master definitions only contain L-14, company-specific page definition files are incomplete, and queries for financial terms fail to retrieve relevant chunks from most companies.

The fix requires improving the regex pattern matching and table parsing logic to correctly extract all L-page entries from the index table, regardless of formatting variations (with/without colons, with/without descriptions, multi-line entries, etc.).

## Glossary

- **Bug_Condition (C)**: The condition that triggers the bug - when the index table contains L-pages other than L-14, but the extraction logic fails to capture them
- **Property (P)**: The desired behavior when processing the index table - all L-page mappings should be extracted and stored
- **Preservation**: Existing L-14 extraction, master file generation, metadata extraction, and table processing that must remain unchanged by the fix
- **extract_index_page()**: The function in `src/pdf_parser.py` that scans the first 5 pages for the IRDAI L-page index table
- **parse_pdf()**: The function in `src/pdf_parser.py` that processes a PDF and extracts the index from the first 2 pages
- **_LPAGE_LABEL_RE**: The regex pattern `r'^(L-\d+)\s*[:\-]?\s*(.*)'` used to match L-page labels in text lines
- **index_map**: The dictionary mapping L-page labels (e.g., "L-4") to section names (e.g., "Premium Schedule")
- **master_page_definitions.json**: The merged file containing all unique L-page mappings from all companies

## Bug Details

### Bug Condition

The bug manifests when the `extract_index_page()` or `parse_pdf()` function processes the IRDAI index table in the first few pages of a PDF. The regex pattern `_LPAGE_LABEL_RE` and table parsing logic are either:
1. Not matching L-page entries due to formatting variations (missing colons, extra spaces, multi-line entries)
2. Stopping early after finding L-14 instead of continuing to extract all entries
3. Failing to parse table rows correctly when L-pages are in different column positions
4. Not handling edge cases like L-pages with suffixes (L-1-A-RA) or without descriptions

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type PDFIndexTable
  OUTPUT: boolean
  
  RETURN input.containsLPages(['L-1', 'L-2', 'L-3', 'L-4', ..., 'L-13', 'L-15', ..., 'L-30'])
         AND extractedLPages(input) = ['L-14']
         AND NOT allLPagesExtracted(input)
END FUNCTION
```

### Examples

- **Example 1**: Index table contains "L-4 Premium Schedule" but regex fails to match because there's no colon after L-4
- **Example 2**: Index table contains "L-1\nRevenue Account" (multi-line) but line-by-line parsing misses the description
- **Example 3**: Table row has L-page in column 0 and description in column 2 (skipping column 1), but parser only checks column 1
- **Example 4**: Index table contains "L-14 : Investments - Assets Held to Cover Linked Liabilities Schedule" and this is correctly extracted (current working case)
- **Edge Case**: Index table contains "L-1-A-RA" with suffix, should be extracted as "L-1-A-RA"

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- L-14 extraction must continue to work exactly as before (currently working)
- Master file generation (`_update_master_page_definitions()`) must continue to create both master_page_definitions.json and master_term_to_page.json
- Metadata extraction from filenames must continue to parse company_code, quarter, and FY correctly
- Table extraction using pdfplumber must continue to work for all table data
- Page label detection from page content (`_extract_lpage_from_text()`) must continue to identify L-pages in page headers

**Scope:**
All inputs that do NOT involve the IRDAI index table parsing should be completely unaffected by this fix. This includes:
- PDF parsing for non-index pages
- Text block extraction
- Company name extraction
- Page-by-page processing
- JSON output generation

## Hypothesized Root Cause

Based on the bug description and code analysis, the most likely issues are:

1. **Regex Pattern Too Restrictive**: The `_LPAGE_LABEL_RE` pattern `r'^(L-\d+)\s*[:\-]?\s*(.*)'` may be:
   - Requiring the line to start with L-page (^) which fails if there's leading whitespace or table formatting
   - Not handling cases where the description is on the next line or in a different table column
   - The `[:\-]?` makes colon/dash optional but may not handle all formatting variations

2. **Table Parsing Logic Incomplete**: In `extract_index_page()` and `parse_pdf()`, the table parsing:
   - Only checks `row[1:]` for section description, missing cases where description is in column 0 with L-page
   - May stop after finding first match instead of continuing through all rows
   - Doesn't handle multi-column tables where L-page and description are separated by empty columns

3. **Early Termination**: The code may have a logic error that causes it to stop extracting after L-14:
   - The condition `if label not in index_map` prevents duplicates but shouldn't cause early termination
   - However, if there's an exception or break statement triggered after L-14, it would explain the behavior

4. **Index Detection Logic**: The `has_index_keywords` check in `parse_pdf()` may be:
   - Too restrictive, causing the function to skip pages that contain the index
   - Not checking all relevant pages (currently only checks first 2 pages)

5. **Line-by-Line Processing Limitation**: Processing text line-by-line may miss multi-line entries:
   - If "L-4" is on one line and "Premium Schedule" is on the next line, they won't be matched together
   - Table extraction should handle this, but if the index is in plain text format, it will fail

## Correctness Properties

Property 1: Bug Condition - Complete L-Page Extraction

_For any_ PDF index table that contains multiple L-page entries (L-1 through L-30+), the fixed extraction functions SHALL extract all L-page mappings present in the index, not just L-14. The extracted index_map SHALL contain all L-pages with their corresponding section names, regardless of formatting variations (with/without colons, with/without descriptions, multi-line entries, different column positions).

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6**

Property 2: Preservation - Existing Extraction Behavior

_For any_ PDF processing that does NOT involve the IRDAI index table parsing (such as L-14 extraction, master file generation, metadata extraction, table processing, and page label detection), the fixed code SHALL produce exactly the same behavior as the original code, preserving all existing functionality for non-index-related operations.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct:

**File**: `src/pdf_parser.py`

**Function**: `extract_index_page()` and `parse_pdf()`

**Specific Changes**:

1. **Improve Regex Pattern Matching**:
   - Modify `_LPAGE_LABEL_RE` to handle leading whitespace: `r'\s*(L-\d+)\s*[:\-]?\s*(.*)'` (remove `^` anchor)
   - Or add a second pattern specifically for table cells: `r'(L-\d+(?:-[A-Z]+)?)\s*[:\-]?\s*(.*)'`
   - Ensure pattern handles L-pages with suffixes like "L-1-A-RA"

2. **Enhance Table Parsing Logic**:
   - In both functions, when processing table rows, check ALL columns for L-page patterns, not just column 0
   - If L-page is found in column N, look for description in columns N+1, N+2, etc.
   - Handle cases where description spans multiple columns (join with spaces)
   - Continue processing all rows even after finding matches (don't break early)

3. **Add Multi-Line Handling**:
   - When processing text lines, if a line matches L-page pattern but has no description, check the next line
   - Implement a lookahead mechanism: `if m and not m.group(2).strip() and i+1 < len(lines): section = lines[i+1].strip()`

4. **Expand Index Detection**:
   - Increase the number of pages scanned from 2 to 5 in `parse_pdf()` (already 5 in `extract_index_page()`)
   - Make `has_index_keywords` check more comprehensive: add keywords like 'form', 'schedule', 'particulars'

5. **Add Logging and Debugging**:
   - Log each L-page as it's extracted: `logger.debug("Extracted %s: %s", label, section)`
   - Log total count at end: `logger.info("Extracted %d L-pages from index", len(index_map))`
   - This will help identify if extraction stops early or if certain patterns aren't matching

6. **Robust Cell Processing**:
   - When checking table cells, handle None values and empty strings more carefully
   - Strip whitespace and normalize formatting before regex matching
   - Handle cases where cell contains multiple lines (split and check each line)

### Detailed Implementation Plan

**In `extract_index_page()`**:
```python
# Current problematic code:
for row in table:
    if not row:
        continue
    cell0 = str(row[0]).strip() if row[0] else ""
    tm = _LPAGE_LABEL_RE.match(cell0)
    if tm:
        label = tm.group(1).upper()
        section_from_row = ""
        for cell in row[1:]:  # Only checks columns after first
            if cell and str(cell).strip():
                section_from_row = str(cell).strip()
                break
        if section_from_row and label not in index_map:
            index_map[label] = section_from_row

# Fixed code should:
# 1. Check ALL cells in row for L-page pattern
# 2. When found, look for description in remaining cells
# 3. Handle multi-column descriptions
# 4. Continue through all rows
```

**In `parse_pdf()`**:
```python
# Current problematic code:
for table in tables[:3]:  # Check first 3 tables
    for row in table:
        if not row or len(row) < 2:
            continue
        
        cell0 = str(row[0]).strip() if row[0] else ""
        cell1 = str(row[1]).strip() if row[1] else ""
        
        tm = _LPAGE_LABEL_RE.match(cell0)
        if tm:
            label = tm.group(1).upper()
            section_from_row = tm.group(2).strip() if tm.group(2).strip() else cell1
            if section_from_row and label not in index_map:
                index_map[label] = section_from_row

# Fixed code should:
# 1. Remove `len(row) < 2` check (some tables have 1 column with L-page and description together)
# 2. Check all cells for L-page pattern, not just cell0
# 3. Handle cases where description is in cell0 after L-page
# 4. Handle cases where description is in any subsequent cell
```

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bug on unfixed code, then verify the fix works correctly and preserves existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE implementing the fix. Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Write tests that process actual PDF files with known index tables containing multiple L-pages (L-1 through L-30+). Run these tests on the UNFIXED code to observe failures and understand the root cause. Examine the extracted index_map to see which L-pages are missing.

**Test Cases**:
1. **Complete Index Extraction Test**: Process a PDF with full index table (L-1 through L-30+), assert that all L-pages are extracted (will fail on unfixed code - only L-14 extracted)
2. **L-4 Premium Extraction Test**: Process a PDF and assert that L-4 (Premium Schedule) is extracted (will fail on unfixed code)
3. **L-1 Revenue Account Test**: Process a PDF and assert that L-1 (Revenue Account) is extracted (will fail on unfixed code)
4. **Master Definitions Test**: After processing all PDFs, check master_page_definitions.json contains more than just L-14 (will fail on unfixed code)
5. **Query Retrieval Test**: Query for "premium for all companies" and assert results from all 6 companies (will fail on unfixed code - only 3-4 companies returned)

**Expected Counterexamples**:
- `extract_index_page()` returns `{"L-14": "Investments - Assets Held to Cover Linked Liabilities Schedule"}` instead of full index
- `parse_pdf()` produces index_map with only L-14
- master_page_definitions.json contains only `{"L-14": [...]}`
- Queries for "premium" return 3-4 companies instead of 6
- Possible causes: regex not matching, table parsing incomplete, early termination, multi-line entries missed

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds (PDFs with multi-page indexes), the fixed function produces the expected behavior (extracts all L-pages).

**Pseudocode:**
```
FOR ALL pdf WHERE isBugCondition(pdf.index_table) DO
  result := extract_index_page_fixed(pdf)
  ASSERT expectedBehavior(result)
  ASSERT result.contains_all_lpages(['L-1', 'L-2', 'L-3', 'L-4', ..., 'L-30'])
  ASSERT len(result) > 1  # More than just L-14
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold (non-index-related PDF processing), the fixed function produces the same result as the original function.

**Pseudocode:**
```
FOR ALL operation WHERE NOT isIndexExtraction(operation) DO
  ASSERT original_function(operation) = fixed_function(operation)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain
- It catches edge cases that manual unit tests might miss
- It provides strong guarantees that behavior is unchanged for all non-buggy inputs

**Test Plan**: Observe behavior on UNFIXED code first for non-index operations (metadata extraction, table processing, page label detection), then write property-based tests capturing that behavior.

**Test Cases**:
1. **L-14 Extraction Preservation**: Observe that L-14 is correctly extracted on unfixed code, then write test to verify this continues after fix
2. **Master File Generation Preservation**: Observe that master_page_definitions.json and master_term_to_page.json are created on unfixed code, then write test to verify this continues after fix
3. **Metadata Extraction Preservation**: Observe that company_code, quarter, FY are correctly parsed on unfixed code, then write test to verify this continues after fix
4. **Table Processing Preservation**: Observe that tables are extracted correctly on unfixed code, then write test to verify this continues after fix
5. **Page Label Detection Preservation**: Observe that L-pages are detected in page headers on unfixed code, then write test to verify this continues after fix

### Unit Tests

- Test regex pattern matching with various L-page formats (with/without colons, with/without descriptions, with suffixes)
- Test table parsing with different column configurations (L-page in column 0, 1, 2; description in various columns)
- Test multi-line entry handling (L-page on one line, description on next)
- Test edge cases (empty cells, None values, extra whitespace, special characters)
- Test that all L-pages from L-1 to L-30+ are extracted from sample index tables

### Property-Based Tests

- Generate random index table structures with varying L-page counts and formats, verify all are extracted
- Generate random table layouts (different column counts, cell positions), verify extraction works for all
- Generate random PDFs with indexes on different pages (1-5), verify detection works
- Test that for all non-index operations, behavior is identical before and after fix

### Integration Tests

- Test full PDF processing pipeline with real company PDFs
- Test that master_page_definitions.json contains all L-pages after processing all companies
- Test that queries for financial terms (premium, revenue, balance sheet) return results from all 6 companies
- Test that company-specific page definition files contain complete L-page sets
- Test that the RAG system can successfully retrieve chunks from all companies for various queries
