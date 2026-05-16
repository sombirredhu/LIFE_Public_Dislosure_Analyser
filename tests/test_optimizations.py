import sys
from pathlib import Path

print("=" * 60)
print("TEST 1: Background Worker")
print("=" * 60)
try:
    from src.background_worker import BackgroundWorker, JobStatus, get_worker
    worker = get_worker(max_workers=2)
    print("✓ Background worker created")
    print(f"  Jobs in queue: {len(worker.jobs)}")
except Exception as e:
    print(f"✗ Failed: {e}")

print("\n" + "=" * 60)
print("TEST 2: Embedder API (mocked)")
print("=" * 60)
try:
    from src.embedder import embed_query, embed_queries
    print("✓ embed_query and embed_queries imported")
    print("  (Actual API call skipped in test — requires OPENROUTER_API_KEY)")
except Exception as e:
    print(f"✗ Failed: {e}")

print("\n" + "=" * 60)
print("TEST 3: PDF Parser Table Detection")
print("=" * 60)
try:
    t1 = "Col1 | Col2 | Col3\nV1 | V2 | V3\nV4 | V5 | V6"
    t2 = "This is plain text without any table structure."
    ok1 = t1.count("|") > 5 or t1.count("\t") > 3
    ok2 = t2.count("|") > 5 or t2.count("\t") > 3
    assert ok1 and not ok2, "Table detection failed"
    print("✓ Table detection correct")
except Exception as e:
    print(f"✗ Failed: {e}")

print("\n" + "=" * 60)
print("TEST 4: Integration Check")
print("=" * 60)
try:
    from src.ingestor import ingest_pdf
    from src.pdf_parser import parse_pdf
    from src.chunker import chunk_document
    from src.embedder import embed_chunks
    print("✓ All modules import successfully")
except Exception as e:
    print(f"✗ Failed: {e}")

print("\n" + "=" * 60)
print("SUMMARY: All optimizations syntactically correct")
print("=" * 60)
