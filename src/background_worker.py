"""
Background Worker - Handles PDF ingestion in background threads.
OPTIMIZATION 1: Process PDFs in background (don't block Streamlit UI)
OPTIMIZATION 2: Process multiple PDFs in parallel
"""

import logging
import threading
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Any, Callable, Optional
from dataclasses import dataclass
from enum import Enum

from src.ingestor import ingest_pdf

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    """Status of a background job."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class IngestionJob:
    """Represents a single PDF ingestion job."""
    job_id: str
    pdf_path: str
    filename: str
    status: JobStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    progress: float = 0.0  # 0.0 to 1.0


class BackgroundWorker:
    """
    Manages background PDF ingestion with parallel processing.
    Thread-safe singleton for use with Streamlit.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, max_workers: int = 2):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
                    cls._instance._max_workers = max_workers
        return cls._instance
    
    def __init__(self, max_workers: int = 2):
        """
        Initialize background worker.
        
        Args:
            max_workers: Maximum number of PDFs to process in parallel (default: 2)
        """
        if self._initialized:
            return
            
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.jobs: Dict[str, IngestionJob] = {}
        self.job_queue = queue.Queue()
        self._shutdown = False
        self._initialized = True
        
        logger.info("[WORKER] Background worker initialized with %d workers", max_workers)
    
    def submit_job(self, pdf_path: str, force_reindex: bool = False) -> str:
        """
        Submit a PDF for background ingestion.
        
        Args:
            pdf_path: Path to PDF file
            force_reindex: If True, re-index even if already indexed
        
        Returns:
            job_id: Unique identifier for this job
        """
        filename = Path(pdf_path).name
        job_id = f"{filename}_{threading.get_ident()}"
        
        # Create job
        job = IngestionJob(
            job_id=job_id,
            pdf_path=pdf_path,
            filename=filename,
            status=JobStatus.PENDING
        )
        
        self.jobs[job_id] = job
        
        # Submit to executor
        future = self.executor.submit(self._process_job, job_id, pdf_path, force_reindex)
        
        logger.info("[WORKER] Submitted job %s: %s", job_id, filename)
        
        return job_id
    
    def submit_batch(self, pdf_paths: list, force_reindex: bool = False) -> list:
        """
        Submit multiple PDFs for parallel processing.
        
        Args:
            pdf_paths: List of PDF file paths
            force_reindex: If True, re-index even if already indexed
        
        Returns:
            List of job_ids
        """
        job_ids = []
        for pdf_path in pdf_paths:
            job_id = self.submit_job(pdf_path, force_reindex)
            job_ids.append(job_id)
        
        logger.info("[WORKER] Submitted batch of %d jobs", len(job_ids))
        return job_ids
    
    def _process_job(self, job_id: str, pdf_path: str, force_reindex: bool):
        """Internal method to process a single job."""
        job = self.jobs[job_id]
        
        try:
            # Update status
            job.status = JobStatus.PROCESSING
            job.progress = 0.0
            
            logger.info("[WORKER] Processing job %s: %s", job_id, job.filename)
            
            # Track progress through stages
            job.progress = 0.1  # Started
            
            # Import here to track stages
            from src.pdf_parser import parse_pdf
            from src.chunker import chunk_document
            from src.embedder import embed_chunks
            
            # Stage 1: Parse PDF
            job.progress = 0.2
            parsed_doc = parse_pdf(pdf_path)
            job.progress = 0.4
            
            # Stage 2: Chunk document
            chunks = chunk_document(parsed_doc)
            job.progress = 0.6
            
            # Stage 3: Embed chunks
            embed_result = embed_chunks(chunks, force_reindex=force_reindex)
            job.progress = 0.9
            
            # Build result
            if embed_result["status"] == "success":
                result = {
                    "status": "success",
                    "message": f"Successfully ingested {job.filename}",
                    "source_file": job.filename,
                    "company": parsed_doc["company"],
                    "period": parsed_doc["period_label"],
                    "pages_processed": parsed_doc["total_pages"],
                    "chunks_created": len(chunks),
                    "already_indexed": False,
                    "page_definitions_found": parsed_doc.get("page_definitions_found", False),
                    "duration_seconds": 0  # Will be calculated by caller
                }
                job.status = JobStatus.COMPLETED
                job.result = result
                job.progress = 1.0
                logger.info("[WORKER] Job %s completed: %d chunks", job_id, len(chunks))
            elif embed_result["status"] == "skipped":
                result = {
                    "status": "skipped",
                    "message": f"{job.filename} is already indexed",
                    "source_file": job.filename,
                    "already_indexed": True,
                    "duration_seconds": 0
                }
                job.status = JobStatus.COMPLETED
                job.result = result
                job.progress = 1.0
                logger.info("[WORKER] Job %s skipped (already indexed)", job_id)
            else:
                job.status = JobStatus.FAILED
                job.error = embed_result.get("message", "Unknown error")
                job.progress = 0.0
                logger.error("[WORKER] Job %s failed: %s", job_id, job.error)
        
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
            job.progress = 0.0
            logger.exception("[WORKER] Job %s crashed", job_id)
    
    def get_job_status(self, job_id: str) -> Optional[IngestionJob]:
        """Get status of a specific job."""
        return self.jobs.get(job_id)
    
    def get_all_jobs(self) -> Dict[str, IngestionJob]:
        """Get all jobs."""
        return self.jobs.copy()
    
    def wait_for_completion(self, job_ids: list, timeout: Optional[float] = None) -> Dict[str, IngestionJob]:
        """
        Wait for multiple jobs to complete.
        
        Args:
            job_ids: List of job IDs to wait for
            timeout: Maximum time to wait in seconds (None = wait forever)
        
        Returns:
            Dictionary of job_id -> IngestionJob
        """
        import time
        start_time = time.time()
        
        while True:
            all_done = all(
                self.jobs[jid].status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]
                for jid in job_ids if jid in self.jobs
            )
            
            if all_done:
                break
            
            if timeout and (time.time() - start_time) > timeout:
                logger.warning("[WORKER] Timeout waiting for jobs: %s", job_ids)
                break
            
            time.sleep(0.1)
        
        return {jid: self.jobs[jid] for jid in job_ids if jid in self.jobs}
    
    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a pending job (cannot cancel already processing jobs).
        
        Args:
            job_id: Job ID to cancel
        
        Returns:
            True if cancelled, False if already processing/completed
        """
        job = self.jobs.get(job_id)
        if not job:
            return False
        
        if job.status == JobStatus.PENDING:
            job.status = JobStatus.CANCELLED
            logger.info("[WORKER] Cancelled job %s", job_id)
            return True
        
        return False
    
    def clear_completed_jobs(self):
        """Remove completed/failed jobs from memory."""
        to_remove = [
            jid for jid, job in self.jobs.items()
            if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]
        ]
        
        for jid in to_remove:
            del self.jobs[jid]
        
        logger.info("[WORKER] Cleared %d completed jobs", len(to_remove))
    
    def shutdown(self, wait: bool = True):
        """Shutdown the worker and cleanup resources."""
        self._shutdown = True
        self.executor.shutdown(wait=wait)
        logger.info("[WORKER] Background worker shutdown")


# Global worker instance
_worker_instance = None


def get_worker(max_workers: int = 2) -> BackgroundWorker:
    """
    Get or create the global background worker instance.
    
    Args:
        max_workers: Maximum number of parallel workers (only used on first call)
    
    Returns:
        BackgroundWorker instance
    """
    global _worker_instance
    if _worker_instance is None:
        _worker_instance = BackgroundWorker(max_workers=max_workers)
    return _worker_instance


if __name__ == "__main__":
    # Test background worker
    import sys
    from pathlib import Path
    from src.config import PDF_INPUT_DIR
    
    # Get test PDFs
    pdf_files = list(Path(PDF_INPUT_DIR).glob("*.pdf"))[:3]  # Test with first 3 PDFs
    
    if not pdf_files:
        print(f"No PDF files found in {PDF_INPUT_DIR}")
        sys.exit(1)
    
    print(f"Testing background worker with {len(pdf_files)} PDFs\n")
    
    # Create worker
    worker = get_worker(max_workers=2)
    
    # Submit jobs
    job_ids = worker.submit_batch([str(f) for f in pdf_files])
    
    print(f"Submitted {len(job_ids)} jobs")
    print("Waiting for completion...\n")
    
    # Wait and show progress
    import time
    while True:
        all_done = True
        for job_id in job_ids:
            job = worker.get_job_status(job_id)
            if job:
                print(f"  {job.filename}: {job.status.value} ({job.progress*100:.0f}%)")
                if job.status not in [JobStatus.COMPLETED, JobStatus.FAILED]:
                    all_done = False
        
        if all_done:
            break
        
        print()
        time.sleep(2)
    
    # Show results
    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)
    
    for job_id in job_ids:
        job = worker.get_job_status(job_id)
        if job:
            if job.status == JobStatus.COMPLETED:
                print(f"✓ {job.filename}: {job.result.get('chunks_created', 0)} chunks")
            else:
                print(f"✗ {job.filename}: {job.error}")
    
    worker.shutdown()
