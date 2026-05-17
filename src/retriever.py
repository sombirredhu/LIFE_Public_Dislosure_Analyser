import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional
from src.config import TOP_K_SIMPLE, SIMILARITY_THRESHOLD
from src.embedder import get_or_create_collection, embed_query, embed_queries

logger = logging.getLogger(__name__)
_DOMAIN_PREFIX = "IRDAI life insurance financial report: "
_FALLBACK_THRESHOLD = 0.10
_LAST_RESORT_THRESHOLD = -1.0

def _metadata_overlap_penalty(candidate: Dict[str, Any], selected: List[Dict[str, Any]]) -> float:
    """Apply small penalties for near-duplicate metadata patterns to increase diversity."""
    meta = candidate.get("metadata", {})
    company = meta.get("company_code")
    page_label = meta.get("page_label")
    section = meta.get("section")
    penalty = 0.0
    for s in selected:
        sm = s.get("metadata", {})
        if company and company == sm.get("company_code"):
            penalty += 0.04
        if page_label and page_label == sm.get("page_label"):
            penalty += 0.03
        if section and section == sm.get("section"):
            penalty += 0.02
    return penalty

def _diversify_chunks(chunks: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
    """
    Greedy diversity-aware ranking:
    start from relevance score, then penalize repeated company/page/section patterns.
    """
    if not chunks:
        return chunks
    ordered = sorted(chunks, key=lambda c: c.get("score", 0.0), reverse=True)
    selected: List[Dict[str, Any]] = []
    while ordered and len(selected) < top_k:
        best_idx = 0
        best_adjusted = -1.0
        for i, c in enumerate(ordered):
            adjusted = float(c.get("score", 0.0)) - _metadata_overlap_penalty(c, selected)
            if adjusted > best_adjusted:
                best_adjusted = adjusted
                best_idx = i
        selected.append(ordered.pop(best_idx))
    return selected

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
            score = max(0.0, min(1.0, score))
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
    if not chunks:
        chunks = _raw_retrieve(emb, coll, top_k, norm, _FALLBACK_THRESHOLD)
    if not chunks:
        raw_emb = embed_query(query)
        chunks = _raw_retrieve(raw_emb, coll, top_k, norm, SIMILARITY_THRESHOLD)
        if not chunks:
            chunks = _raw_retrieve(raw_emb, coll, top_k, norm, _FALLBACK_THRESHOLD)
        if not chunks:
            chunks = _raw_retrieve(raw_emb, coll, top_k, norm, _LAST_RESORT_THRESHOLD)
    return _diversify_chunks(chunks, top_k)[:top_k]

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
    if not all_chunks:
        raw_embs = embed_queries(queries)
        for emb in raw_embs:
            for c in _raw_retrieve(emb, coll, effective_k, norm, SIMILARITY_THRESHOLD):
                cid = c["metadata"].get("chunk_id", c["text"][:80])
                if cid not in all_chunks or c["score"] > all_chunks[cid]["score"]: all_chunks[cid] = c
        if not all_chunks:
            for emb in raw_embs:
                for c in _raw_retrieve(emb, coll, effective_k, norm, _FALLBACK_THRESHOLD):
                    cid = c["metadata"].get("chunk_id", c["text"][:80])
                    if cid not in all_chunks or c["score"] > all_chunks[cid]["score"]: all_chunks[cid] = c
        if not all_chunks:
            for emb in raw_embs:
                for c in _raw_retrieve(emb, coll, effective_k, norm, _LAST_RESORT_THRESHOLD):
                    cid = c["metadata"].get("chunk_id", c["text"][:80])
                    if cid not in all_chunks or c["score"] > all_chunks[cid]["score"]: all_chunks[cid] = c
    ranked = sorted(all_chunks.values(), key=lambda x: x["score"], reverse=True)
    return _diversify_chunks(ranked, effective_k)[:effective_k]

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
