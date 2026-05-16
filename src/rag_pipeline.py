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

def _refine_user_request(question: str, free_model: Optional[str] = None) -> Dict[str, str]:
    prompt = f"Analyze: '{question}'. Return JSON with: 1. 'search_query' (clean intent for DB), 2. 'format_instruction' (styling like 'table', 'summary')."
    try:
        res = ask_llm("You are a query translator. Return only JSON.", prompt, use_paid=False, free_model=free_model)
        return json.loads(re.search(r'\{.*\}', res, re.DOTALL).group())
    except Exception: return {"search_query": question, "format_instruction": ""}

def _extract_auto_filters(q: str) -> Dict[str, Any]:
    f = {}
    companies = get_indexed_companies()
    found_cos = [c for c in companies if c.lower().replace('_', ' ') in q.lower() or c.lower() in q.lower()]
    if found_cos: f["company_code"] = found_cos[0] if len(found_cos) == 1 else {"$in": found_cos}
    qs, fys = get_available_quarters(), get_available_fys()
    f_qs = [q_ for q_ in qs if q_.lower() in q.lower()]
    if f_qs: f["quarter"] = f_qs[0]
    f_fys = [f_ for f_ in fys if f_.lower() in q.lower()]
    if f_fys: f["fy"] = f_fys[0]
    return f

def _generate_queries(q: str, fm: Optional[str] = None) -> List[str]:
    prompt = f"Generate 3 diverse search queries for: '{q}'. Return JSON list of strings."
    try:
        res = ask_llm("Return only JSON.", prompt, use_paid=False, free_model=fm)
        qs = json.loads(re.search(r'\[.*\]', res, re.DOTALL).group())
        return list(set([q] + qs))
    except Exception: return [q]

def classify_complexity(q: str) -> str:
    if re.search(r'\b(compare|vs\.?|versus|all companies|rank)\b', q, re.I): return "complex"
    return "simple" if len(re.findall(r'\b[A-Z]{2,}\b', q)) == 1 else "complex"

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
    if total_chars > LLM_MAX_INPUT_CHARS: chunks = chunks[:LLM_MAX_INPUT_CHARS // (total_chars // len(chunks))]
    
    context = "\n\n---\n\n".join([f"Source: {c['metadata']['source_file']} | Company: {c['metadata']['company']} | Period: {c['metadata']['period_label']} | Section: {c['metadata']['section']}\n\n{c['text']}" for c in chunks])
    final_prompt = f"Question: {question}\nFormat Instruction: {format_inst}\n\nExcerpts:\n{context}"
    answer = ask_llm(SYSTEM_PROMPT, final_prompt, use_paid=use_paid, free_model=free_model, paid_model=paid_model)
    
    res = {"answer": answer, "sources": sorted(set(c["metadata"]["source_file"] for c in chunks)), "chunks_used": len(chunks), "confidence": get_confidence_level(chunks), "model_used": model_name}
    _response_cache[cache_key] = res
    if len(_response_cache) > _MAX_CACHE_SIZE: _response_cache.pop(next(iter(_response_cache)))
    return res
