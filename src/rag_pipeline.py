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

def _get_cache_key(question: str, filters: Optional[Dict[str, Any]], top_k: Optional[int], free_model: Optional[str] = None, paid_model: Optional[str] = None) -> str:
    filters_str = json.dumps(filters, sort_keys=True) if filters else "None"
    return f"{question}::{filters_str}::{top_k}::{free_model}::{paid_model}"

SYSTEM_PROMPT = """You are a financial analyst specializing in Indian life insurance.
Answer based ONLY on provided excerpts. Rules: 1. Mention company, quarter, FY. 2. Use markdown tables for comparisons. 3. monetary values in ₹ Cr. 4. Cite sources.
"""

def _extract_auto_filters(question: str) -> Dict[str, Any]:
    filters = {}
    companies = get_indexed_companies()
    found_cos = [c for c in companies if c.lower().replace('_', ' ') in question.lower() or c.lower() in question.lower()]
    if found_cos: filters["company_code"] = found_cos[0] if len(found_cos) == 1 else {"$in": found_cos}
    qs = get_available_quarters()
    found_qs = [q for q in qs if q.lower() in question.lower()]
    if found_qs: filters["quarter"] = found_qs[0]
    fys = get_available_fys()
    found_fys = [f for f in fys if f.lower() in question.lower()]
    if found_fys: filters["fy"] = found_fys[0]
    return filters

def _generate_queries(question: str, free_model: Optional[str] = None) -> List[str]:
    prompt = f"Generate 3 diverse search queries to find data for this question in financial reports: '{question}'. Return only a JSON list of strings."
    try:
        res = ask_llm("You are a search expert. Return only JSON.", prompt, use_paid=False, free_model=free_model)
        queries = json.loads(re.search(r'\[.*\]', res, re.DOTALL).group())
        return list(set([question] + queries))
    except Exception: return [question]

def classify_complexity(question: str) -> str:
    if re.search(r'\b(compare|vs\.?|versus|all companies|rank|which company)\b', question, re.I): return "complex"
    cos = re.findall(r'\b[A-Z]{2,}(?:\s[A-Z][a-z]+)*\b', question)
    if re.search(r'\b(highest|lowest|top|trend)\b', question, re.I) and len(cos) != 1: return "complex"
    return "simple" if len(cos) == 1 else "complex"

def answer_question(question: str, filters: Optional[Dict[str, Any]] = None, top_k: int = None, free_model: Optional[str] = None, paid_model: Optional[str] = None) -> Dict[str, Any]:
    question = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', question.strip())[:2000]
    cache_key = _get_cache_key(question, filters, top_k, free_model, paid_model)
    if cache_key in _response_cache: return _response_cache[cache_key]
    
    auto_filters = _extract_auto_filters(question)
    merged_filters = {**(auto_filters), **(filters or {})}
    
    complexity = classify_complexity(question)
    use_paid = complexity == "complex"
    model_name = (paid_model or LLM_MODEL_PAID) if use_paid else (free_model or LLM_MODEL_FREE)
    effective_top_k = top_k or (TOP_K_COMPLEX if use_paid else TOP_K_SIMPLE)
    
    queries = _generate_queries(question, free_model=free_model) if use_paid else [question]
    from src.retriever import retrieve_multi
    chunks = retrieve_multi(queries, filters=merged_filters, top_k=effective_top_k)
    
    if use_paid:
        indexed = get_indexed_companies()
        if indexed: chunks = top_up_missing_companies(question, chunks, indexed, merged_filters)
    
    if not chunks: return {"answer": "No relevant info found.", "sources": [], "chunks_used": 0, "confidence": "none", "model_used": LLM_MODEL_FREE}
    
    total_chars = sum(len(c["text"]) for c in chunks)
    if total_chars > LLM_MAX_INPUT_CHARS: chunks = chunks[:LLM_MAX_INPUT_CHARS // (total_chars // len(chunks))]
    
    answer = ask_llm(SYSTEM_PROMPT, f"Question: {question}\n\nExcerpts:\n" + "\n\n---\n\n".join([f"Source: {c['metadata']['source_file']} | Company: {c['metadata']['company']} | Period: {c['metadata']['period_label']} | Section: {c['metadata']['section']}\n\n{c['text']}" for c in chunks]), use_paid=use_paid, free_model=free_model, paid_model=paid_model)
    
    res = {"answer": answer, "sources": sorted(set(c["metadata"]["source_file"] for c in chunks)), "chunks_used": len(chunks), "confidence": get_confidence_level(chunks), "model_used": model_name}
    _response_cache[cache_key] = res
    if len(_response_cache) > _MAX_CACHE_SIZE: _response_cache.pop(next(iter(_response_cache)))
    return res
