import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional
from src.config import TOP_K_SIMPLE, SIMILARITY_THRESHOLD
from src.embedder import get_or_create_collection, get_embedding_model

logger = logging.getLogger(__name__)
_DOMAIN_PREFIX = "IRDAI life insurance financial report: "
_FALLBACK_THRESHOLD = 0.10

def _normalize_filters(filters: Dict[str, Any]) -> Dict[str, Any]:
    if not filters or len(filters) == 1: return filters
    return {"$and": [{k: v} for k, v in filters.items()]}

def _raw_retrieve(query_embedding: List[float], collection, top_k: int, normalized_filters: Optional[Dict[str, Any]], threshold: float) -> List[Dict[str, Any]]:
    params = {"query_embeddings": [query_embedding], "n_results": top_k}
    if normalized_filters: params["where"] = normalized_filters
    res = collection.query(**params)
    chunks = []
    if res["ids"] and res["ids"][0]:
        for i in range(len(res["ids"][0])):
            score = round(1.0 - res["distances"][0][i], 4)
            if score >= threshold:
                chunks.append({"text": res["documents"][0][i], "metadata": res["metadatas"][0][i], "score": score})
    return chunks

def retrieve(query: str, filters: Optional[Dict[str, Any]] = None, top_k: int = None) -> List[Dict[str, Any]]:
    coll = get_or_create_collection()
    model = get_embedding_model()
    total = coll.count()
    if total == 0: return []
    top_k = min(top_k or TOP_K_SIMPLE, total)
    norm = _normalize_filters(filters) if filters else None
    emb = model.encode(_DOMAIN_PREFIX + query).tolist()
    chunks = _raw_retrieve(emb, coll, top_k, norm, SIMILARITY_THRESHOLD)
    if not chunks: chunks = _raw_retrieve(emb, coll, top_k, norm, _FALLBACK_THRESHOLD)
    return chunks

def retrieve_multi(queries: List[str], filters: Optional[Dict[str, Any]] = None, top_k: int = None) -> List[Dict[str, Any]]:
    all_chunks = {}
    with ThreadPoolExecutor(max_workers=len(queries)) as pool:
        futs = {pool.submit(retrieve, q, filters, top_k): q for q in queries}
        for f in as_completed(futs):
            for c in f.result():
                cid = c["metadata"].get("chunk_id", c["text"][:50])
                if cid not in all_chunks or c["score"] > all_chunks[cid]["score"]: all_chunks[cid] = c
    return sorted(all_chunks.values(), key=lambda x: x["score"], reverse=True)[:top_k]

def top_up_missing_companies(query: str, chunks: List[Dict[str, Any]], expected_companies: List[str], filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    present = {c["metadata"]["company_code"] for c in chunks}
    missing = [co for co in expected_companies if co not in present]
    if not missing: return chunks
    def _fetch_one(co: str) -> List[Dict[str, Any]]:
        return retrieve(query, filters={**(filters or {}), "company_code": co}, top_k=2)
    top_up = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(_fetch_one, co): co for co in missing}
        for f in as_completed(futs):
            try: top_up.extend(f.result())
            except Exception: pass
    return chunks + top_up

def get_confidence_level(chunks: List[Dict[str, Any]]) -> str:
    if not chunks: return "none"
    s = chunks[0]["score"]
    return "high" if s >= 0.7 else ("medium" if s >= 0.4 else "none")
