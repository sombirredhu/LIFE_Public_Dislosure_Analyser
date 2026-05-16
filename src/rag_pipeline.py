import logging
import re
from typing import Any, Dict, List, Optional
import json
from src.config import (
    LLM_MAX_INPUT_CHARS,
    LLM_MODEL_FREE,
    LLM_MODEL_PAID,
    TOP_K_COMPLEX,
    TOP_K_SIMPLE,
)
from src.embedder import get_indexed_companies
from src.llm_client import ask_llm
from src.retriever import get_confidence_level, retrieve, top_up_missing_companies

logger = logging.getLogger(__name__)

_response_cache: Dict[str, Dict[str, Any]] = {}
_MAX_CACHE_SIZE = 100

def _get_cache_key(question: str, filters: Optional[Dict[str, Any]], top_k: Optional[int], free_model: Optional[str] = None, paid_model: Optional[str] = None) -> str:
    filters_str = json.dumps(filters, sort_keys=True) if filters else "None"
    return f"{question}::{filters_str}::{top_k}::{free_model}::{paid_model}"

SYSTEM_PROMPT = """You are a financial analyst specializing in Indian life insurance industry data.
You have access to IRDAI Public Disclosure reports.
Answer based ONLY on provided excerpts.
Rules: 1. Mention company, quarter, FY. 2. Use markdown tables for comparisons. 3. monetary values in ₹ Cr. 4. Cite source PDF filenames.
"""

_ALWAYS_COMPLEX = re.compile(r'\b(compare|vs\.?|versus|all companies|all quarters|industry total|channel[\s-]wise|rank(?:ing)?|which company)\b', re.IGNORECASE)
_COMPLEX_IF_NO_COMPANY = re.compile(r'\b(highest|lowest|top|bottom|best|worst|most|least|trend)\b', re.IGNORECASE)

def classify_complexity(question: str) -> str:
    if _ALWAYS_COMPLEX.search(question): return "complex"
    company_like = re.findall(r'\b[A-Z]{2,}(?:\s[A-Z][a-z]+)*\b', question)
    single_company_named = len(company_like) == 1
    if _COMPLEX_IF_NO_COMPANY.search(question) and not single_company_named: return "complex"
    return "simple" if single_company_named else "complex"

def _build_context(chunks: List[Dict[str, Any]]) -> str:
    return "\n\n---\n\n".join([f"Source: {c['metadata']['source_file']} | Company: {c['metadata']['company']} | Period: {c['metadata']['period_label']} | Page: {c['metadata']['page_number']} | Section: {c['metadata']['section']}\n\n{c['text']}" for c in chunks])

def _build_user_message(question: str, chunks: List[Dict[str, Any]]) -> str:
    return f"Answer this question using the report excerpts below:\n\nQuestion: {question}\n\nReport Excerpts:\n{_build_context(chunks)}"

def answer_question(question: str, filters: Optional[Dict[str, Any]] = None, top_k: int = None, free_model: Optional[str] = None, paid_model: Optional[str] = None) -> Dict[str, Any]:
    _MAX_QUERY_LEN = 2000
    question = question.strip()
    if len(question) > _MAX_QUERY_LEN:
        question = question[:_MAX_QUERY_LEN]
        logger.warning("[RAG] Query truncated")
    question = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', question)
    cache_key = _get_cache_key(question, filters, top_k, free_model, paid_model)
    if cache_key in _response_cache: return _response_cache[cache_key]
    complexity = classify_complexity(question)
    use_paid = complexity == "complex"
    model_name = (paid_model or LLM_MODEL_PAID) if use_paid else (free_model or LLM_MODEL_FREE)
    effective_top_k = top_k if top_k is not None else (TOP_K_COMPLEX if use_paid else TOP_K_SIMPLE)
    chunks = retrieve(question, filters=filters, top_k=effective_top_k)
    if use_paid:
        indexed = get_indexed_companies()
        if indexed: chunks = top_up_missing_companies(question, chunks, indexed, filters)
    if not chunks:
        return {"answer": "I couldn't find any relevant information.", "sources": [], "chunks_used": 0, "confidence": "none", "model_used": LLM_MODEL_FREE}
    total_chars = sum(len(c["text"]) for c in chunks)
    if total_chars > LLM_MAX_INPUT_CHARS:
        max_chunks = LLM_MAX_INPUT_CHARS // (total_chars // len(chunks))
        chunks = chunks[:max_chunks]
    answer = ask_llm(SYSTEM_PROMPT, _build_user_message(question, chunks), use_paid=use_paid, free_model=free_model, paid_model=paid_model)
    result = {"answer": answer, "sources": sorted(set(c["metadata"]["source_file"] for c in chunks)), "chunks_used": len(chunks), "confidence": get_confidence_level(chunks), "model_used": model_name}
    _response_cache[cache_key] = result
    if len(_response_cache) > _MAX_CACHE_SIZE: _response_cache.pop(next(iter(_response_cache)))
    return result
