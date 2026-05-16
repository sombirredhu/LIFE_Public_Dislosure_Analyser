import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional
from src.config import TOP_K_SIMPLE, SIMILARITY_THRESHOLD
from src.embedder import get_or_create_collection, embed_query, embed_queries

logger = logging.getLogger(__name__)
_DOMAIN_PREFIX = "IRDAI life insurance financial report: "
_FALLBACK_THRESHOLD = 0.10

def _normalize_filters(filters: Dict[str, Any]) -> Dict[str, Any]:
    if not filters or len(filters) == 1: return filters
    return {"$and": [{k: v} for k, v in filters.items()]}

def _raw_retrieve(query_embedding: List[float], collection, top_k: int, norm_filters: Optional[Dict[str, Any]], threshold: float) -> List[Dict[str, Any]]:
    params = {"query_embeddings": [query_embedding], "n_results": top_k}
    if norm_filters: params["where"] = norm_filters
    try:
        res = collection.query(**params)
    except Exception as e:
        logger.warning("[RETRIEVE] Query failed (filter issue?): %s", e)
        params.pop("where", None)
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
    total = coll.count()
    if total == 0: return []
    top_k = min(top_k or TOP_K_SIMPLE, total)
    norm = _normalize_filters(filters) if filters else None
    emb = embed_query(_DOMAIN_PREFIX + query)
    chunks = _raw_retrieve(emb, coll, top_k, norm, SIMILARITY_THRESHOLD)
    if not chunks: chunks = _raw_retrieve(emb, coll, top_k, norm, _FALLBACK_THRESHOLD)
    return chunks

def retrieve_multi(queries: List[str], filters: Optional[Dict[str, Any]] = None, top_k: int = None) -> List[Dict[str, Any]]:
    if len(queries) == 1: return retrieve(queries[0], filters, top_k)
    coll = get_or_create_collection()
    total = coll.count()
    if total == 0: return []
    effective_k = min(top_k or TOP_K_SIMPLE, total)
    norm = _normalize_filters(filters) if filters else None
    prefixed = [_DOMAIN_PREFIX + q for q in queries]
    all_embs = embed_queries(prefixed)
    all_chunks = {}
    for emb in all_embs:
        for c in _raw_retrieve(emb, coll, effective_k, norm, SIMILARITY_THRESHOLD):
            cid = c["metadata"].get("chunk_id", c["text"][:80])
            if cid not in all_chunks or c["score"] > all_chunks[cid]["score"]: all_chunks[cid] = c
    if not all_chunks:
        for emb in all_embs:
            for c in _raw_retrieve(emb, coll, effective_k, norm, _FALLBACK_THRESHOLD):
                cid = c["metadata"].get("chunk_id", c["text"][:80])
                if cid not in all_chunks or c["score"] > all_chunks[cid]["score"]: all_chunks[cid] = c
    return sorted(all_chunks.values(), key=lambda x: x["score"], reverse=True)[:effective_k]

def top_up_missing_companies(query: str, chunks: List[Dict[str, Any]], expected: List[str], filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    if filters and "company_code" in filters: return chunks
    present = {c["metadata"]["company_code"] for c in chunks}
    missing = [co for co in expected if co not in present]
    if not missing: return chunks
    top_up = []
    with ThreadPoolExecutor(max_workers=min(len(missing), 6)) as pool:
        futs = {pool.submit(retrieve, query, {**(filters or {}), "company_code": co}, 2): co for co in missing}
        for f in as_completed(futs):
            try: top_up.extend(f.result())
            except Exception: pass
    return chunks + top_up

def get_confidence_level(chunks: List[Dict[str, Any]]) -> str:
    if not chunks: return "none"
    s = chunks[0]["score"]
    return "high" if s >= 0.7 else ("medium" if s >= 0.4 else "none")
