"""
Chunker - splits parsed PDF content into chunks with metadata.
Supports two strategies:
1. Page-wise chunking (default): One chunk per page, preserving semantic coherence
2. Text-based chunking (legacy): Overlapping chunks for backward compatibility
"""

import logging
from typing import Any, Dict, List

from src.config import CHUNK_SIZE, CHUNK_OVERLAP, MIN_CHUNK_SIZE, PAGE_WISE_CHUNKING, MAX_PAGE_TOKENS
from src.chunking.utils import (
    _detect_content_type, _split_text, _make_chunk,
    _estimate_tokens, _combine_page_content,
)
from src.chunking.table_handler import _chunk_table
from src.chunking.page_splitter import _chunk_page_wise
from src.chunking.sub_chunker import _split_page_into_subchunks

logger = logging.getLogger(__name__)

def chunk_document(
    parsed_doc: Dict[str, Any],
    additional_metadata: Dict[str, Any] = None,
) -> List[Dict[str, Any]]:
    """Convert parsed PDF document into chunks with metadata."""
    base_metadata: Dict[str, Any] = {
        "company":      parsed_doc["company"],
        "company_code": parsed_doc["company_code"],
        "quarter":      parsed_doc["quarter"],
        "fy":           parsed_doc["fy"],
        "period_label": parsed_doc["period_label"],
        "source_file":  parsed_doc["source_file"],
    }

    if additional_metadata:
        base_metadata.update(additional_metadata)

    if PAGE_WISE_CHUNKING:
        logger.info(f"Using page-wise chunking for {parsed_doc['source_file']}")
        all_chunks = _chunk_page_wise(parsed_doc, base_metadata)
    else:
        logger.info(f"Using legacy text-based chunking for {parsed_doc['source_file']}")
        all_chunks: List[Dict[str, Any]] = []
        chunk_counter = 1
        prefix = f"{base_metadata['company_code']}_{base_metadata['quarter']}_{base_metadata['fy']}"

        for page in parsed_doc["pages"]:
            page_number = page["page_number"]
            page_label  = page.get("page_label", "")
            section     = page.get("section", "unknown")

            for table in page["tables"]:
                table_chunks = _chunk_table(
                    table, base_metadata, page_number, page_label, section, chunk_counter
                )
                all_chunks.extend(table_chunks)
                chunk_counter += len(table_chunks)

            for text_block in page["text_blocks"]:
                if len(text_block) < MIN_CHUNK_SIZE:
                    continue

                for sub_text in _split_text(text_block, CHUNK_SIZE, CHUNK_OVERLAP):
                    if len(sub_text) < MIN_CHUNK_SIZE:
                        continue

                    ctype = _detect_content_type(sub_text, section, page_number, is_table=False)
                    cid = f"{prefix}_page{page_number}_chunk{chunk_counter}"
                    all_chunks.append(
                        _make_chunk(sub_text, base_metadata, page_number, page_label, section, ctype, cid)
                    )
                    chunk_counter += 1

    if all_chunks:
        avg_size = sum(c["metadata"]["char_count"] for c in all_chunks) // len(all_chunks)
        logger.info(f"Chunking complete: {len(all_chunks)} chunks, avg size {avg_size} chars")

    return all_chunks

if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path
    from src.config import PROCESSED_OUTPUT_DIR

    if len(sys.argv) > 1:
        json_path = sys.argv[1]
    else:
        json_files = [f for f in Path(PROCESSED_OUTPUT_DIR).glob("*.json")
                      if not f.name.endswith("_page_definitions.json")]
        if json_files:
            json_path = str(json_files[0])
        else:
            print(f"No JSON files found in {PROCESSED_OUTPUT_DIR}")
            sys.exit(1)

    print(f"Chunking: {json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        parsed_doc = json.load(f)

    chunks = chunk_document(parsed_doc)
    print(f"\\n✓ Chunking complete! Total Chunks: {len(chunks)}")
