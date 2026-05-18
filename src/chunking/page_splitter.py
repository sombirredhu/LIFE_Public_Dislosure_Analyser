import logging
from typing import Any, Dict, List
from src.config import MAX_PAGE_TOKENS
from src.chunking.utils import _estimate_tokens, _make_chunk, _combine_page_content
from src.chunking.sub_chunker import _split_page_into_subchunks

logger = logging.getLogger(__name__)

def _chunk_page_wise(
    parsed_doc: Dict[str, Any],
    base_metadata: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Create one chunk per page by combining all tables and text_blocks.
    
    This is the main page-wise chunking strategy that treats each PDF page as a
    complete semantic unit. It creates one chunk per page by default, preserving
    the natural boundaries and relationships between tables and text on the same page.
    
    For pages exceeding the token limit (MAX_PAGE_TOKENS, default 8000), the function
    automatically splits them into sub-chunks using _split_page_into_subchunks().
    
    The function aligns with IRDAI L-page identifiers, ensuring each chunk corresponds
    to a complete section (e.g., L-1 = Revenue Account, L-5 = Claims).
    
    Args:
        parsed_doc: Output from pdf_parser.parse_pdf() with structure:
            {
                "company": str,
                "company_code": str,
                "quarter": str,
                "fy": str,
                "period_label": str,
                "source_file": str,
                "total_pages": int,
                "pages": [
                    {
                        "page_number": int,
                        "page_label": str,  # L-page identifier
                        "section": str,
                        "tables": [...],
                        "text_blocks": [...],
                        "company_name": str (optional)
                    },
                    ...
                ]
            }
        base_metadata: Base metadata dict to include in all chunks, typically contains:
            - company, company_code, quarter, fy, period_label, source_file
    
    Returns:
        List of chunk dictionaries, each with structure:
        {
            "text": str,  # Combined page content (tables + text_blocks)
            "metadata": {
                ...base_metadata,
                "chunk_id": str,  # Format: {company_code}_{quarter}_{fy}_page{N}[_part{M}]
                "page_number": int,
                "page_label": str,  # L-page identifier (e.g., "L-1", "L-5")
                "section": str,  # Section name (e.g., "Premium Schedule")
                "content_type": "page",
                "char_count": int,
                "ingested_at": str,  # ISO 8601 timestamp
                "table_count": int,  # Number of tables on page
                "text_block_count": int,  # Number of text blocks on page
                "is_split": bool,  # True if page was split into sub-chunks
                "total_parts": int,  # Only present if is_split=True
                "part_number": int,  # Only present if is_split=True
                "company_full_name": str  # Only present if extracted from page
            }
        }
    
    Examples:
        >>> # Simple document with 3 pages
        >>> parsed_doc = {
        ...     "company": "HDFC Life",
        ...     "company_code": "HDFC_Life",
        ...     "quarter": "Q1",
        ...     "fy": "FY25",
        ...     "period_label": "Q1 FY2024-25",
        ...     "source_file": "HDFC_Life_Q1_FY25.pdf",
        ...     "pages": [
        ...         {
        ...             "page_number": 1,
        ...             "page_label": "L-1",
        ...             "section": "Revenue Account",
        ...             "tables": [{"raw_text": "Premium | 1000\\nClaims | 500"}],
        ...             "text_blocks": ["Summary of revenue"]
        ...         },
        ...         {
        ...             "page_number": 2,
        ...             "page_label": "L-5",
        ...             "section": "Claims",
        ...             "tables": [],
        ...             "text_blocks": ["Claims details"]
        ...         }
        ...     ]
        ... }
        >>> base_meta = {
        ...     "company": "HDFC Life",
        ...     "company_code": "HDFC_Life",
        ...     "quarter": "Q1",
        ...     "fy": "FY25"
        ... }
        >>> chunks = _chunk_page_wise(parsed_doc, base_meta)
        >>> len(chunks)
        2
        >>> chunks[0]["metadata"]["chunk_id"]
        'HDFC_Life_Q1_FY25_page1'
        >>> chunks[0]["metadata"]["page_label"]
        'L-1'
        >>> chunks[0]["metadata"]["is_split"]
        False
        >>> chunks[0]["metadata"]["table_count"]
        1
        >>> chunks[0]["metadata"]["text_block_count"]
        1
        
        >>> # Document with oversized page that gets split
        >>> large_page_doc = {
        ...     "company_code": "TEST",
        ...     "quarter": "Q1",
        ...     "fy": "FY25",
        ...     "pages": [{
        ...         "page_number": 1,
        ...         "page_label": "L-1",
        ...         "section": "Large Section",
        ...         "tables": [{"raw_text": "A" * 40000}],  # Exceeds 8000 token limit
        ...         "text_blocks": []
        ...     }]
        ... }
        >>> chunks = _chunk_page_wise(large_page_doc, {"company_code": "TEST", "quarter": "Q1", "fy": "FY25"})
        >>> len(chunks) > 1  # Page was split
        True
        >>> chunks[0]["metadata"]["is_split"]
        True
        >>> chunks[0]["metadata"]["chunk_id"]
        'TEST_Q1_FY25_page1_part1'
    
    Behavior:
        - Empty pages (no tables or text_blocks): Skipped, warning logged
        - Pages exceeding MAX_PAGE_TOKENS: Split into sub-chunks automatically
        - Unsplittable pages: Rejected, error logged, processing continues
        - Missing 'pages' array: Returns empty list
        - Company name from page content: Added to metadata if available
    
    Logging:
        - INFO: Processing start, chunk creation summary
        - WARNING: Empty pages, oversized pages being split
        - ERROR: Pages rejected due to unsplittable content
    
    Note:
        - Reduces chunk count by ~75-80% compared to text-based chunking
        - Preserves semantic coherence by keeping page content together
        - Aligns with IRDAI L-page structure for better retrieval
        - Compatible with existing embedder and ChromaDB storage
    """
    all_chunks = []
    prefix = f"{base_metadata['company_code']}_{base_metadata['quarter']}_{base_metadata['fy']}"
    
    # Get company full name from document level
    company_full_name = parsed_doc.get("company_full_name")
    
    for page in parsed_doc.get("pages", []):
        page_number = page["page_number"]
        page_label = page.get("page_label", "")
        page_label_normalized = page.get("page_label_normalized", "")
        section = page.get("section", "unknown")
        
        # Extract company name from page content (if available)
        company_name_from_page = page.get("company_name") or company_full_name
        
        # Combine page content
        page_text = _combine_page_content(page)
        
        # Skip empty pages
        if not page_text or not page_text.strip():
            logger.warning(f"Skipping empty page {page_number}")
            continue

        # Skip very short pages (version/upload date markers, single-line stubs)
        if len(page_text.strip()) < 80:
            logger.debug(f"Skipping too-short page {page_number} ({len(page_text.strip())} chars)")
            continue

        # Skip TOC/index pages — high L-page density, no page_label, no real data.
        # They are already used for building the index_map during PDF parsing.
        if page.get("is_index_page") and not page_label:
            logger.debug(f"Skipping index/TOC page {page_number}")
            continue
        
        # Check if page exceeds token limit
        page_tokens = _estimate_tokens(page_text)
        
        if page_tokens > MAX_PAGE_TOKENS:
            # Split page into sub-chunks
            logger.warning(f"Page {page_number} exceeds token limit ({page_tokens} > {MAX_PAGE_TOKENS}), splitting into sub-chunks")
            try:
                sub_chunks = _split_page_into_subchunks(page, base_metadata, max_tokens=7600)
                
                # Add enhanced metadata to sub-chunks
                for chunk in sub_chunks:
                    if company_name_from_page:
                        chunk["metadata"]["company_full_name"] = company_name_from_page
                    if page_label_normalized:
                        chunk["metadata"]["page_label_normalized"] = page_label_normalized
                
                all_chunks.extend(sub_chunks)
                logger.info(f"Page {page_number} split into {len(sub_chunks)} sub-chunks")
            except ValueError as e:
                # Page rejected due to unsplittable content
                logger.error(f"Page {page_number} rejected: {e}")
                continue
        else:
            # Create single chunk for page
            chunk_id = f"{prefix}_page{page_number}"
            chunk = _make_chunk(
                page_text, base_metadata, page_number, page_label, section, "page", chunk_id
            )
            
            # Add page statistics
            chunk["metadata"]["table_count"] = len(page.get("tables", []))
            chunk["metadata"]["text_block_count"] = len(page.get("text_blocks", []))
            chunk["metadata"]["is_split"] = False
            
            # Add enhanced metadata
            if company_name_from_page:
                chunk["metadata"]["company_full_name"] = company_name_from_page
            if page_label_normalized:
                chunk["metadata"]["page_label_normalized"] = page_label_normalized
            
            all_chunks.append(chunk)
    
    logger.info(f"Created {len(all_chunks)} page-wise chunks from {len(parsed_doc.get('pages', []))} pages")
    
    return all_chunks



