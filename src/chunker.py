import logging
from typing import Any, Dict, List
from src.config import CHUNK_SIZE, CHUNK_OVERLAP, MIN_CHUNK_SIZE, PAGE_WISE_CHUNKING
from src.chunking.utils import _detect_content_type, _split_text, _make_chunk
from src.chunking.table_handler import _chunk_table
from src.chunking.page_splitter import _chunk_page_wise

logger = logging.getLogger(__name__)

def chunk_document(parsed_doc: Dict[str, Any], additional_metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    base_meta = {"company": parsed_doc["company"], "company_code": parsed_doc["company_code"], "quarter": parsed_doc["quarter"], "fy": parsed_doc["fy"], "period_label": parsed_doc["period_label"], "source_file": parsed_doc["source_file"]}
    if additional_metadata: base_meta.update(additional_metadata)
    if PAGE_WISE_CHUNKING: return _chunk_page_wise(parsed_doc, base_meta)
    chunks, counter, prefix = [], 1, f"{base_meta['company_code']}_{base_meta['quarter']}_{base_meta['fy']}"
    for pg in parsed_doc["pages"]:
        pn, pl, sec = pg["page_number"], pg.get("page_label", ""), pg.get("section", "unknown")
        for t in pg["tables"]:
            tc = _chunk_table(t, base_meta, pn, pl, sec, counter)
            chunks.extend(tc); counter += len(tc)
        for tb in pg["text_blocks"]:
            if len(tb) < MIN_CHUNK_SIZE: continue
            for st in _split_text(tb, CHUNK_SIZE, CHUNK_OVERLAP):
                if len(st) < MIN_CHUNK_SIZE: continue
                ct = _detect_content_type(st, sec, pn, is_table=False)
                chunks.append(_make_chunk(st, base_meta, pn, pl, sec, ct, f"{prefix}_page{pn}_chunk{counter}"))
                counter += 1
    return chunks
