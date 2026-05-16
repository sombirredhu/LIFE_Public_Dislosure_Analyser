import logging
from typing import Any, Dict, List
from src.chunking.utils import _estimate_tokens, _make_chunk

logger = logging.getLogger(__name__)

def _split_page_into_subchunks(
    page: Dict[str, Any],
    base_metadata: Dict[str, Any],
    max_tokens: int = 7600
) -> List[Dict[str, Any]]:
    """
    Split oversized page into sub-chunks while preserving table and text integrity.
    
    This function handles pages that exceed the embedding model's token limit by
    intelligently splitting them into smaller sub-chunks. It prioritizes keeping
    complete tables intact and splits at natural boundaries (table rows, sentences)
    when necessary.
    
    Algorithm:
    1. Process tables first (keep intact if possible)
    2. If table exceeds max_tokens, split by rows with repeated headers
    3. Process text_blocks after tables
    4. If text_block exceeds max_tokens, split at sentence boundaries
    5. Accumulate content until max_tokens reached
    6. Create new sub-chunk when threshold exceeded
    
    Constraints:
    - Minimum 2 data rows per table sub-chunk (plus headers)
    - Minimum 100 characters per text fragment
    - Maximum 20 sub-chunks per page (excess content truncated)
    - Single table row exceeding max_tokens causes page rejection
    
    Args:
        page: Page dictionary with the following structure:
            - 'page_number': Integer page number (1-based)
            - 'page_label': L-page identifier (e.g., "L-1", "L-5")
            - 'section': Section name (e.g., "Premium Schedule")
            - 'tables': List of table dicts with 'raw_text', 'headers', 'rows'
            - 'text_blocks': List of text strings
        base_metadata: Base metadata dict to include in all sub-chunks, must contain:
            - 'company_code': Company identifier (e.g., "HDFC_Life")
            - 'quarter': Quarter identifier (e.g., "Q1", "Q2")
            - 'fy': Fiscal year (e.g., "FY25", "FY26")
        max_tokens: Maximum tokens per sub-chunk (default 7600, leaves buffer below 8000 limit)
    
    Returns:
        List of sub-chunk dictionaries, each with structure:
        {
            "text": str,  # Combined content for this sub-chunk
            "metadata": {
                ...base_metadata,
                "chunk_id": str,  # Format: {company_code}_{quarter}_{fy}_page{N}_part{M}
                "page_number": int,
                "page_label": str,
                "section": str,
                "content_type": "page",
                "char_count": int,
                "ingested_at": str,  # ISO 8601 timestamp
                "is_split": True,
                "total_parts": int,  # Total number of sub-chunks for this page
                "part_number": int,  # Sequential position (1-based)
                "table_count": int,  # Original table count from page
                "text_block_count": int  # Original text block count from page
            }
        }
    
    Raises:
        ValueError: If single table row (with headers) exceeds max_tokens, making
                   the page unsplittable. Error message format:
                   "Page {page_number}: unsplittable table row exceeds token limit"
    
    Examples:
        >>> # Page with large table that needs splitting
        >>> page = {
        ...     "page_number": 5,
        ...     "page_label": "L-5",
        ...     "section": "Claims",
        ...     "tables": [{
        ...         "raw_text": "...",  # Very long table
        ...         "headers": ["Claim Type", "Amount"],
        ...         "rows": [["Type1", "1000"], ["Type2", "2000"], ...]  # 100 rows
        ...     }],
        ...     "text_blocks": ["Summary text"]
        ... }
        >>> base_meta = {"company_code": "HDFC", "quarter": "Q1", "fy": "FY25"}
        >>> chunks = _split_page_into_subchunks(page, base_meta)
        >>> len(chunks)
        3
        >>> chunks[0]["metadata"]["chunk_id"]
        'HDFC_Q1_FY25_page5_part1'
        >>> chunks[0]["metadata"]["total_parts"]
        3
        >>> chunks[0]["metadata"]["is_split"]
        True
        
        >>> # Page with unsplittable table row (raises error)
        >>> bad_page = {
        ...     "page_number": 10,
        ...     "tables": [{
        ...         "headers": ["Col1", "Col2"],
        ...         "rows": [["A" * 50000, "B" * 50000]]  # Single row exceeds limit
        ...     }],
        ...     "text_blocks": []
        ... }
        >>> _split_page_into_subchunks(bad_page, base_meta)
        Traceback (most recent call last):
        ...
        ValueError: Page 10: unsplittable table row exceeds token limit
    
    Error Conditions:
        - Single table row > max_tokens: Raises ValueError, page rejected
        - Page would create > 20 sub-chunks: Truncates to 20, logs warning
        - Table without headers/rows: Logs error, raises ValueError
        - Empty page: Returns empty list (handled by caller)
    
    Note:
        - Table headers are repeated in each sub-chunk when splitting tables
        - Text blocks are split at sentence boundaries (. ! ?) when too large
        - Fragments < 100 characters are discarded to maintain quality
        - Token estimation uses char_count / 4 approximation
    """
    page_number = page["page_number"]
    page_label = page.get("page_label", "")
    section = page.get("section", "unknown")
    prefix = f"{base_metadata['company_code']}_{base_metadata['quarter']}_{base_metadata['fy']}"
    
    sub_chunks = []
    current_content = []
    current_tokens = 0
    
    # Process tables first
    tables = page.get("tables", [])
    for table in tables:
        if not table or "raw_text" not in table:
            continue
        
        table_text = table["raw_text"]
        table_tokens = _estimate_tokens(table_text)
        
        # If table fits within limit, try to add to current chunk
        if table_tokens <= max_tokens:
            # Check if adding this table would exceed limit
            if current_tokens + table_tokens > max_tokens and current_content:
                # Finalize current sub-chunk
                sub_chunks.append("\n\n".join(current_content))
                current_content = []
                current_tokens = 0
            
            # Add table to current chunk
            current_content.append(table_text)
            current_tokens += table_tokens
        else:
            # Table exceeds max_tokens, need to split by rows
            # First, finalize any current content
            if current_content:
                sub_chunks.append("\n\n".join(current_content))
                current_content = []
                current_tokens = 0
            
            # Split table by rows with repeated headers
            headers = table.get("headers", [])
            rows = table.get("rows", [])
            
            if not headers or not rows:
                # No structure to split, log error and skip
                logger.error(f"Page {page_number} rejected: table without headers/rows exceeds token limit")
                raise ValueError(f"Page {page_number}: unsplittable table exceeds token limit")
            
            # Build header text
            header_text = " | ".join(headers)
            header_tokens = _estimate_tokens(header_text)
            
            # Check if single row with headers exceeds limit
            if rows:
                first_row_text = " | ".join(rows[0])
                single_row_tokens = header_tokens + _estimate_tokens(first_row_text) + _estimate_tokens("\n")
                
                if single_row_tokens > max_tokens:
                    logger.error(f"Page {page_number} rejected: single table row exceeds token limit")
                    raise ValueError(f"Page {page_number}: unsplittable table row exceeds token limit")
            
            # Split table into sub-chunks with at least 2 rows each
            table_sub_content = []
            table_sub_tokens = header_tokens
            
            for i, row in enumerate(rows):
                row_text = " | ".join(row)
                row_tokens = _estimate_tokens(row_text) + _estimate_tokens("\n")
                
                # Check if adding this row would exceed limit
                if table_sub_tokens + row_tokens > max_tokens and len(table_sub_content) >= 2:
                    # Finalize this table sub-chunk (minimum 2 rows met)
                    table_chunk_text = header_text + "\n" + "\n".join(table_sub_content)
                    sub_chunks.append(table_chunk_text)
                    table_sub_content = []
                    table_sub_tokens = header_tokens
                
                # Add row to current table sub-chunk
                table_sub_content.append(row_text)
                table_sub_tokens += row_tokens
            
            # Finalize remaining table rows (even if < 2 rows remain)
            if table_sub_content:
                table_chunk_text = header_text + "\n" + "\n".join(table_sub_content)
                sub_chunks.append(table_chunk_text)
    
    # Process text_blocks after tables
    text_blocks = page.get("text_blocks", [])
    for text_block in text_blocks:
        if not text_block or not text_block.strip():
            continue
        
        text_block = text_block.strip()
        block_tokens = _estimate_tokens(text_block)
        
        # If text block fits within limit, try to add to current chunk
        if block_tokens <= max_tokens:
            # Check if adding this block would exceed limit
            if current_tokens + block_tokens > max_tokens and current_content:
                # Finalize current sub-chunk
                sub_chunks.append("\n\n".join(current_content))
                current_content = []
                current_tokens = 0
            
            # Add text block to current chunk
            current_content.append(text_block)
            current_tokens += block_tokens
        else:
            # Text block exceeds max_tokens, need to split at sentence boundaries
            # First, finalize any current content
            if current_content:
                sub_chunks.append("\n\n".join(current_content))
                current_content = []
                current_tokens = 0
            
            # Split at sentence boundaries (. ! ?)
            sentences = []
            current_pos = 0
            
            # Find sentence boundaries
            for i, char in enumerate(text_block):
                if char in '.!?' and i + 1 < len(text_block):
                    # Check if followed by space or end of string
                    if text_block[i + 1] in ' \n' or i + 1 == len(text_block) - 1:
                        sentence = text_block[current_pos:i + 1].strip()
                        if sentence:
                            sentences.append(sentence)
                        current_pos = i + 1
            
            # Add remaining text as last sentence
            if current_pos < len(text_block):
                remaining = text_block[current_pos:].strip()
                if remaining:
                    sentences.append(remaining)
            
            # If no sentence boundaries found, treat as single fragment
            if not sentences:
                sentences = [text_block]
            
            # Accumulate sentences into fragments of at least 100 characters
            fragment = []
            fragment_tokens = 0
            
            for sentence in sentences:
                sentence_tokens = _estimate_tokens(sentence)
                
                # Check if adding this sentence would exceed limit
                if fragment_tokens + sentence_tokens > max_tokens and fragment:
                    # Finalize current fragment (if >= 100 chars)
                    fragment_text = " ".join(fragment)
                    if len(fragment_text) >= 100:
                        sub_chunks.append(fragment_text)
                    fragment = []
                    fragment_tokens = 0
                
                # Add sentence to current fragment
                fragment.append(sentence)
                fragment_tokens += sentence_tokens
            
            # Finalize remaining fragment (even if < 100 chars)
            if fragment:
                fragment_text = " ".join(fragment)
                if len(fragment_text) >= 100:
                    sub_chunks.append(fragment_text)
    
    # Finalize any remaining content
    if current_content:
        sub_chunks.append("\n\n".join(current_content))
    
    # Check sub-chunk limit
    if len(sub_chunks) > 20:
        logger.warning(f"Page {page_number} would create {len(sub_chunks)} sub-chunks, limiting to 20")
        sub_chunks = sub_chunks[:20]
    
    # Create chunk dictionaries with metadata
    total_parts = len(sub_chunks)
    result_chunks = []
    
    for part_num, sub_text in enumerate(sub_chunks, start=1):
        chunk_id = f"{prefix}_page{page_number}_part{part_num}"
        chunk = _make_chunk(
            sub_text, base_metadata, page_number, page_label, section, "page", chunk_id
        )
        
        # Add split metadata
        chunk["metadata"]["is_split"] = True
        chunk["metadata"]["total_parts"] = total_parts
        chunk["metadata"]["part_number"] = part_num
        
        # Add page statistics (for consistency)
        chunk["metadata"]["table_count"] = len(tables)
        chunk["metadata"]["text_block_count"] = len(text_blocks)
        
        result_chunks.append(chunk)
    
    return result_chunks



