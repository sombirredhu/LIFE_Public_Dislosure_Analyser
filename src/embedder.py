import logging
import time
from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from src.config import CHROMA_DB_PATH, CHROMA_COLLECTION_NAME, EMBEDDING_MODEL, EMBEDDING_DIMENSION

logger = logging.getLogger(__name__)

_embedding_model = None
_chroma_client = None
_chroma_collection = None

def get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    return _embedding_model

def get_or_create_collection():
    global _chroma_client, _chroma_collection
    if _chroma_collection is not None: return _chroma_collection
    _chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH, settings=Settings(anonymized_telemetry=False, allow_reset=True))
    _chroma_collection = _chroma_client.get_or_create_collection(name=CHROMA_COLLECTION_NAME, metadata={"hnsw:space": "cosine", "description": "IRDAI Reports"})
    return _chroma_collection

def is_already_indexed(source_file: str) -> bool:
    collection = get_or_create_collection()
    res = collection.get(where={"source_file": source_file}, limit=1)
    return len(res["ids"]) > 0

def delete_file_chunks(source_file: str) -> int:
    collection = get_or_create_collection()
    res = collection.get(where={"source_file": source_file})
    if res["ids"]: collection.delete(ids=res["ids"])
    return len(res["ids"])

def embed_chunks(chunks: List[Dict[str, Any]], force_reindex: bool = False) -> Dict[str, Any]:
    if not chunks: return {"status": "error", "message": "No chunks", "chunks_added": 0}
    source_file = chunks[0]["metadata"]["source_file"]
    if is_already_indexed(source_file) and not force_reindex:
        return {"status": "skipped", "message": f"{source_file} already indexed", "chunks_added": 0, "already_indexed": True}
    if is_already_indexed(source_file) and force_reindex: delete_file_chunks(source_file)
    collection, model = get_or_create_collection(), get_embedding_model()
    texts = [c["text"] for c in chunks]
    ids = [c["metadata"]["chunk_id"] for c in chunks]
    metas = [c["metadata"] for c in chunks]
    embeddings = model.encode(texts, show_progress_bar=False, batch_size=16)
    collection.add(ids=ids, embeddings=[e.tolist() for e in embeddings], documents=texts, metadatas=metas)
    return {"status": "success", "message": f"Indexed {len(chunks)} chunks", "chunks_added": len(chunks), "already_indexed": False, "source_file": source_file}

_CACHE_TTL = 30
_metadata_cache = {"ts": 0.0, "data": None}

def _get_cached_metadatas() -> List[Dict[str, Any]]:
    now = time.time()
    if _metadata_cache["data"] is not None and (now - _metadata_cache["ts"]) < _CACHE_TTL: return _metadata_cache["data"]
    collection = get_or_create_collection()
    if collection.count() == 0:
        _metadata_cache.update({"ts": now, "data": []})
        return []
    res = collection.get(include=["metadatas"])
    _metadata_cache.update({"ts": now, "data": res["metadatas"]})
    return res["metadatas"]

def invalidate_metadata_cache():
    _metadata_cache.update({"ts": 0.0, "data": None})

def get_indexed_companies() -> List[str]:
    metas = _get_cached_metadatas()
    return sorted(set(m["company_code"] for m in metas)) if metas else []

def get_available_quarters() -> List[str]:
    metas = _get_cached_metadatas()
    return sorted(set(m["quarter"] for m in metas)) if metas else []

def get_available_fys() -> List[str]:
    metas = _get_cached_metadatas()
    return sorted(set(m["fy"] for m in metas)) if metas else []

def get_collection_stats() -> Dict[str, Any]:
    metas = _get_cached_metadatas()
    if not metas: return {"total_chunks": 0, "unique_files": 0, "files": [], "chunks_by_company": {}}
    files = sorted(set(m["source_file"] for m in metas))
    companies = {}
    for m in metas: companies[m["company"]] = companies.get(m["company"], 0) + 1
    return {"total_chunks": len(metas), "unique_files": len(files), "files": files, "chunks_by_company": companies}
