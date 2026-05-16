# Task 3.1 Implementation Summary: _split_page_into_subchunks() Function

## Overview
Successfully implemented the `_split_page_into_subchunks()` function in `src/chunker.py` to handle pages that exceed the token limit by intelligently splitting them into sub-chunks while preserving semantic coherence.

## Implementation Details

### Function Signature
```python
def _split_page_into_subchunks(
    page: Dict[str, Any],
    base_metadata: Dict[str, Any],
    max_tokens: int = 7600
) -> List[Dict[str, Any]]
```

### Key Features Implemented

1. **Table Processing (Priority)**
   - Tables are processed first to maintain data integrity
   - Tables ≤ max_tokens are kept intact
   - Large tables are split by rows with repeated headers
   - Minimum 2 data rows per table sub-chunk (when possible)
   - Single table row exceeding max_tokens causes page rejection

2. **Text Block Processing**
   - Text blocks are processed after tables
   - Text blocks ≤ max_tokens are kept intact
   - Large text blocks are split at sentence boundaries (. ! ?)
   - Each text fragment is kept ≥ 100 characters
   - Sentences are accumulated into fragments

3. **Sub-Chunk Management**
   - New sub-chunk created when adding content would exceed max_tokens
   - Maximum 20 sub-chunks per page (excess content truncated)
   - Chunk ID format: `{company_code}_{quarter}_{fy}_page{page_number}_part{n}`

4. **Metadata Enrichment**
   - `is_split`: True for all sub-chunks
   - `total_parts`: Total number of sub-chunks from the page
   - `part_number`: Sequential position (1-based)
   - `table_count`: Number of tables on original page
   - `text_block_count`: Number of text blocks on original page

5. **Error Handling**
   - Raises `ValueError` for unsplittable table rows
   - Logs errors for pages without proper table structure
   - Gracefully handles empty content

### Integration with _chunk_page_wise()

Updated the `_chunk_page_wise()` function to:
- Check if page exceeds MAX_PAGE_TOKENS (8000)
- Call `_split_page_into_subchunks()` with max_tokens=7600 (buffer below limit)
- Handle ValueError exceptions for rejected pages
- Log warnings and info messages for split operations
- Continue processing remaining pages if one is rejected

## Requirements Validated

The implementation satisfies all requirements from the task details:

✅ Accept page dict, base_metadata, and max_tokens parameter (default 7600)
✅ Initialize empty list for sub-chunks and current_content accumulator
✅ Process tables first: keep intact if ≤ max_tokens
✅ If table exceeds max_tokens, split by rows with repeated headers
✅ Ensure minimum 2 data rows per table sub-chunk
✅ Process text_blocks after tables
✅ If text_block exceeds max_tokens, split at sentence boundaries (. ! ?)
✅ Keep each text fragment ≥ 100 characters
✅ Create new sub-chunk when adding content would exceed max_tokens
✅ Set chunk_id format: {company_code}_{quarter}_{fy}_page{page_number}_part{n}
✅ Add is_split=True, total_parts, and part_number to metadata
✅ Reject page if single table row exceeds max_tokens (log error)
✅ Limit to maximum 20 sub-chunks per page

Requirements mapped: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.8, 2.9, 2.10, 2.11, 2.12

## Test Coverage

### Unit Tests (9 tests in test_split_page_into_subchunks.py)
1. ✅ test_split_page_basic - Basic page splitting with oversized content
2. ✅ test_split_page_with_table - Page splitting with table that fits
3. ✅ test_split_page_large_table - Large table splitting with repeated headers
4. ✅ test_split_page_text_at_sentence_boundaries - Text splitting at sentences
5. ✅ test_split_page_unsplittable_table_row - Rejection of unsplittable rows
6. ✅ test_split_page_max_20_subchunks - Maximum 20 sub-chunks limit
7. ✅ test_split_page_minimum_2_rows_per_table_chunk - Minimum 2 rows per chunk
8. ✅ test_split_page_metadata_consistency - Metadata consistency across chunks
9. ✅ test_split_page_empty_content - Empty content handling

### Integration Tests (4 tests in test_integration_page_splitting.py)
1. ✅ test_chunk_document_with_oversized_page - End-to-end oversized page
2. ✅ test_chunk_document_with_large_table - End-to-end large table
3. ✅ test_chunk_document_normal_pages - Normal pages not split
4. ✅ test_chunk_document_rejected_page - Page rejection handling

**Total: 13 tests, all passing**

## Code Quality

- **Type Hints**: Complete type annotations for all parameters and return values
- **Documentation**: Comprehensive docstring with algorithm description
- **Error Handling**: Proper exception handling with descriptive messages
- **Logging**: Appropriate log levels (error, warning, info) for different scenarios
- **Code Style**: Follows existing project conventions and PEP 8 guidelines

## Files Modified

1. **src/chunker.py**
   - Added `_split_page_into_subchunks()` function (220 lines)
   - Updated `_chunk_page_wise()` to use the new function
   - Integrated error handling and logging

2. **tests/test_split_page_into_subchunks.py** (NEW)
   - 9 comprehensive unit tests
   - Tests cover all edge cases and requirements

3. **tests/test_integration_page_splitting.py** (NEW)
   - 4 integration tests
   - Tests verify end-to-end functionality

## Performance Characteristics

- **Single-pass processing**: Content is processed once without redundant iterations
- **Memory efficient**: Uses accumulator pattern to build sub-chunks incrementally
- **Token estimation**: Fast character-based estimation (char_count / 4)
- **Graceful degradation**: Continues processing even if one page fails

## Example Usage

```python
from src.chunker import chunk_document

# Document with oversized page
doc = {
    "company": "Test Insurance",
    "company_code": "TEST_INS",
    "quarter": "Q1",
    "fy": "FY25",
    "period_label": "Q1 FY2024-25",
    "source_file": "TEST_INS_Q1_FY25.pdf",
    "pages": [
        {
            "page_number": 1,
            "page_label": "L-1",
            "section": "Revenue",
            "tables": [...],  # Large table
            "text_blocks": [...]  # Large text
        }
    ]
}

# Automatically splits oversized pages
chunks = chunk_document(doc)

# Result: Multiple sub-chunks with proper metadata
for chunk in chunks:
    print(f"Chunk ID: {chunk['metadata']['chunk_id']}")
    print(f"Is Split: {chunk['metadata']['is_split']}")
    if chunk['metadata']['is_split']:
        print(f"Part {chunk['metadata']['part_number']} of {chunk['metadata']['total_parts']}")
```

## Next Steps

The implementation is complete and ready for use. The function is fully integrated into the chunking pipeline and will automatically handle oversized pages when `PAGE_WISE_CHUNKING=True` in the configuration.

## Notes

- The function uses a conservative max_tokens default of 7600 to leave a buffer below the 8000 token limit
- Table splitting preserves headers in each sub-chunk for context
- Text splitting at sentence boundaries maintains readability
- The 20 sub-chunk limit prevents excessive fragmentation
- Error handling ensures the pipeline continues even if individual pages fail
