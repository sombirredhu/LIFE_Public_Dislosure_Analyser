import logging
import re
from typing import Any, Dict, List, Optional
import json
from src.config import (
    LLM_MAX_INPUT_CHARS, LLM_MODEL_FREE, LLM_MODEL_PAID,
    TOP_K_COMPLEX, TOP_K_SIMPLE,
)
from src.embedder import get_indexed_companies, get_available_quarters, get_available_fys
from src.llm_client import ask_llm
from src.retriever import get_confidence_level, retrieve, top_up_missing_companies

logger = logging.getLogger(__name__)

_response_cache: Dict[str, Dict[str, Any]] = {}
_MAX_CACHE_SIZE = 100

def _get_cache_key(q: str, f: Optional[Dict[str, Any]], k: Optional[int], fm: Optional[str], pm: Optional[str]) -> str:
    return f"{q}::{json.dumps(f, sort_keys=True) if f else 'N'}::{k}::{fm}::{pm}"

SYSTEM_PROMPT = """You are a financial analyst specializing in Indian life insurance.
Answer based ONLY on excerpts. Rules: 1. Mention company, quarter, FY. 2. Use markdown tables for comparisons. 3. monetary values in ₹ Cr. 4. Cite sources.
"""

_FORMAT_WORDS = re.compile(
    r'\b(in\s+)?'
    r'(table|tabular|summary|bullet|list|detailed|brief|short|chart|graph|paragraph|point|points)\s*'
    r'(format|form|style|way|manner)?\.?\s*',
    re.I
)

def _refine_user_request(question: str, free_model: Optional[str] = None) -> Dict[str, str]:
    format_matches = _FORMAT_WORDS.findall(question)
    format_inst = " ".join(m[1] for m in format_matches).strip() if format_matches else ""
    search_q = _FORMAT_WORDS.sub(' ', question).strip()
    search_q = re.sub(r'\s{2,}', ' ', search_q).strip(' .,?!')
    if not search_q: search_q = question
    if format_inst:
        format_inst = f"Present the answer in {format_inst} format."
    return {"search_query": search_q, "format_instruction": format_inst}

def _extract_auto_filters(q: str) -> Dict[str, Any]:
    f = {}
    ql = q.lower()
    companies = get_indexed_companies()
    found = []
    for c in companies:
        variants = [c.lower(), c.lower().replace('_', ' ')]
        for v in variants:
            pattern = r'(?:^|\b)' + re.escape(v) + r'(?:\b|$)'
            if re.search(pattern, ql): found.append(c); break
    if found: f["company_code"] = found[0] if len(found) == 1 else {"$in": found}
    for q_ in get_available_quarters():
        if re.search(r'\b' + re.escape(q_.lower()) + r'\b', ql): f["quarter"] = q_; break
    for f_ in get_available_fys():
        if re.search(r'\b' + re.escape(f_.lower()) + r'\b', ql): f["fy"] = f_; break
    return f

def _generate_queries(q: str, fm: Optional[str] = None) -> List[str]:
    prompt = f"Generate 3 diverse search queries for finding data in IRDAI financial reports for: '{q}'. Return ONLY a JSON array of strings, nothing else."
    try:
        res = ask_llm("Return only a JSON array.", prompt, use_paid=False, free_model=fm)
        match = re.search(r'\[.*\]', res, re.DOTALL)
        if not match: return [q]
        qs = json.loads(match.group())
        if not isinstance(qs, list) or not all(isinstance(x, str) for x in qs): return [q]
        return list(set([q] + [x.strip() for x in qs if x.strip()]))[:4]
    except Exception:
        logger.warning("[RAG] Multi-query generation failed, using original query")
        return [q]

_COMPLEX_KEYWORDS = re.compile(r'\b(compare|vs\.?|versus|all\s+companies|rank|ranking|which\s+company|across|between)\b', re.I)
_SUPERLATIVE_KEYWORDS = re.compile(r'\b(highest|lowest|top|bottom|best|worst|most|least|trend|growth)\b', re.I)

def classify_complexity(q: str) -> str:
    if _COMPLEX_KEYWORDS.search(q): return "complex"
    cos = get_indexed_companies()
    mentioned = sum(1 for c in cos if c.lower() in q.lower())
    if mentioned > 1: return "complex"
    if _SUPERLATIVE_KEYWORDS.search(q) and mentioned == 0: return "complex"
    return "simple"

def answer_question(question: str, filters: Optional[Dict[str, Any]] = None, top_k: int = None, free_model: Optional[str] = None, paid_model: Optional[str] = None) -> Dict[str, Any]:
    question = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', question.strip())[:2000]
    cache_key = _get_cache_key(question, filters, top_k, free_model, paid_model)
    if cache_key in _response_cache: return _response_cache[cache_key]

    refined = _refine_user_request(question, free_model=free_model)
    search_q, format_inst = refined["search_query"], refined["format_instruction"]

    merged_filters = {**(_extract_auto_filters(search_q)), **(filters or {})}
    complexity = classify_complexity(search_q)
    use_paid = complexity == "complex"
    model_name = (paid_model or LLM_MODEL_PAID) if use_paid else (free_model or LLM_MODEL_FREE)
    effective_top_k = top_k or (TOP_K_COMPLEX if use_paid else TOP_K_SIMPLE)

    queries = _generate_queries(search_q, fm=free_model) if use_paid else [search_q]
    from src.retriever import retrieve_multi
    chunks = retrieve_multi(queries, filters=merged_filters, top_k=effective_top_k)

    if use_paid and (indexed := get_indexed_companies()):
        chunks = top_up_missing_companies(search_q, chunks, indexed, merged_filters)

    if not chunks: return {"answer": "No relevant info found.", "sources": [], "chunks_used": 0, "confidence": "none", "model_used": LLM_MODEL_FREE}

    total_chars = sum(len(c["text"]) for c in chunks)
    if total_chars > LLM_MAX_INPUT_CHARS:
        avg = max(total_chars // len(chunks), 1)
        chunks = chunks[:LLM_MAX_INPUT_CHARS // avg]

    ctx = "\n\n---\n\n".join([f"Source: {c['metadata']['source_file']} | Company: {c['metadata']['company']} | Period: {c['metadata']['period_label']} | Section: {c['metadata']['section']}\n\n{c['text']}" for c in chunks])
    fmt = f"\nFormat Instruction: {format_inst}" if format_inst else ""
    answer = ask_llm(SYSTEM_PROMPT, f"Question: {question}{fmt}\n\nExcerpts:\n{ctx}", use_paid=use_paid, free_model=free_model, paid_model=paid_model)

    res = {"answer": answer, "sources": sorted(set(c["metadata"]["source_file"] for c in chunks)), "chunks_used": len(chunks), "confidence": get_confidence_level(chunks), "model_used": model_name}
    _response_cache[cache_key] = res
    if len(_response_cache) > _MAX_CACHE_SIZE: _response_cache.pop(next(iter(_response_cache)))
    return res
