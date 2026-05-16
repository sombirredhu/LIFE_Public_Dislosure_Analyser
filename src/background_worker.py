import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class JobStatus(Enum):
    PENDING = "pending"; PROCESSING = "processing"; COMPLETED = "completed"; FAILED = "failed"; CANCELLED = "cancelled"

@dataclass
class IngestionJob:
    job_id: str; pdf_path: str; filename: str; status: JobStatus; result: Optional[Dict[str, Any]] = None; error: Optional[str] = None; progress: float = 0.0

class BackgroundWorker:
    _instance, _lock = None, threading.Lock()
    def __new__(cls, max_workers: int = 2):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls); cls._instance._initialized = False
        return cls._instance
    def __init__(self, max_workers: int = 2):
        if self._initialized: return
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.jobs: Dict[str, IngestionJob] = {}; self._initialized = True
    def submit_job(self, pdf_path: str, force_reindex: bool = False) -> str:
        fn = Path(pdf_path).name
        jid = f"{fn}_{threading.get_ident()}"
        self.jobs[jid] = IngestionJob(jid, pdf_path, fn, JobStatus.PENDING)
        self.executor.submit(self._process_job, jid, pdf_path, force_reindex)
        return jid
    def _process_job(self, jid: str, pdf_path: str, force_reindex: bool):
        j = self.jobs[jid]
        try:
            j.status, j.progress = JobStatus.PROCESSING, 0.1
            from src.pdf_parser import parse_pdf
            from src.chunker import chunk_document
            from src.embedder import embed_chunks
            doc = parse_pdf(pdf_path); j.progress = 0.4
            chunks = chunk_document(doc); j.progress = 0.6
            res = embed_chunks(chunks, force_reindex=force_reindex); j.progress = 0.9
            if res["status"] in ["success", "skipped"]:
                j.result = {"status": res["status"], "message": res["message"], "source_file": j.filename, "company": doc.get("company"), "period": doc.get("period_label"), "pages_processed": doc.get("total_pages", 0), "chunks_created": len(chunks), "already_indexed": res["status"]=="skipped", "duration_seconds": 0}
                j.status, j.progress = JobStatus.COMPLETED, 1.0
            else:
                j.status, j.error = JobStatus.FAILED, res.get("message", "Unknown error")
        except Exception as e:
            j.status, j.error, j.progress = JobStatus.FAILED, str(e), 0.0
            logger.exception("Job %s crashed", jid)
    def get_job_status(self, jid: str) -> Optional[IngestionJob]: return self.jobs.get(jid)
    def clear_completed_jobs(self):
        to_del = [jid for jid, j in self.jobs.items() if j.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]]
        for jid in to_del: del self.jobs[jid]

def get_worker(max_workers: int = 2) -> BackgroundWorker:
    global _worker_instance
    if '_worker_instance' not in globals() or _worker_instance is None:
        _worker_instance = BackgroundWorker(max_workers=max_workers)
    return _worker_instance
