from datetime import datetime
from typing import Any, Dict, List
import logging
from src.config import CHUNK_SIZE, CHUNK_OVERLAP, MIN_CHUNK_SIZE, PAGE_WISE_CHUNKING, MAX_PAGE_TOKENS

logger = logging.getLogger(__name__)

_SUMMARY_SECTION_KEYWORDS = ("summary", "highlights", "key metrics", "overview", "executive")
_SUMMARY_TEXT_PREFIXES = (
    "Key Highlights",
    "Executive Summary",
    "Performance Highlights",
    "Summary of Operations",
)

def _estimate_tokens(text: str) -> int:
    """Approximate token count (chars / 4). Used for MAX_PAGE_TOKENS check."""
    return len(text) // 4



def _detect_content_type(text: str, section: str, page_number: int, is_table: bool) -> str:
    """
    Determine content_type for a chunk.
    Values: "table" | "text" | "summary" | "header" | "page"
    """
    if is_table:
        return "table"

    section_lower = section.lower()
    if any(kw in section_lower for kw in _SUMMARY_SECTION_KEYWORDS):
        return "summary"

    if page_number == 1 and section == "unknown":
        return "summary"

    text_start = text[:200]
    if any(text_start.startswith(prefix) for prefix in _SUMMARY_TEXT_PREFIXES):
        return "summary"

    # Header: short line with no sentence-ending punctuation
    stripped = text.strip()
    if len(stripped) < 100 and not any(c in stripped for c in ".!?"):
        return "header"

    return "text"



def _split_text(text: str, max_size: int, overlap: int) -> List[str]:
    """Split text into overlapping chunks at sentence boundaries."""
    if len(text) <= max_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = start + max_size

        if end >= len(text):
            chunks.append(text[start:])
            break

        window = text[start:end]
        last_break = max(window.rfind(". "), window.rfind("! "), window.rfind("? "))

        if last_break > max_size // 2:
            end = start + last_break + 1

        chunks.append(text[start:end].strip())
        start = end - overlap

    return chunks



def _make_chunk(
    text: str,
    base_metadata: Dict[str, Any],
    page_number: int,
    page_label: str,
    section: str,
    content_type: str,
    chunk_id: str,
) -> Dict[str, Any]:
    """Build a single chunk dict with exactly 2 top-level keys: text + metadata."""
    return {
        "text": text,
        "metadata": {
            **base_metadata,
            "chunk_id":    chunk_id,
            "page_number": page_number,
            "page_label":  page_label,
            "section":     section,
            "content_type": content_type,
            "char_count":  len(text),
            "ingested_at": datetime.now().isoformat(),
        },
    }



def _combine_page_content(page: Dict[str, Any]) -> str:
    """
    Combine all tables and text_blocks from a page into a single text string.
    
    This function creates a single semantic unit from a PDF page by concatenating
    all tables (in pipe-separated format) followed by all text blocks. Each element
    is separated by double newlines to maintain visual separation.
    
    The function handles missing or empty arrays gracefully by treating them as
    empty lists. Empty text blocks (whitespace-only) are filtered out.
    
    Args:
        page: Page dictionary from parsed PDF with the following structure:
            - 'tables': List of table dicts, each with 'raw_text' key (pipe-separated format)
            - 'text_blocks': List of text strings extracted from the page
            - Other keys (page_number, page_label, section) are not used by this function
    
    Returns:
        Combined text string with tables followed by text_blocks, separated by "\n\n".
        Returns empty string if page has no tables or text_blocks.
    
    Examples:
        >>> page = {
        ...     "tables": [{"raw_text": "Header1 | Header2\\nValue1 | Value2"}],
        ...     "text_blocks": ["This is a summary.", "Additional notes."]
        ... }
        >>> result = _combine_page_content(page)
        >>> print(result)
        Header1 | Header2
        Value1 | Value2
        
        This is a summary.
        
        Additional notes.
        
        >>> # Empty page
        >>> empty_page = {"tables": [], "text_blocks": []}
        >>> _combine_page_content(empty_page)
        ''
        
        >>> # Page with missing keys
        >>> partial_page = {"text_blocks": ["Only text here"]}
        >>> _combine_page_content(partial_page)
        'Only text here'
    
    Note:
        - Tables are already in pipe-separated format from pdf_parser.py
        - Whitespace-only text blocks are automatically filtered out
        - Missing 'tables' or 'text_blocks' keys are treated as empty arrays
    """
    parts = []
    
    # Add all tables (already in pipe-separated format from pdf_parser)
    tables = page.get("tables", [])
    for table in tables:
        if table and "raw_text" in table:
            parts.append(table["raw_text"])
    
    # Add all text blocks
    text_blocks = page.get("text_blocks", [])
    for text_block in text_blocks:
        if text_block and text_block.strip():
            parts.append(text_block.strip())
    
    # Combine with double newline separator
    return "\n\n".join(parts)



