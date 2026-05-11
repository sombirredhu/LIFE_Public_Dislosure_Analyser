# Requirements Document

## Introduction

This document specifies requirements for implementing a page-wise chunking strategy for the IRDAI Public Disclosure PDF analyzer. The current system uses text-based chunking that splits documents into overlapping chunks of ~1000 characters, which breaks semantic coherence by fragmenting complete tables and related text that naturally belong together on a single page. Each PDF page represents a complete semantic unit with a unique L-page identifier (L-1, L-2, etc.) that maps to specific sections like Premium Schedule, Claims, or Balance Sheet. The proposed page-wise chunking strategy will treat each page as a single chunk, preserving semantic coherence and reducing the total chunk count from ~1,820 to ~300-400 chunks across 6 companies.

## Glossary

- **Chunker**: The module (`src/chunker.py`) responsible for splitting parsed PDF content into chunks with metadata
- **PDF_Parser**: The module (`src/pdf_parser.py`) that extracts pages with page_number, page_label (L-page), section, tables, and text_blocks from PDF files
- **Ingestor**: The module (`src/ingestor.py`) that orchestrates the PDF → chunks → embeddings → ChromaDB pipeline
- **L-page**: IRDAI-defined page label (e.g., "L-1", "L-5", "L-12") that uniquely identifies a section type across all insurance company PDFs
- **Page**: A single page from a PDF document containing tables and text blocks that form a complete semantic unit
- **Chunk**: A unit of text with associated metadata that is embedded and stored in ChromaDB for retrieval
- **Embedding_Model**: The sentence-transformers/all-MiniLM-L6-v2 model with 384 dimensions and ~512 token limit per chunk
- **Token_Limit**: The maximum number of tokens (~8000) that the embedding model can process in a single chunk
- **Semantic_Coherence**: The property where related information (tables, text, context) stays together in a single retrievable unit
- **Metadata_Schema**: The structure of metadata attached to each chunk (company, quarter, FY, page_number, page_label, section, content_type)
- **ChromaDB**: The vector database that stores embedded chunks for semantic search and retrieval
- **RAG_Pipeline**: The Retrieval-Augmented Generation pipeline that retrieves relevant chunks and generates answers

## Requirements

### Requirement 1: Page-Wise Chunking Strategy

**User Story:** As a system developer, I want the Chunker to create one chunk per page by default, so that complete semantic units (tables + text from a single page) stay together for better retrieval accuracy.

#### Acceptance Criteria

1. WHEN the Chunker processes a parsed PDF document, THE Chunker SHALL create one chunk per page by combining all tables from the page followed by all text_blocks from the page, separated by double newline characters ("\n\n")

2. IF a page contains neither tables nor text_blocks, THEN THE Chunker SHALL skip that page and create no chunk for it

3. IF the parsed PDF document is missing the "pages" array or any page is missing the "tables" or "text_blocks" arrays, THEN THE Chunker SHALL treat missing arrays as empty arrays and continue processing

4. THE Chunker SHALL populate chunk metadata with the following fields from the parsed document: company, company_code, quarter, fy, period_label, source_file, page_number, page_label, section, and content_type

5. THE Chunker SHALL set chunk_id to the format `{company_code}_{quarter}_{fy}_page{page_number}` without any chunk number suffix

6. THE Chunker SHALL set content_type to "page" for all page-wise chunks

7. THE Chunker SHALL set char_count in metadata to the total character length of the combined chunk text

8. THE Chunker SHALL set ingested_at in metadata to the ISO 8601 timestamp at the time of chunk creation

### Requirement 2: Token Limit Handling

**User Story:** As a system developer, I want the Chunker to handle pages that exceed the embedding model token limit, so that all pages can be processed without errors.

#### Acceptance Criteria

1. WHEN a page's combined content exceeds 8000 tokens (estimated as char_count / 4), THE Chunker SHALL split the page into sub-chunks where each sub-chunk contains ≤ 7600 tokens
2. WHEN splitting a page, THE Chunker SHALL keep complete tables intact within a single sub-chunk IF the table's estimated token count ≤ 7600 tokens
3. WHEN a single table exceeds 7600 tokens, THE Chunker SHALL split the table by rows while repeating the table headers in each sub-chunk
4. WHEN splitting a table by rows, THE Chunker SHALL include at least 2 data rows per sub-chunk (in addition to headers), OR include all remaining rows if fewer than 2 rows remain
5. WHEN splitting a page into sub-chunks, THE Chunker SHALL set chunk_id to `{company_code}_{quarter}_{fy}_page{page_number}_part{n}` format where n starts at 1
6. WHEN splitting a page, THE Chunker SHALL include page_number, page_label, and section metadata in all sub-chunks
7. THE Chunker SHALL use a token estimation function that approximates token count as `char_count / 4` for the Embedding_Model
8. WHEN creating sub-chunks from a page, THE Chunker SHALL preserve the original document order by processing tables and text_blocks in the sequence they appear in the PDF_Parser output
9. WHEN adding content to a sub-chunk, IF adding the next complete table or text_block would exceed 7600 tokens, THEN THE Chunker SHALL start a new sub-chunk with that content
10. IF a single text_block exceeds 7600 tokens, THEN THE Chunker SHALL split the text_block at sentence boundaries (. ! ?) while keeping each fragment ≥ 100 characters
11. IF a single table row (including headers) exceeds 7600 tokens, THEN THE Chunker SHALL reject that page and log an error message indicating the page_number and reason "unsplittable table row exceeds token limit"
12. WHEN splitting a page, THE Chunker SHALL create no more than 20 sub-chunks per page

### Requirement 3: Configuration Management

**User Story:** As a system administrator, I want to configure the chunking strategy via configuration settings, so that I can switch between page-wise and text-based chunking without code changes.

#### Acceptance Criteria

1. THE Config SHALL define a PAGE_WISE_CHUNKING boolean flag with default value True
2. THE Config SHALL define a MAX_PAGE_TOKENS integer setting with default value 8000
3. WHEN PAGE_WISE_CHUNKING is True, THE Chunker SHALL use page-wise chunking strategy
4. WHEN PAGE_WISE_CHUNKING is False, THE Chunker SHALL use the legacy text-based chunking strategy (CHUNK_SIZE=1000, CHUNK_OVERLAP=200)
5. THE Config SHALL preserve existing CHUNK_SIZE, CHUNK_OVERLAP, and MIN_CHUNK_SIZE settings for backward compatibility with text-based chunking

### Requirement 4: Backward Compatibility

**User Story:** As a system administrator, I want to re-index existing PDFs with the new chunking strategy, so that I can migrate from text-based to page-wise chunks without data loss.

#### Acceptance Criteria

1. THE Ingestor SHALL support a force_reindex parameter that allows re-processing of already-indexed PDFs
2. WHEN force_reindex is True, THE Ingestor SHALL delete existing chunks for a PDF before creating new chunks
3. THE Chunker SHALL maintain the existing two-key chunk structure (text and metadata) for compatibility with the Embedder
4. THE Chunker SHALL preserve all existing metadata fields to ensure compatibility with the RAG_Pipeline filtering logic
5. WHEN PAGE_WISE_CHUNKING is False, THE Chunker SHALL produce chunks identical to the legacy implementation

### Requirement 5: Chunk Quality Validation

**User Story:** As a system developer, I want the Chunker to validate chunk quality, so that malformed or empty chunks are not stored in ChromaDB.

#### Acceptance Criteria

1. WHEN the Chunker processes a chunk where the text field is empty or contains only whitespace characters, THE Chunker SHALL exclude that chunk from the output list
2. WHEN the Chunker processes a chunk where char_count is less than MIN_CHUNK_SIZE, THE Chunker SHALL exclude that chunk from the output list
3. WHEN a page contains no tables and no text_blocks, THE Chunker SHALL skip that page and log a warning message indicating the page_number
4. THE Chunker SHALL log the total number of chunks created and the average chunk size in characters after processing each document
5. WHEN a page text_block is split into multiple sub-chunks due to exceeding CHUNK_SIZE, THE Chunker SHALL log the page_number and the number of sub-chunks created

### Requirement 6: Metadata Enrichment

**User Story:** As a data analyst, I want chunks to include page-level statistics in metadata, so that I can analyze chunk distribution and quality.

#### Acceptance Criteria

1. WHEN the Chunker creates a chunk from a table, THE Chunker SHALL add a table_count field to metadata with value 1
2. WHEN the Chunker creates a chunk from a text block, THE Chunker SHALL add a table_count field to metadata with value 0
3. WHEN the Chunker creates a chunk from a table, THE Chunker SHALL add a text_block_count field to metadata with value 0
4. WHEN the Chunker creates a chunk from a text block, THE Chunker SHALL add a text_block_count field to metadata with value 1
5. IF a page generates exactly one chunk, THEN THE Chunker SHALL add an is_split field to metadata with value False
6. IF a page generates two or more chunks, THEN THE Chunker SHALL add an is_split field to metadata with value True
7. IF is_split is False, THEN THE Chunker SHALL NOT add total_parts or part_number fields to metadata
8. IF is_split is True, THEN THE Chunker SHALL add a total_parts field to metadata indicating the total number of chunks generated from that page, with value between 2 and 999
9. IF is_split is True, THEN THE Chunker SHALL add a part_number field to metadata indicating the current chunk's sequential position among all chunks from that page, with value between 1 and total_parts

### Requirement 7: Performance Optimization

**User Story:** As a system administrator, I want the page-wise chunking to process documents faster than text-based chunking, so that ingestion time is reduced.

#### Acceptance Criteria

1. THE Chunker SHALL process pages in a single pass without requiring multiple iterations over the same content
2. THE Chunker SHALL avoid redundant text splitting operations when PAGE_WISE_CHUNKING is True
3. THE Chunker SHALL reduce total chunk count by at least 75% compared to text-based chunking (from ~1820 to ~400 chunks for 6 companies)
4. THE Chunker SHALL complete processing of a 50-page PDF in less than 5 seconds on standard hardware
5. THE Chunker SHALL log processing time for each document to enable performance monitoring

### Requirement 8: Testing and Validation

**User Story:** As a quality assurance engineer, I want comprehensive tests for the page-wise chunking implementation, so that I can verify correctness and prevent regressions.

#### Acceptance Criteria

1. THE Test_Suite SHALL include at least 5 unit tests for page-wise chunking logic using pytest framework with test documents containing 1-50 pages and varying content types (tables-only, text-only, mixed, empty)
2. THE Test_Suite SHALL include at least 3 tests for token limit handling with pages exceeding MAX_PAGE_TOKENS (8000 tokens or approximately 32000 characters)
3. THE Test_Suite SHALL include at least 2 tests for configuration switching between PAGE_WISE_CHUNKING True and False that verify chunk_id format and chunk count differences
4. THE Test_Suite SHALL include at least 2 integration tests that verify chunks are created, embedded, stored in ChromaDB, and retrievable via semantic search
5. THE Test_Suite SHALL include at least 1 test that verifies page-wise chunking produces 70-80% fewer chunks than text-based chunking for the same document and that both strategies preserve the Metadata_Schema structure
6. THE Test_Suite SHALL include at least 4 tests for edge cases: empty pages (no tables or text_blocks), pages with only tables, pages with only text, and pages with mixed content
7. THE Test_Suite SHALL verify that chunk_id matches format `{company_code}_{quarter}_{fy}_page{page_number}` for single-page chunks and `{company_code}_{quarter}_{fy}_page{page_number}_part{n}` for split-page sub-chunks
8. THE Test_Suite SHALL verify that all metadata fields (company, company_code, quarter, fy, period_label, source_file, chunk_id, page_number, page_label, section, content_type, char_count, ingested_at, table_count, text_block_count, is_split, total_parts, part_number) are present with non-null values and correct data types in page-wise chunks
9. WHEN running integration tests, THE Test_Suite SHALL create an isolated test ChromaDB instance separate from production data and clean up test data after test completion
