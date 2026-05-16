import logging
import time
import requests
from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings
from src.config import (
    CHROMA_DB_PATH, CHROMA_COLLECTION_NAME, EMBEDDING_MODEL,
    EMBEDDING_DIMENSION, EMBEDDING_BATCH_SIZE, OPENROUTER_API_KEY, OPENROUTER_BASE_URL
)

logger = logging.getLogger(__name__)
_chroma_client = None
_chroma_collection = None

def _embed_texts_via_api(texts: List[str], max_retries: int = 3) -> List[List[float]]:
    cleaned = [t.strip()[:8000] if t.strip() else "empty" for t in texts]
    url = f"{OPENROUTER_BASE_URL}/embeddings"
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    all_embeddings = []
    for i in range(0, len(cleaned), EMBEDDING_BATCH_SIZE):
        batch = cleaned[i:i + EMBEDDING_BATCH_SIZE]
        last_err = None
        for attempt in range(max_retries):
            try:
                resp = requests.post(url, headers=headers, json={"model": EMBEDDING_MODEL, "input": batch}, timeout=60)
                resp.raise_for_status()
                data = resp.json()["data"]
                data.sort(key=lambda x: x["index"])
                all_embeddings.extend([item["embedding"] for item in data])
                last_err = None
                break
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                last_err = e
                time.sleep(2 ** attempt)
            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 429:
                    last_err = e
                    time.sleep(2 ** attempt + 1)
                else:
                    raise
        if last_err:
            raise last_err
    return all_embeddings

def embed_query(text: str) -> List[float]:
    return _embed_texts_via_api([text])[0]

def embed_queries(texts: List[str]) -> List[List[float]]:
    return _embed_texts_via_api(texts)

def get_embedding_model():
    return None

def get_or_create_collection():
    global _chroma_client, _chroma_collection
    if _chroma_collection is not None: return _chroma_collection
    _chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH, settings=Settings(anonymized_telemetry=False, allow_reset=True))
    _chroma_collection = _chroma_client.get_or_create_collection(name=CHROMA_COLLECTION_NAME, metadata={"hnsw:space": "cosine"})
    return _chroma_collection

def is_already_indexed(source_file: str) -> bool:
    return len(get_or_create_collection().get(where={"source_file": source_file}, limit=1)["ids"]) > 0

def delete_file_chunks(source_file: str) -> int:
    coll = get_or_create_collection()
    res = coll.get(where={"source_file": source_file})
    if res["ids"]: coll.delete(ids=res["ids"])
    return len(res["ids"])

def embed_chunks(chunks: List[Dict[str, Any]], force_reindex: bool = False) -> Dict[str, Any]:
    if not chunks: return {"status": "error", "message": "No chunks", "chunks_added": 0}
    src = chunks[0]["metadata"]["source_file"]
    if is_already_indexed(src) and not force_reindex:
        return {"status": "skipped", "message": f"{src} already indexed", "chunks_added": 0, "already_indexed": True}
    if is_already_indexed(src): delete_file_chunks(src)
    texts = [c["text"] for c in chunks]
    ids = [c["metadata"]["chunk_id"] for c in chunks]
    metas = [c["metadata"] for c in chunks]
    try:
        embeddings = _embed_texts_via_api(texts)
    except Exception as e:
        logger.error("[EMBED] API error: %s", e)
        return {"status": "error", "message": str(e), "chunks_added": 0}
    get_or_create_collection().add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metas)
    return {"status": "success", "message": f"Indexed {len(chunks)} chunks", "chunks_added": len(chunks), "already_indexed": False, "source_file": src}

_CACHE_TTL = 30
_metadata_cache = {"ts": 0.0, "data": None}

def _get_cached_metadatas() -> List[Dict[str, Any]]:
    now = time.time()
    if _metadata_cache["data"] is not None and (now - _metadata_cache["ts"]) < _CACHE_TTL: return _metadata_cache["data"]
    coll = get_or_create_collection()
    if coll.count() == 0:
        _metadata_cache.update({"ts": now, "data": []})
        return []
    res = coll.get(include=["metadatas"])
    _metadata_cache.update({"ts": now, "data": res["metadatas"]})
    return res["metadatas"]

def invalidate_metadata_cache():
    _metadata_cache.update({"ts": 0.0, "data": None})

def get_indexed_companies() -> List[str]:
    m = _get_cached_metadatas()
    return sorted(set(x["company_code"] for x in m)) if m else []

def get_available_quarters() -> List[str]:
    m = _get_cached_metadatas()
    return sorted(set(x["quarter"] for x in m)) if m else []

def get_available_fys() -> List[str]:
    m = _get_cached_metadatas()
    return sorted(set(x["fy"] for x in m)) if m else []

def get_collection_stats() -> Dict[str, Any]:
    metas = _get_cached_metadatas()
    if not metas: return {"total_chunks": 0, "unique_files": 0, "files": [], "chunks_by_company": {}}
    files = sorted(set(m["source_file"] for m in metas))
    cos = {}
    for m in metas: cos[m["company"]] = cos.get(m["company"], 0) + 1
    return {"total_chunks": len(metas), "unique_files": len(files), "files": files, "chunks_by_company": cos}
