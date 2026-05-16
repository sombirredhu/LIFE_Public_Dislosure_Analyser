from typing import Any, Dict, List
from src.config import CHUNK_SIZE
from src.chunking.utils import _make_chunk

def _chunk_table(
    table_data: Dict[str, Any],
    base_metadata: Dict[str, Any],
    page_number: int,
    page_label: str,
    section: str,
    chunk_counter: int,
) -> List[Dict[str, Any]]:
    """Split a table into chunks, repeating headers for large tables."""
    raw_text = table_data["raw_text"]
    prefix = f"{base_metadata['company_code']}_{base_metadata['quarter']}_{base_metadata['fy']}"

    if len(raw_text) <= CHUNK_SIZE:
        cid = f"{prefix}_page{page_number}_chunk{chunk_counter}"
        return [_make_chunk(raw_text, base_metadata, page_number, page_label, section, "table", cid)]

    headers_text = " | ".join(table_data["headers"])
    rows = table_data["rows"]
    chunks: List[Dict[str, Any]] = []
    current_rows: List[str] = []
    current_size = len(headers_text)

    for row in rows:
        row_text = " | ".join(row)
        row_size = len(row_text) + 1

        if current_size + row_size > CHUNK_SIZE and current_rows:
            body = headers_text + "\n" + "\n".join(current_rows)
            cid = f"{prefix}_page{page_number}_chunk{chunk_counter}"
            chunks.append(_make_chunk(body, base_metadata, page_number, page_label, section, "table", cid))
            chunk_counter += 1
            current_rows = []
            current_size = len(headers_text)

        current_rows.append(row_text)
        current_size += row_size

    if current_rows:
        body = headers_text + "\n" + "\n".join(current_rows)
        cid = f"{prefix}_page{page_number}_chunk{chunk_counter}"
        chunks.append(_make_chunk(body, base_metadata, page_number, page_label, section, "table", cid))

    return chunks



