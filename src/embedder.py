"""
Embedder - creates vector embeddings and manages ChromaDB storage.
Uses sentence-transformers for free local embeddings.
"""

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

# Global embedding model instance (loaded once)
_embedding_model = None


def get_embedding_model() -> SentenceTransformer:
    """Get or initialize the embedding model (singleton pattern)."""
    global _embedding_model
    if _embedding_model is None:
        print(f"Loading embedding model: {EMBEDDING_MODEL}")
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL)
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
    
    # Get or create collection
    collection = client.get_or_create_collection(
        name=CHROMA_COLLECTION_NAME,
        metadata={"description": "IRDAI Public Disclosure Reports - Insurance Companies"}
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
        print(f"Deleted {deleted_count} existing chunks for {source_file}")
    
    # Get collection and embedding model
    collection = get_or_create_collection()
    model = get_embedding_model()
    
    # Extract texts and metadata
    texts = [chunk["text"] for chunk in chunks]
    chunk_ids = [chunk["chunk_id"] for chunk in chunks]
    metadatas = [chunk["metadata"] for chunk in chunks]
    
    # Create embeddings
    print(f"Creating embeddings for {len(texts)} chunks...")
    embeddings = model.encode(texts, show_progress_bar=True)
    
    # Convert numpy arrays to lists for ChromaDB
    embeddings_list = [emb.tolist() for emb in embeddings]
    
    # Add to ChromaDB
    print(f"Storing chunks in ChromaDB...")
    collection.add(
        ids=chunk_ids,
        embeddings=embeddings_list,
        documents=texts,
        metadatas=metadatas
    )
    
    return {
        "status": "success",
        "message": f"Successfully indexed {len(chunks)} chunks from {source_file}",
        "chunks_added": len(chunks),
        "already_indexed": False,
        "source_file": source_file
    }


def get_collection_stats() -> Dict[str, Any]:
    """Get statistics about the ChromaDB collection."""
    collection = get_or_create_collection()
    
    total_chunks = collection.count()
    
    # Get all metadata to compute stats
    if total_chunks > 0:
        results = collection.get()
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
