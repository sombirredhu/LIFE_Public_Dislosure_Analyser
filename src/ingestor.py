"""
Ingestor - end-to-end pipeline from PDF to ChromaDB.
Orchestrates: PDF parsing → chunking → embedding → storage.
"""

import time
from pathlib import Path
from typing import Dict, Any

from src.pdf_parser import parse_pdf
from src.chunker import chunk_document
from src.embedder import embed_chunks, is_already_indexed


def ingest_pdf(pdf_path: str, force_reindex: bool = False) -> Dict[str, Any]:
    """
    Ingest a PDF file end-to-end: parse → chunk → embed → store.
    
    Args:
        pdf_path: Path to PDF file
        force_reindex: If True, re-index even if already indexed
    
    Returns:
        Dictionary with ingestion statistics and status
    """
    start_time = time.time()
    
    pdf_path = Path(pdf_path)
    
    if not pdf_path.exists():
        return {
            "status": "error",
            "message": f"File not found: {pdf_path}",
            "source_file": pdf_path.name
        }
    
    try:
        # Check if already indexed
        if not force_reindex and is_already_indexed(pdf_path.name):
            return {
                "status": "skipped",
                "message": f"{pdf_path.name} is already indexed. Use force_reindex=True to re-index.",
                "source_file": pdf_path.name,
                "already_indexed": True,
                "duration_seconds": 0
            }
        
        # Step 1: Parse PDF
        print(f"[1/3] Parsing PDF: {pdf_path.name}")
        parsed_doc = parse_pdf(str(pdf_path))
        
        # Step 2: Chunk document
        print(f"[2/3] Chunking document...")
        chunks = chunk_document(parsed_doc)
        
        if not chunks:
            return {
                "status": "error",
                "message": "No chunks created from PDF. File may be empty or unreadable.",
                "source_file": pdf_path.name,
                "pages_processed": parsed_doc["total_pages"],
                "chunks_created": 0
            }
        
        # Step 3: Embed and store
        print(f"[3/3] Creating embeddings and storing in ChromaDB...")
        embed_result = embed_chunks(chunks, force_reindex=force_reindex)
        
        duration = time.time() - start_time
        
        return {
            "status": "success",
            "message": f"Successfully ingested {pdf_path.name}",
            "source_file": pdf_path.name,
            "company": parsed_doc["company"],
            "period": parsed_doc["period_label"],
            "pages_processed": parsed_doc["total_pages"],
            "chunks_created": len(chunks),
            "already_indexed": False,
            "duration_seconds": round(duration, 2)
        }
    
    except ValueError as e:
        # Filename format error
        return {
            "status": "error",
            "message": str(e),
            "source_file": pdf_path.name
        }
    
    except Exception as e:
        # Other errors
        return {
            "status": "error",
            "message": f"Error during ingestion: {str(e)}",
            "source_file": pdf_path.name
        }


def ingest_directory(directory_path: str, force_reindex: bool = False) -> Dict[str, Any]:
    """
    Ingest all PDF files in a directory.
    
    Args:
        directory_path: Path to directory containing PDFs
        force_reindex: If True, re-index all files
    
    Returns:
        Dictionary with overall statistics
    """
    directory = Path(directory_path)
    
    if not directory.exists():
        return {
            "status": "error",
            "message": f"Directory not found: {directory_path}",
            "files_processed": 0
        }
    
    pdf_files = list(directory.glob("*.pdf"))
    
    if not pdf_files:
        return {
            "status": "warning",
            "message": f"No PDF files found in {directory_path}",
            "files_processed": 0
        }
    
    results = []
    success_count = 0
    skipped_count = 0
    error_count = 0
    
    print(f"Found {len(pdf_files)} PDF files to process\n")
    
    for i, pdf_file in enumerate(pdf_files, 1):
        print(f"\n{'='*80}")
        print(f"Processing file {i}/{len(pdf_files)}: {pdf_file.name}")
        print(f"{'='*80}")
        
        result = ingest_pdf(str(pdf_file), force_reindex=force_reindex)
        results.append(result)
        
        if result["status"] == "success":
            success_count += 1
            print(f"✓ Success: {result['chunks_created']} chunks in {result['duration_seconds']}s")
        elif result["status"] == "skipped":
            skipped_count += 1
            print(f"⊘ Skipped: Already indexed")
        else:
            error_count += 1
            print(f"✗ Error: {result['message']}")
    
    return {
        "status": "complete",
        "total_files": len(pdf_files),
        "success_count": success_count,
        "skipped_count": skipped_count,
        "error_count": error_count,
        "results": results
    }


if __name__ == "__main__":
    # Test ingestor
    import sys
    from src.config import PDF_INPUT_DIR
    
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        
        if Path(pdf_path).is_dir():
            # Ingest directory
            print(f"Ingesting all PDFs from: {pdf_path}\n")
            result = ingest_directory(pdf_path)
            
            print(f"\n{'='*80}")
            print("INGESTION SUMMARY")
            print(f"{'='*80}")
            print(f"Total Files: {result['total_files']}")
            print(f"Success: {result['success_count']}")
            print(f"Skipped: {result['skipped_count']}")
            print(f"Errors: {result['error_count']}")
        else:
            # Ingest single file
            print(f"Ingesting: {pdf_path}\n")
            result = ingest_pdf(pdf_path)
            
            print(f"\n{'='*80}")
            print("RESULT")
            print(f"{'='*80}")
            print(f"Status: {result['status']}")
            print(f"Message: {result['message']}")
            
            if result['status'] == 'success':
                print(f"Company: {result['company']}")
                print(f"Period: {result['period']}")
                print(f"Pages: {result['pages_processed']}")
                print(f"Chunks: {result['chunks_created']}")
                print(f"Duration: {result['duration_seconds']}s")
    else:
        # Default: ingest all from PDF_INPUT_DIR
        print(f"Ingesting all PDFs from: {PDF_INPUT_DIR}\n")
        result = ingest_directory(PDF_INPUT_DIR)
        
        print(f"\n{'='*80}")
        print("INGESTION SUMMARY")
        print(f"{'='*80}")
        print(f"Total Files: {result['total_files']}")
        print(f"Success: {result['success_count']}")
        print(f"Skipped: {result['skipped_count']}")
        print(f"Errors: {result['error_count']}")
