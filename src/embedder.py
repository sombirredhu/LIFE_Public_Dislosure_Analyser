"""
Embedder - creates vector embeddings and manages ChromaDB storage.
Uses sentence-transformers for free local embeddings.
"""

import logging
from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

from src.config import (
    CHROMA_DB_PATH,
    CHROMA_COLLECTION_NAME,
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSION
)

logger = logging.getLogger(__name__)

# Global embedding model instance (loaded once)
_embedding_model = None


def get_embedding_model() -> SentenceTransformer:
    """Get or initialize the embedding model (singleton pattern)."""
    global _embedding_model
    if _embedding_model is None:
        logger.info("[EMBEDDER] Loading embedding model: %s", EMBEDDING_MODEL)
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL)
        logger.info("[EMBEDDER] Model loaded")
    return _embedding_model


def get_or_create_collection():
    """
    Get or create the ChromaDB collection.
    Returns the collection object.
    """
    client = chromadb.PersistentClient(
        path=CHROMA_DB_PATH,
        settings=Settings(
            anonymized_telemetry=False,
            allow_reset=True
        )
    )
    
    # Get or create collection — cosine distance so score = 1.0 - distance is cosine similarity
    collection = client.get_or_create_collection(
        name=CHROMA_COLLECTION_NAME,
        metadata={
            "hnsw:space": "cosine",
            "description": "IRDAI Public Disclosure Reports - Insurance Companies",
        }
    )
    
    return collection


def is_already_indexed(source_file: str) -> bool:
    """
    Check if a file has already been indexed in ChromaDB.
    
    Args:
        source_file: Filename (e.g., "HDFC_Life_Q1_FY25.pdf")
    
    Returns:
        True if file is already indexed, False otherwise
    """
    collection = get_or_create_collection()
    
    # Query for any chunks from this file
    results = collection.get(
        where={"source_file": source_file},
        limit=1
    )
    
    return len(results["ids"]) > 0


def delete_file_chunks(source_file: str) -> int:
    """
    Delete all chunks from a specific file.
    Used for re-indexing.
    
    Args:
        source_file: Filename to delete
    
    Returns:
        Number of chunks deleted
    """
    collection = get_or_create_collection()
    
    # Get all chunk IDs for this file
    results = collection.get(
        where={"source_file": source_file}
    )
    
    chunk_ids = results["ids"]
    
    if chunk_ids:
        collection.delete(ids=chunk_ids)
    
    return len(chunk_ids)


def embed_chunks(chunks: List[Dict[str, Any]], force_reindex: bool = False) -> Dict[str, Any]:
    """
    Create embeddings for chunks and store in ChromaDB.
    OPTIMIZATION 3: Batch processing for embeddings (all chunks encoded at once).
    
    Args:
        chunks: List of chunk dictionaries from chunker
        force_reindex: If True, delete existing chunks for this file first
    
    Returns:
        Dictionary with ingestion statistics
    """
    if not chunks:
        return {
            "status": "error",
            "message": "No chunks provided",
            "chunks_added": 0
        }
    
    source_file = chunks[0]["metadata"]["source_file"]
    
    # Check if already indexed
    already_indexed = is_already_indexed(source_file)
    
    if already_indexed and not force_reindex:
        return {
            "status": "skipped",
            "message": f"{source_file} is already indexed. Use force_reindex=True to re-index.",
            "chunks_added": 0,
            "already_indexed": True
        }
    
    # Delete existing chunks if force reindex
    if already_indexed and force_reindex:
        deleted_count = delete_file_chunks(source_file)
        logger.info("[EMBEDDER] Deleted %d existing chunks for %s", deleted_count, source_file)
    
    # Get collection and embedding model
    collection = get_or_create_collection()
    model = get_embedding_model()
    
    # Extract texts and metadata
    texts = [chunk["text"] for chunk in chunks]
    chunk_ids = [chunk["metadata"]["chunk_id"] for chunk in chunks]
    metadatas = [chunk["metadata"] for chunk in chunks]
    
    # OPTIMIZATION 3: Batch encode all chunks at once (much faster than one-by-one)
    import time as _time
    t_emb = _time.time()
    logger.info("[EMBEDDER] Batch encoding %d chunks (%s)", len(texts), source_file)
    # Use smaller batch size for better CPU performance
    embeddings = model.encode(texts, show_progress_bar=False, batch_size=16)
    logger.info("[EMBEDDER] Batch encoding done in %.1fs", _time.time() - t_emb)

    # Convert numpy arrays to lists for ChromaDB
    embeddings_list = [emb.tolist() for emb in embeddings]

    # Add to ChromaDB in batches (ChromaDB handles this efficiently)
    t_store = _time.time()
    logger.info("[EMBEDDER] Storing %d chunks in ChromaDB collection '%s'", len(chunks), CHROMA_COLLECTION_NAME)
    collection.add(
        ids=chunk_ids,
        embeddings=embeddings_list,
        documents=texts,
        metadatas=metadatas
    )
    logger.info("[EMBEDDER] Stored in %.1fs | total in DB: %d", _time.time() - t_store, collection.count())

    return {
        "status": "success",
        "message": f"Successfully indexed {len(chunks)} chunks from {source_file}",
        "chunks_added": len(chunks),
        "already_indexed": False,
        "source_file": source_file
    }


def get_indexed_companies() -> list:
    """
    Return all unique company_codes currently stored in ChromaDB.
    Called by rag_pipeline to know which companies need top-up retrieval.
    """
    collection = get_or_create_collection()
    total = collection.count()
    if total == 0:
        return []
    results = collection.get(include=["metadatas"])
    return sorted(set(m["company_code"] for m in results["metadatas"]))


def get_available_quarters() -> List[str]:
    """
    Return all unique quarters currently stored in ChromaDB.
    Returns sorted list like ["Q1", "Q2", "Q3", "Q4"].
    """
    collection = get_or_create_collection()
    total = collection.count()
    if total == 0:
        return []
    results = collection.get(include=["metadatas"])
    quarters = sorted(set(m["quarter"] for m in results["metadatas"]))
    return quarters


def get_available_fys() -> List[str]:
    """
    Return all unique fiscal years currently stored in ChromaDB.
    Returns sorted list like ["FY25", "FY26", "FY27"].
    """
    collection = get_or_create_collection()
    total = collection.count()
    if total == 0:
        return []
    results = collection.get(include=["metadatas"])
    fys = sorted(set(m["fy"] for m in results["metadatas"]))
    return fys


def get_collection_stats() -> Dict[str, Any]:
    """Get statistics about the ChromaDB collection."""
    collection = get_or_create_collection()
    
    total_chunks = collection.count()
    
    # Get all metadata to compute stats (skip documents/embeddings)
    if total_chunks > 0:
        results = collection.get(include=["metadatas"])
        metadatas = results["metadatas"]
        
        # Count unique files
        unique_files = set(m["source_file"] for m in metadatas)
        
        # Count by company
        companies = {}
        for m in metadatas:
            company = m["company"]
            companies[company] = companies.get(company, 0) + 1
        
        return {
            "total_chunks": total_chunks,
            "unique_files": len(unique_files),
            "files": sorted(unique_files),
            "chunks_by_company": companies
        }
    else:
        return {
            "total_chunks": 0,
            "unique_files": 0,
            "files": [],
            "chunks_by_company": {}
        }


if __name__ == "__main__":
    # Test embedder
    import sys
    import json
    from pathlib import Path
    from src.config import PROCESSED_OUTPUT_DIR
    from src.chunker import chunk_document
    
    # Get collection stats
    print("Current ChromaDB Collection Stats:")
    stats = get_collection_stats()
    print(f"  Total Chunks: {stats['total_chunks']}")
    print(f"  Unique Files: {stats['unique_files']}")
    
    if stats['chunks_by_company']:
        print(f"  Chunks by Company:")
        for company, count in stats['chunks_by_company'].items():
            print(f"    {company}: {count}")
    
    # If a JSON file is provided, embed it
    if len(sys.argv) > 1:
        json_path = sys.argv[1]
        
        print(f"\nEmbedding chunks from: {json_path}")
        
        with open(json_path, 'r', encoding='utf-8') as f:
            parsed_doc = json.load(f)
        
        chunks = chunk_document(parsed_doc)
        result = embed_chunks(chunks)
        
        print(f"\n✓ {result['message']}")
        print(f"  Status: {result['status']}")
        print(f"  Chunks Added: {result['chunks_added']}")
