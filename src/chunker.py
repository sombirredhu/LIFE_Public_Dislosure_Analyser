import logging
from typing import Any, Dict, List
from src.config import CHUNK_SIZE, CHUNK_OVERLAP, MIN_CHUNK_SIZE, PAGE_WISE_CHUNKING
from src.chunking.utils import (
    _detect_content_type,
    _split_text,
    _make_chunk,
    _estimate_tokens,
    _combine_page_content,
)
from src.chunking.table_handler import _chunk_table
from src.chunking.page_splitter import _chunk_page_wise
from src.chunking.sub_chunker import _split_page_into_subchunks

logger = logging.getLogger(__name__)

def chunk_document(parsed_doc: Dict[str, Any], additional_metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    base_meta = {
        "company": parsed_doc["company"], 
        "company_code": parsed_doc["company_code"], 
        "quarter": parsed_doc["quarter"], 
        "fy": parsed_doc["fy"], 
        "period_label": parsed_doc["period_label"], 
        "source_file": parsed_doc["source_file"]
    }
    
    # Add company full name if available
    if parsed_doc.get("company_full_name"):
        base_meta["company_full_name"] = parsed_doc["company_full_name"]
    
    if additional_metadata: 
        base_meta.update(additional_metadata)
    
    if PAGE_WISE_CHUNKING: 
        return _chunk_page_wise(parsed_doc, base_meta)
    
    chunks, counter, prefix = [], 1, f"{base_meta['company_code']}_{base_meta['quarter']}_{base_meta['fy']}"
    
    for pg in parsed_doc["pages"]:
        pn = pg["page_number"]
        pl = pg.get("page_label", "")
        pl_norm = pg.get("page_label_normalized", "")
        sec = pg.get("section", "unknown")
        company_name = pg.get("company_name")
        
        for t in pg["tables"]:
            tc = _chunk_table(t, base_meta, pn, pl, sec, counter)
            # Add enhanced metadata to table chunks
            for chunk in tc:
                if company_name:
                    chunk["metadata"]["company_full_name"] = company_name
                if pl_norm:
                    chunk["metadata"]["page_label_normalized"] = pl_norm
            chunks.extend(tc)
            counter += len(tc)
        
        for tb in pg["text_blocks"]:
            if len(tb) < MIN_CHUNK_SIZE: 
                continue
            for st in _split_text(tb, CHUNK_SIZE, CHUNK_OVERLAP):
                if len(st) < MIN_CHUNK_SIZE: 
                    continue
                ct = _detect_content_type(st, sec, pn, is_table=False)
                chunk = _make_chunk(st, base_meta, pn, pl, sec, ct, f"{prefix}_page{pn}_chunk{counter}")
                
                # Add enhanced metadata
                if company_name:
                    chunk["metadata"]["company_full_name"] = company_name
                if pl_norm:
                    chunk["metadata"]["page_label_normalized"] = pl_norm
                
                chunks.append(chunk)
                counter += 1
    
    return chunks
