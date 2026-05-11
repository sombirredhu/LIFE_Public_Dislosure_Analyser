# Metadata Extraction Enhancement Summary

## Overview
Enhanced the PDF parser and chunker to extract company full name and L-page identifier directly from each page's content, rather than relying solely on filename parsing or index pages.

## Changes Made

### 1. PDF Parser (`src/pdf_parser.py`)

#### New Regex Patterns
- **`_PAGE_LPAGE_RE`**: Extracts L-page identifiers from page content
  - Handles formats: "FORM L-4", "Form L-5", "L-6", "L-1-A-RA", etc.
  - Case-insensitive matching
  
- **`_COMPANY_NAME_RE`**: Extracts full company names from page content
  - Matches patterns ending with: "Limited", "Ltd", "Insurance Company Limited", etc.
  - Requires minimum 10 characters to avoid capturing short prefixes
  - Examples: "Aditya Birla Sun Life Insurance Company Limited"

#### New Functions

**`_extract_company_name_from_text(text: str) -> Optional[str]`**
- Searches first 500 characters of page text
- Returns the longest matching company name
- Cleans up extra whitespace

**`_extract_lpage_from_text(text: str) -> Optional[str]`**
- Searches first 200 characters of page text
- Returns L-page identifier in uppercase
- Handles various formats (FORM L-4, L-4, etc.)

#### Modified Functions

**`_process_page()`**
- Now extracts `company_name` from each page's content
- Stores it in page data as `"company_name"` field
- Uses both new extraction functions and legacy `_detect_page_label()`
- Page data structure now includes:
  ```python
  {
      "page_number": int,
      "page_label": str,        # L-page identifier (e.g., "L-4")
      "company_name": str,      # Full company name from page
      "section": str,
      "text_blocks": [...],
      "tables": [...]
  }
  ```

**`parse_pdf()`**
- Enhanced index extraction to better capture L-page descriptions
- Now checks for "list of website disclosure" keyword
- Improved table parsing to handle various index formats
- Processes up to 3 tables per index page (was 2)

### 2. Chunker (`src/chunker.py`)

#### Modified Functions

**`_chunk_page_wise()`**
- Extracts `company_name_from_page` from each page
- Adds it to chunk metadata as `"company_full_name"`
- Chunk metadata now includes:
  ```python
  {
      "chunk_id": str,
      "page_number": int,
      "page_label": str,           # L-page from page content
      "company_full_name": str,    # Full company name from page content
      "section": str,
      "content_type": "page",
      "table_count": int,
      "text_block_count": int,
      "is_split": bool,
      "char_count": int,
      "ingested_at": str,
      # ... other base metadata
  }
  ```

## Benefits

### 1. **Accurate Per-Page Metadata**
- Each chunk now has the exact company name and L-page from that specific page
- No longer relies on filename parsing or index page mapping
- Works even if pages are out of order or index is missing

### 2. **Better Index Capture**
- Index page definitions are now captured more reliably
- Handles various table formats in index pages
- Stores L-page → description mappings for all companies

### 3. **Improved RAG Accuracy**
- Chunks contain precise metadata for filtering
- Users can query by exact company name or L-page
- Better context for LLM responses

## Testing

Created `scripts/test_extraction.py` to verify extraction logic:
- ✓ Extracts company name from index page
- ✓ Extracts company name and L-page from content pages
- ✓ Handles various L-page formats (L-4, L-1-A-RA, Form L-5, etc.)

## Next Steps

1. **Re-index Database**: Run `scripts/ingest_all.py` with `force_reindex=True` to update all chunks with new metadata
2. **Verify Metadata**: Check that `company_full_name` and `page_label` are populated correctly
3. **Update Queries**: Modify RAG queries to use the new `company_full_name` field for filtering

## Example Output

### Before (filename-based):
```json
{
  "metadata": {
    "company": "Aditya Birla",
    "company_code": "Aditya_Birla",
    "page_label": "",  // Often empty
    ...
  }
}
```

### After (content-based):
```json
{
  "metadata": {
    "company": "Aditya Birla",
    "company_code": "Aditya_Birla",
    "company_full_name": "Aditya Birla Sun Life Insurance Company Limited",
    "page_label": "L-4",
    ...
  }
}
```

## Files Modified

1. `src/pdf_parser.py` - Added extraction functions and enhanced index parsing
2. `src/chunker.py` - Added company_full_name to chunk metadata
3. `scripts/test_extraction.py` - New test script for verification

## Configuration

No configuration changes required. The extraction happens automatically during PDF parsing.
