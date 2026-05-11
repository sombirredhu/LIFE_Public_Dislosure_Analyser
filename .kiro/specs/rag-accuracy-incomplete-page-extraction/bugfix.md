# Bugfix Requirements Document

## Introduction

The RAG system is failing to return results from all 6 uploaded company PDFs when users query for financial data like "premium for all companies". Currently, only 3-4 companies are returned instead of all 6. This severely impacts the accuracy and completeness of financial analysis queries.

The root cause is that the `extract_index_page()` function in `src/pdf_parser.py` is only extracting L-14 from the IRDAI index table, missing critical pages like L-4 (Premium), L-1 through L-13, and L-15 through L-30+. This incomplete extraction means:
- Master definitions only contain L-14
- Company-specific page definition files are incomplete
- Queries for financial terms fail to retrieve relevant chunks from most companies
- The system cannot map user queries to the correct L-pages for retrieval

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN the `extract_index_page()` function scans the first 5 pages of a PDF for the IRDAI L-page index table THEN the system only extracts L-14 and misses L-1 through L-13 and L-15 through L-30+

1.2 WHEN the `parse_pdf()` function processes a PDF and extracts the index from the first 2 pages THEN the system only captures L-14 in the index_map and fails to extract other L-page mappings

1.3 WHEN a user queries for "premium for all companies" THEN the system only returns results from 3-4 companies instead of all 6 uploaded PDFs

1.4 WHEN the master_page_definitions.json is generated THEN it only contains `{"L-14": ["Investments - Assets Held to Cover Linked Liabilities Schedule"]}` instead of all L-pages (L-1 through L-30+)

1.5 WHEN company-specific page definition files are created THEN they only contain L-14 instead of the complete set of L-pages from that company's index

### Expected Behavior (Correct)

2.1 WHEN the `extract_index_page()` function scans the first 5 pages of a PDF for the IRDAI L-page index table THEN the system SHALL extract all L-page mappings present in the index (L-1 through L-30+ with their corresponding section names)

2.2 WHEN the `parse_pdf()` function processes a PDF and extracts the index from the first 2 pages THEN the system SHALL capture all L-page mappings in the index_map including L-4 (Premium), L-1 (Revenue Account), L-2 (Balance Sheet), and all other L-pages

2.3 WHEN a user queries for "premium for all companies" THEN the system SHALL return results from all 6 uploaded PDFs by correctly mapping "premium" to L-4 and retrieving chunks from all companies

2.4 WHEN the master_page_definitions.json is generated THEN it SHALL contain all unique L-page mappings from all companies (e.g., L-1 through L-30+ with their section names)

2.5 WHEN company-specific page definition files are created THEN they SHALL contain all L-pages extracted from that company's index table

2.6 WHEN the regex pattern `_LPAGE_LABEL_RE` or table parsing logic processes index rows THEN it SHALL correctly match and extract all L-page entries regardless of formatting variations (with/without colons, with/without descriptions)

### Unchanged Behavior (Regression Prevention)

3.1 WHEN the system processes PDFs that have already been parsed THEN it SHALL CONTINUE TO correctly extract L-14 mappings as it does currently

3.2 WHEN the `_update_master_page_definitions()` function merges company-specific files THEN it SHALL CONTINUE TO create both master_page_definitions.json and master_term_to_page.json files

3.3 WHEN the system extracts metadata from filenames THEN it SHALL CONTINUE TO correctly parse company_code, quarter, and FY information

3.4 WHEN the system processes table data from PDFs THEN it SHALL CONTINUE TO extract tables using pdfplumber and convert them to structured format

3.5 WHEN the system detects page labels from page content THEN it SHALL CONTINUE TO use the `_extract_lpage_from_text()` function to identify L-pages in page headers
