"""
RAG Pipeline - orchestrates retrieval and LLM to answer questions.
Implements two-tier model routing based on query complexity.
"""

import logging
import re
from typing import Any, Dict, List, Optional

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

SYSTEM_PROMPT = """You are a financial analyst specializing in Indian life insurance industry data.
You have access to IRDAI Public Disclosure reports from multiple life insurance companies across multiple quarters.

Your job is to answer questions accurately based ONLY on the provided report excerpts. Do not make up numbers or use outside knowledge for specific figures.

Rules:
1. Always mention the company name, quarter, and FY when quoting a number
2. If comparing companies, present results as a ranked table in markdown format
3. All monetary values are in Indian Rupees Crore (₹ Cr) unless stated otherwise
4. If data is not available in the provided excerpts, say so clearly
5. For ranking questions, rank all companies for which data is available
6. Always cite the source PDF filename at the end of your answer
7. Use markdown tables for comparisons and rankings
8. Be concise but complete - include all relevant numbers

Response format:
- For single company questions: direct answer with number + source
- For comparison/ranking questions: markdown table with all companies
- For trend questions: show quarter-wise data in a table
"""

# Keywords that force COMPLEX regardless of company name
_ALWAYS_COMPLEX = re.compile(
    r'\b(compare|vs\.?|versus|all companies|all quarters|industry total|'
    r'channel[\s-]wise|rank(?:ing)?|which company)\b',
    re.IGNORECASE,
)

# Keywords that make a query COMPLEX only when no single company is named
_COMPLEX_IF_NO_COMPANY = re.compile(
    r'\b(highest|lowest|top|bottom|best|worst|most|least|trend)\b',
    re.IGNORECASE,
)


def classify_complexity(question: str) -> str:
    """
    Classify query complexity as "simple" or "complex".
    Pure keyword/heuristic — no LLM call, runs before retrieval.

    Rules:
      ALWAYS COMPLEX: compare / vs / rank / which company / industry total / channel-wise
      COMPLEX if no single company named: highest / lowest / top / trend / etc.
      SIMPLE: exactly one company named AND none of the always-complex keywords present
      Default when in doubt: COMPLEX (wrong answer costs more than extra retrieval)
    """
    if _ALWAYS_COMPLEX.search(question):
        return "complex"

    # Count company-like tokens: must start with 2+ UPPERCASE letters (e.g. HDFC, LIC, SBI)
    # optionally followed by title-case words (e.g. "HDFC Life", "ICICI Pru").
    # This deliberately excludes ordinary English words like "What", "How", "Which"
    # and quarter/FY labels like "Q1", "FY25" (they lack a word boundary after 2+ caps).
    company_like = re.findall(r'\b[A-Z]{2,}(?:\s[A-Z][a-z]+)*\b', question)
    single_company_named = len(company_like) == 1

    if _COMPLEX_IF_NO_COMPANY.search(question) and not single_company_named:
        return "complex"

    if single_company_named:
        return "simple"

    return "complex"


def _build_context(chunks: List[Dict[str, Any]]) -> str:
    parts = []
    for chunk in chunks:
        m = chunk["metadata"]
        parts.append(
            f"Source: {m['source_file']} | Company: {m['company']} | "
            f"Period: {m['period_label']} | Page: {m['page_number']} | "
            f"Section: {m['section']}\n\n{chunk['text']}"
        )
    return "\n\n---\n\n".join(parts)


def _build_user_message(question: str, chunks: List[Dict[str, Any]]) -> str:
    context = _build_context(chunks)
    return (
        f"Answer this question using the report excerpts below:\n\n"
        f"Question: {question}\n\n"
        f"Report Excerpts:\n{context}"
    )


def answer_question(
    question: str,
    filters: Optional[Dict[str, Any]] = None,
    top_k: int = None,
    free_model: Optional[str] = None,
    paid_model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Answer a question using the full RAG pipeline.

    Returns dict with keys:
        answer, sources, chunks_used, confidence, model_used
    """
    complexity = classify_complexity(question)
    use_paid = complexity == "complex"
    model_name = (paid_model or LLM_MODEL_PAID) if use_paid else (free_model or LLM_MODEL_FREE)

    logger.info(
        "[RAG] Question: %r | Complexity: %s | Model: %s | Filters: %s",
        question[:100], complexity, model_name, filters,
    )

    # Step 1: Retrieve
    effective_top_k = top_k if top_k is not None else (TOP_K_COMPLEX if use_paid else TOP_K_SIMPLE)
    chunks = retrieve(question, filters=filters, top_k=effective_top_k)
    logger.info("[RAG] Step 1 — Retrieved %d chunks (top_k=%d)", len(chunks), effective_top_k)

    # Step 2: Top-up for complex queries
    if use_paid and not filters:
        indexed = get_indexed_companies()
        if indexed:
            before = len(chunks)
            chunks = top_up_missing_companies(question, chunks, indexed, filters)
            logger.info(
                "[RAG] Step 2 — Top-up: %d → %d chunks (indexed companies: %s)",
                before, len(chunks), indexed,
            )
        else:
            logger.info("[RAG] Step 2 — Top-up skipped (no indexed companies)")
    else:
        logger.info("[RAG] Step 2 — Top-up skipped (simple query or filter active)")

    if not chunks:
        logger.warning("[RAG] No chunks found — returning empty answer | question=%r", question[:100])
        return {
            "answer":      "I couldn't find any relevant information in the indexed reports. "
                           "Please ensure the relevant PDF files have been uploaded and indexed.",
            "sources":     [],
            "chunks_used": 0,
            "confidence":  "none",
            "model_used":  LLM_MODEL_FREE,
        }

    # Step 3: Input token budget guard
    total_chars = sum(len(c["text"]) for c in chunks)
    if total_chars > LLM_MAX_INPUT_CHARS:
        avg_chunk_size = total_chars // len(chunks)
        max_chunks = LLM_MAX_INPUT_CHARS // avg_chunk_size
        logger.warning(
            "[RAG] Step 3 — Input truncated: %d chars > %d limit. Keeping %d/%d chunks.",
            total_chars, LLM_MAX_INPUT_CHARS, max_chunks, len(chunks),
        )
        chunks = chunks[:max_chunks]
    else:
        logger.info("[RAG] Step 3 — Input chars: %d (within %d limit)", total_chars, LLM_MAX_INPUT_CHARS)

    # Step 4: Build prompt and call LLM
    user_message = _build_user_message(question, chunks)
    confidence = get_confidence_level(chunks)
    logger.info("[RAG] Step 4 — Calling LLM | chunks=%d | confidence=%s", len(chunks), confidence)
    answer = ask_llm(SYSTEM_PROMPT, user_message, use_paid=use_paid,
                     free_model=free_model, paid_model=paid_model)
    sources = sorted(set(c["metadata"]["source_file"] for c in chunks))
    logger.info("[RAG] Done | sources=%s", sources)

    return {
        "answer":      answer,
        "sources":     sources,
        "chunks_used": len(chunks),
        "confidence":  confidence,
        "model_used":  model_name,
    }


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    question = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Which company had the highest gross written premium?"
    print(f"Question: {question}")
    print(f"Complexity: {classify_complexity(question)}\n")
    print("Retrieving and generating answer...\n")

    try:
        result = answer_question(question)

        print("=" * 80)
        print("ANSWER")
        print("=" * 80)
        print(result["answer"])
        print()
        print("=" * 80)
        print("METADATA")
        print("=" * 80)
        print(f"Confidence:  {result['confidence']}")
        print(f"Chunks Used: {result['chunks_used']}")
        print(f"Model Used:  {result['model_used']}")
        print(f"Sources:     {', '.join(result['sources'])}")

    except ValueError as e:
        print(f"✗ Configuration error: {e}")
        print("\nPlease ensure:")
        print("1. .env file exists with OPENROUTER_API_KEY")
        print("2. PDF files have been ingested into ChromaDB")
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
