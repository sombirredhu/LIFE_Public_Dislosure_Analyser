import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from src.config import TOP_K_SIMPLE, SIMILARITY_THRESHOLD
from src.embedder import get_or_create_collection, embed_query, embed_queries

logger = logging.getLogger(__name__)
_DOMAIN_PREFIX = "IRDAI life insurance financial report: "
_FALLBACK_THRESHOLD = 0.10
_LAST_RESORT_THRESHOLD = -1.0
_LPAGE_TOKEN_RE = re.compile(r"\bL-\d+[A-Z]?(?:-[A-Z]-[A-Z]{2})?\b", re.I)
_TOPUP_NOISE_WORDS = {
    "compare", "comparison", "show", "list", "rank", "ranking", "across", "between",
    "for", "all", "companies", "company", "wise", "each", "metric", "metrics",
    "cite", "source", "sources", "with", "and", "the", "of", "to", "page", "pages",
    "quarter", "quarters", "fy", "value", "values", "highest", "lowest",
}

def _extract_topup_intent(query: str) -> Tuple[Set[str], Set[str]]:
    q = (query or "").strip()
    lpages = {m.upper() for m in _LPAGE_TOKEN_RE.findall(q)}
    terms = {
        w.lower()
        for w in re.findall(r"\b[a-z]{4,}\b", q.lower())
        if w.lower() not in _TOPUP_NOISE_WORDS
    }
    return lpages, terms

def _lpage_match(page_label: str, target: str) -> bool:
    p = (page_label or "").upper()
    t = (target or "").upper()
    return p == t or p.startswith(f"{t}-") or t.startswith(f"{p}-")

def _base_lpage(token: str) -> str:
    m = re.match(r"^(L-\d+[A-Z]?)", (token or "").upper())
    return m.group(1) if m else (token or "").upper()

def _intent_score(chunk: Dict[str, Any], lpages: Set[str], terms: Set[str]) -> int:
    meta = chunk.get("metadata", {})
    score = 0
    page_label = str(meta.get("page_label", ""))
    section = str(meta.get("section", "")).lower()
    text = str(chunk.get("text", "")).lower()

    if lpages and any(_lpage_match(page_label, lp) for lp in lpages):
        score += 4

    for t in terms:
        if t in section:
            score += 2
        elif t in text:
            score += 1
    return score

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
    target_lpages, target_terms = _extract_topup_intent(query)
    by_company: Dict[str, List[Dict[str, Any]]] = {}
    for c in chunks:
        co = c.get("metadata", {}).get("company_code")
        if not co:
            continue
        by_company.setdefault(co, []).append(c)

    present = set(by_company.keys())
    missing = [co for co in expected if co not in present]

    # Companies present in retrieval but without any intent-matching chunk
    # should also be repaired.
    weak_intent = []
    if target_lpages or target_terms:
        for co in expected:
            cchunks = by_company.get(co, [])
            if not cchunks:
                continue
            if target_lpages:
                has_lpage_match = any(
                    any(_lpage_match(str(c.get("metadata", {}).get("page_label", "")), lp) for lp in target_lpages)
                    for c in cchunks
                )
                if not has_lpage_match:
                    weak_intent.append(co)
            elif not any(_intent_score(c, target_lpages, target_terms) > 0 for c in cchunks):
                weak_intent.append(co)

    needs_repair = list(dict.fromkeys(missing + weak_intent))
    if not needs_repair:
        return chunks

    top_up = []

    def _uid(c: Dict[str, Any]) -> str:
        m = c.get("metadata", {})
        return str(m.get("chunk_id") or f"{m.get('company_code','')}::{m.get('page_label','')}::{c.get('text','')[:80]}")

    existing_uids = {_uid(c) for c in chunks}

    for co in needs_repair:
        try:
            scoped_filters = {**(filters or {}), "company_code": co}
            company_chunks = retrieve(query, scoped_filters, 16) or []
            if not company_chunks:
                continue

            targeted: List[Dict[str, Any]] = []
            # Strong repair path: fetch intended L-pages directly (normalized).
            for lp in sorted(target_lpages):
                base_lp = _base_lpage(lp)
                if not base_lp.startswith("L-"):
                    continue
                lp_filters = {**scoped_filters, "page_label_normalized": base_lp}
                hits = retrieve(query, lp_filters, 2) or []
                for h in hits:
                    targeted.append(h)

            # Rank by intent match first, then semantic score.
            ranked = sorted(
                company_chunks,
                key=lambda c: (_intent_score(c, target_lpages, target_terms), float(c.get("score", 0.0))),
                reverse=True,
            )

            selected: List[Dict[str, Any]] = []
            strong_intent = [c for c in ranked if _intent_score(c, target_lpages, target_terms) >= 4]
            target_take = min(
                6,
                max(
                    2,
                    len(target_lpages) * 2 if target_lpages else 2,
                    min(6, len(strong_intent))
                ),
            )
            # Use targeted L-page hits first.
            for c in targeted:
                if _intent_score(c, target_lpages, target_terms) <= 0:
                    continue
                selected.append(c)
                if len(selected) >= target_take:
                    break

            # Then intent-ranked semantic hits.
            if len(selected) < target_take:
                for c in ranked:
                    if _intent_score(c, target_lpages, target_terms) <= 0:
                        continue
                    selected.append(c)
                    if len(selected) >= target_take:
                        break

            if not selected:
                selected = ranked[:1]

            for c in selected:
                uid = _uid(c)
                if uid in existing_uids:
                    continue
                existing_uids.add(uid)
                top_up.append(c)
        except Exception:
            pass
    return chunks + top_up

def get_confidence_level(chunks: List[Dict[str, Any]]) -> str:
    if not chunks: return "none"
    s = chunks[0]["score"]
    return "high" if s >= 0.7 else ("medium" if s >= 0.4 else "none")
