# Implementation Plan: Page-Wise Chunking

## Overview

This implementation plan breaks down the page-wise chunking feature into discrete, executable tasks. The feature will transform the current text-based chunking strategy (which creates ~1,820 overlapping chunks) into a page-wise strategy that creates one chunk per page (~300-400 chunks), preserving semantic coherence by keeping complete tables and related text together.

The implementation follows a layered approach:
1. Configuration setup (enable/disable feature)
2. Core page-wise chunking logic (combine page content)
3. Token limit handling (split oversized pages)
4. Metadata enrichment (page statistics)
5. Testing and validation

## Tasks

- [x] 1. Set up configuration for page-wise chunking
  - Verify PAGE_WISE_CHUNKING and MAX_PAGE_TOKENS are already defined in src/config.py
  - Update .env file with PAGE_WISE_CHUNKING=True and MAX_PAGE_TOKENS=8000
  - Add configuration validation to ensure MAX_PAGE_TOKENS is between 1000 and 10000
  - _Requirements: 3.1, 3.2, 3.5_

- [x] 2. Implement core page-wise chunking functions
  - [x] 2.1 Verify _estimate_tokens() function exists and works correctly
    - Confirm function estimates tokens as char_count / 4
    - Test with sample text of known length
    - _Requirements: 2.7_

  - [x] 2.2 Implement _combine_page_content() function
    - Combine all tables from page (pipe-separated format)
    - Append all text_blocks from page
    - Separate tables and text_blocks with "\n\n"
    - Handle missing or empty tables/text_blocks arrays
    - Return combined text string
    - _Requirements: 1.1, 1.3_

  - [ ]* 2.3 Write unit tests for _combine_page_content()
    - Test page with tables only
    - Test page with text_blocks only
    - Test page with mixed content
    - Test page with empty arrays
    - _Requirements: 8.6_

  - [x] 2.4 Implement _chunk_page_wise() main function
    - Iterate through pages array from parsed_doc
    - For each page, call _combine_page_content()
    - Skip pages with empty content (no tables and no text_blocks)
    - Create chunk dictionary with text and metadata
    - Set chunk_id format: {company_code}_{quarter}_{fy}_page{page_number}
    - Set content_type to "page"
    - Populate metadata: company, company_code, quarter, fy, period_label, source_file, page_number, page_label, section
    - Set char_count, ingested_at timestamp
    - Return list of chunks
    - _Requirements: 1.1, 1.2, 1.4, 1.5, 1.6, 1.7, 1.8_

  - [ ]* 2.5 Write unit tests for _chunk_page_wise()
    - Test single page with tables and text
    - Test multiple pages
    - Test empty page handling
    - Test metadata population
    - Verify chunk_id format
    - _Requirements: 8.1, 8.7_

- [x] 3. Implement token limit handling for oversized pages
  - [x] 3.1 Implement _split_page_into_subchunks() function
    - Accept page dict, base_metadata, and max_tokens parameter (default 7600)
    - Initialize empty list for sub-chunks and current_content accumulator
    - Process tables first: keep intact if ≤ max_tokens
    - If table exceeds max_tokens, split by rows with repeated headers
    - Ensure minimum 2 data rows per table sub-chunk
    - Process text_blocks after tables
    - If text_block exceeds max_tokens, split at sentence boundaries (. ! ?)
    - Keep each text fragment ≥ 100 characters
    - Create new sub-chunk when adding content would exceed max_tokens
    - Set chunk_id format: {company_code}_{quarter}_{fy}_page{page_number}_part{n}
    - Add is_split=True, total_parts, and part_number to metadata
    - Reject page if single table row exceeds max_tokens (log error)
    - Limit to maximum 20 sub-chunks per page
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.8, 2.9, 2.10, 2.11, 2.12_

  - [ ]* 3.2 Write unit tests for _split_page_into_subchunks()
    - Test page exceeding token limit (40,000 chars)
    - Test large table splitting with header repetition
    - Test text_block splitting at sentence boundaries
    - Test unsplittable table row rejection
    - Verify sub-chunk metadata (part_number, total_parts, is_split)
    - Test maximum 20 sub-chunks limit
    - _Requirements: 8.2, 8.7, 8.8_

  - [x] 3.3 Integrate token limit handling into _chunk_page_wise()
    - After combining page content, estimate tokens using _estimate_tokens()
    - If tokens > MAX_PAGE_TOKENS, call _split_page_into_subchunks()
    - Otherwise, create single chunk with is_split=False
    - Ensure all chunks pass through quality validation
    - _Requirements: 2.1, 2.9_

- [x] 4. Implement metadata enrichment for page statistics
  - [x] 4.1 Add table_count and text_block_count to chunk metadata
    - Count number of tables in page["tables"] array
    - Count number of text_blocks in page["text_blocks"] array
    - Add both counts to chunk metadata
    - Handle missing arrays (treat as 0)
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [x] 4.2 Add is_split, total_parts, and part_number metadata
    - For single-page chunks: set is_split=False, omit total_parts and part_number
    - For split pages: set is_split=True, add total_parts (2-999) and part_number (1-based)
    - Ensure part_number ≤ total_parts
    - _Requirements: 6.5, 6.6, 6.7, 6.8, 6.9_

  - [ ]* 4.3 Write unit tests for metadata enrichment
    - Test table_count and text_block_count for various page types
    - Test is_split=False for single chunks
    - Test is_split=True with correct total_parts and part_number
    - Verify metadata schema completeness
    - _Requirements: 8.8_

- [x] 5. Modify chunk_document() to support strategy selection
  - [x] 5.1 Add strategy selection logic to chunk_document()
    - Check PAGE_WISE_CHUNKING config flag
    - If True: call _chunk_page_wise()
    - If False: use existing text-based chunking logic
    - Maintain existing function signature for backward compatibility
    - _Requirements: 3.3, 3.4, 4.5_

  - [ ]* 5.2 Write unit tests for configuration switching
    - Test PAGE_WISE_CHUNKING=True produces page-wise chunks
    - Test PAGE_WISE_CHUNKING=False produces text-based chunks
    - Verify chunk_id format differences
    - Verify chunk count differences (75-80% reduction)
    - _Requirements: 8.3, 8.5_

- [x] 6. Implement chunk quality validation
  - [x] 6.1 Add validation logic to filter malformed chunks
    - Check if chunk text is empty or whitespace-only
    - Check if char_count < MIN_CHUNK_SIZE
    - Exclude invalid chunks from output list
    - Log warning for skipped pages
    - _Requirements: 5.1, 5.2, 5.3_

  - [x] 6.2 Add processing statistics logging
    - Log total chunks created per document
    - Log average chunk size in characters
    - Log processing time per document
    - Log page_number and sub-chunk count for split pages
    - _Requirements: 5.4, 5.5, 7.5_

  - [ ]* 6.3 Write unit tests for chunk quality validation
    - Test empty chunk exclusion
    - Test whitespace-only chunk exclusion
    - Test MIN_CHUNK_SIZE threshold
    - Verify logging messages
    - _Requirements: 8.6_

- [x] 7. Checkpoint - Ensure all unit tests pass
  - Run pytest on all new test files
  - Verify code coverage ≥ 90% for modified chunker.py functions
  - Fix any failing tests
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Create integration tests for end-to-end pipeline
  - [x] 8.1 Write integration test for PDF → chunks → embeddings → ChromaDB
    - Use sample PDF file from data/pdfs/
    - Call parse_pdf() to get parsed_doc
    - Call chunk_document() with PAGE_WISE_CHUNKING=True
    - Call embed_chunks() to create embeddings
    - Store in isolated test ChromaDB instance
    - Query ChromaDB to verify chunks are retrievable
    - Clean up test data after completion
    - _Requirements: 8.4, 8.9_

  - [ ]* 8.2 Write integration test for force_reindex functionality
    - Index sample PDF with text-based chunking
    - Re-index same PDF with PAGE_WISE_CHUNKING=True and force_reindex=True
    - Verify old chunks are deleted
    - Verify new page-wise chunks are created
    - Verify chunk count reduction (75-80%)
    - _Requirements: 4.1, 4.2, 8.5_

  - [ ]* 8.3 Write integration test for retrieval accuracy
    - Index sample PDFs with page-wise chunking
    - Run test queries against ChromaDB
    - Verify retrieved chunks contain complete page content
    - Compare with text-based chunking baseline
    - _Requirements: 8.4_

- [x] 9. Test with real data and validate results
  - [x] 9.1 Run page-wise chunking on existing 6 company PDFs
    - Set PAGE_WISE_CHUNKING=True in .env
    - Run ingest_directory with force_reindex=True
    - Monitor processing logs for errors
    - Verify chunk count reduction (target: 300-400 chunks)
    - Check for any rejected pages due to unsplittable content
    - _Requirements: 7.3, 7.4_

  - [x] 9.2 Validate metadata completeness and correctness
    - Query ChromaDB for all page-wise chunks
    - Verify all required metadata fields are present
    - Check chunk_id format matches specification
    - Verify page_label (L-page) alignment
    - Validate table_count and text_block_count accuracy
    - _Requirements: 1.4, 6.1, 6.2, 8.8_

  - [x] 9.3 Test retrieval quality with page-wise chunks
    - Run sample queries from scripts/test_query.py
    - Compare retrieval results with text-based chunking baseline
    - Verify complete tables and context are retrieved together
    - Document any quality improvements or regressions
    - _Requirements: 7.3_

- [x] 10. Checkpoint - Ensure all integration tests pass
  - Run full test suite (unit + integration)
  - Verify no regressions in existing functionality
  - Validate performance metrics (processing time < 5s per 50-page PDF)
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Update documentation
  - [x] 11.1 Update README.md with page-wise chunking configuration
    - Document PAGE_WISE_CHUNKING and MAX_PAGE_TOKENS settings
    - Add migration instructions for existing installations
    - Document expected chunk count reduction
    - Add troubleshooting section for common issues
    - _Requirements: 3.1, 3.2_

  - [x] 11.2 Update inline code documentation
    - Add docstrings to all new functions
    - Document function parameters and return types
    - Add usage examples in docstrings
    - Document error conditions and exceptions
    - _Requirements: 7.1_

  - [x] 11.3 Create migration guide for existing users
    - Document backup procedure for existing ChromaDB
    - Provide step-by-step migration instructions
    - Document rollback procedure if issues occur
    - Add performance comparison metrics
    - _Requirements: 4.1, 4.2_

- [x] 12. Final validation and deployment preparation
  - [x] 12.1 Run performance benchmarks
    - Measure processing time for 50-page PDF
    - Compare with text-based chunking performance
    - Verify chunk count reduction ≥ 75%
    - Document memory and CPU usage
    - _Requirements: 7.3, 7.4_

  - [x] 12.2 Verify backward compatibility
    - Test PAGE_WISE_CHUNKING=False produces identical results to legacy
    - Verify existing metadata fields are preserved
    - Test RAG pipeline filtering with page-wise chunks
    - Ensure no breaking changes to embedder or ingestor interfaces
    - _Requirements: 4.3, 4.4, 4.5_

  - [x] 12.3 Prepare deployment checklist
    - Document pre-deployment backup steps
    - Create deployment script for .env updates
    - Document post-deployment validation steps
    - Create rollback procedure documentation
    - _Requirements: 4.1, 4.2_

- [x] 13. Final checkpoint - Production readiness
  - All tests passing (unit + integration)
  - Documentation complete and reviewed
  - Performance benchmarks meet requirements
  - Backward compatibility verified
  - Deployment checklist ready
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional testing tasks and can be skipped for faster MVP delivery
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at key milestones
- The implementation preserves backward compatibility by maintaining the existing chunk structure and metadata schema
- Configuration flag (PAGE_WISE_CHUNKING) allows switching between strategies without code changes
- Token limit handling ensures all pages can be processed, even those exceeding embedding model limits
- Metadata enrichment provides page-level statistics for analysis and debugging
- Integration tests validate the complete pipeline from PDF to ChromaDB retrieval
- Real data testing with 6 company PDFs validates production readiness
- Documentation updates ensure users can migrate smoothly from text-based to page-wise chunking

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1"] },
    { "id": 1, "tasks": ["2.2", "2.3"] },
    { "id": 2, "tasks": ["2.4", "2.5"] },
    { "id": 3, "tasks": ["3.1", "3.2", "4.1"] },
    { "id": 4, "tasks": ["3.3", "4.2", "4.3"] },
    { "id": 5, "tasks": ["5.1", "5.2", "6.1"] },
    { "id": 6, "tasks": ["6.2", "6.3"] },
    { "id": 7, "tasks": ["8.1", "8.2", "8.3"] },
    { "id": 8, "tasks": ["9.1"] },
    { "id": 9, "tasks": ["9.2", "9.3"] },
    { "id": 10, "tasks": ["11.1", "11.2", "11.3"] },
    { "id": 11, "tasks": ["12.1", "12.2", "12.3"] }
  ]
}
```
