import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
from uuid import uuid4

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
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.jobs: Dict[str, IngestionJob] = {}
        self.jobs_lock = threading.RLock()
        self._initialized = True

    def _set_job_state(self, job_id: str, **updates) -> None:
        with self.jobs_lock:
            job = self.jobs.get(job_id)
            if not job:
                return
            for k, v in updates.items():
                setattr(job, k, v)

    def _get_job_ref(self, job_id: str) -> Optional[IngestionJob]:
        with self.jobs_lock:
            return self.jobs.get(job_id)

    def submit_job(self, pdf_path: str, force_reindex: bool = False) -> str:
        fn = Path(pdf_path).name
        jid = f"{fn}_{uuid4().hex[:12]}"
        with self.jobs_lock:
            self.jobs[jid] = IngestionJob(jid, pdf_path, fn, JobStatus.PENDING)
        self.executor.submit(self._process_job, jid, pdf_path, force_reindex)
        return jid

    def _process_job(self, jid: str, pdf_path: str, force_reindex: bool):
        try:
            self._set_job_state(jid, status=JobStatus.PROCESSING, progress=0.1)
            from src.pdf_parser import parse_pdf
            from src.chunker import chunk_document
            from src.embedder import embed_chunks
            doc = parse_pdf(pdf_path)
            self._set_job_state(jid, progress=0.4)
            chunks = chunk_document(doc)
            self._set_job_state(jid, progress=0.6)
            res = embed_chunks(chunks, force_reindex=force_reindex)
            self._set_job_state(jid, progress=0.9)
            if res["status"] in ["success", "skipped"]:
                job = self._get_job_ref(jid)
                source_name = job.filename if job else Path(pdf_path).name
                result = {
                    "status": res["status"], "message": res["message"], "source_file": source_name,
                    "company": doc.get("company"), "period": doc.get("period_label"),
                    "pages_processed": doc.get("total_pages", 0), "chunks_created": len(chunks),
                    "already_indexed": res["status"] == "skipped", "duration_seconds": 0
                }
                self._set_job_state(jid, result=result, status=JobStatus.COMPLETED, progress=1.0)
            else:
                self._set_job_state(jid, status=JobStatus.FAILED, error=res.get("message", "Unknown error"))
        except Exception as e:
            self._set_job_state(jid, status=JobStatus.FAILED, error=str(e), progress=0.0)
            logger.exception("Job %s crashed", jid)

    def get_job_status(self, jid: str) -> Optional[IngestionJob]:
        return self._get_job_ref(jid)

    def clear_completed_jobs(self):
        with self.jobs_lock:
            to_del = [jid for jid, j in self.jobs.items() if j.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]]
            for jid in to_del:
                del self.jobs[jid]

def get_worker(max_workers: int = 2) -> BackgroundWorker:
    global _worker_instance
    if '_worker_instance' not in globals() or _worker_instance is None:
        _worker_instance = BackgroundWorker(max_workers=max_workers)
    return _worker_instance
