import logging
import time
from pathlib import Path
from typing import Dict, Any
from src.pdf_parser import parse_pdf
from src.chunker import chunk_document
from src.embedder import embed_chunks, is_already_indexed

logger = logging.getLogger(__name__)

def ingest_pdf(pdf_path: str, force_reindex: bool = False) -> Dict[str, Any]:
    start_time = time.time()
    pdf_path = Path(pdf_path)
    if not pdf_path.exists(): return {"status": "error", "message": f"File not found: {pdf_path}", "source_file": pdf_path.name}
    try:
        if not force_reindex and is_already_indexed(pdf_path.name):
            return {"status": "skipped", "message": f"{pdf_path.name} already indexed", "source_file": pdf_path.name, "already_indexed": True, "duration_seconds": 0}
        parsed_doc = parse_pdf(str(pdf_path))
        chunks = chunk_document(parsed_doc)
        if not chunks: return {"status": "error", "message": "No chunks created", "source_file": pdf_path.name, "pages_processed": parsed_doc["total_pages"], "chunks_created": 0}
        embed_chunks(chunks, force_reindex=force_reindex)
        duration = time.time() - start_time
        return {"status": "success", "message": f"Ingested {pdf_path.name}", "source_file": pdf_path.name, "company": parsed_doc["company"], "period": parsed_doc["period_label"], "pages_processed": parsed_doc["total_pages"], "chunks_created": len(chunks), "already_indexed": False, "page_definitions_found": parsed_doc.get("page_definitions_found", False), "duration_seconds": round(duration, 2)}
    except Exception as e:
        logger.exception("[INGEST ERROR] %s", pdf_path.name)
        return {"status": "error", "message": str(e), "source_file": pdf_path.name}

def ingest_directory(directory_path: str, force_reindex: bool = False) -> Dict[str, Any]:
    directory = Path(directory_path)
    if not directory.exists(): return {"status": "error", "message": "Directory not found", "files_processed": 0}
    pdf_files = list(directory.glob("*.pdf"))
    if not pdf_files: return {"status": "warning", "message": "No PDFs found", "files_processed": 0}
    results = []
    success = skipped = error = 0
    for pdf_file in pdf_files:
        res = ingest_pdf(str(pdf_file), force_reindex=force_reindex)
        results.append(res)
        if res["status"] == "success": success += 1
        elif res["status"] == "skipped": skipped += 1
        else: error += 1
    return {"status": "complete", "total_files": len(pdf_files), "success_count": success, "skipped_count": skipped, "error_count": error, "results": results}
