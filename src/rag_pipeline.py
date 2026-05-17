import logging
import re
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set
import json
from src.config import (
    LLM_MAX_INPUT_CHARS, LLM_MODEL_FREE, LLM_MODEL_PAID,
    TOP_K_COMPLEX, TOP_K_SIMPLE, ENABLE_MULTI_QUERY, PROCESSED_OUTPUT_DIR,
)
from src.embedder import get_indexed_companies, get_available_quarters, get_available_fys
from src.llm_client import ask_llm
from src.retriever import get_confidence_level, retrieve, top_up_missing_companies
from src.rag.types import QueryPlan

logger = logging.getLogger(__name__)

_response_cache: Dict[str, Dict[str, Any]] = {}
_MAX_CACHE_SIZE = 100

# Optimizer-level cache: avoids repeated LLM calls for similar complex queries
_optimizer_cache: Dict[str, Dict[str, Any]] = {}
_MAX_OPTIMIZER_CACHE = 64

def _get_optimizer_cache_key(question: str) -> str:
    """Normalize question for optimizer cache: lowercase, strip format words, collapse whitespace."""
    normalized = _FORMAT_WORDS.sub(' ', question.lower()).strip()
    normalized = re.sub(r'\s{2,}', ' ', normalized).strip(' .,?!')
    return normalized

def _get_cache_key(q: str, f: Optional[Dict[str, Any]], k: Optional[int], fm: Optional[str], pm: Optional[str]) -> str:
    # Include callable identities so tests/monkeypatching don't leak stale cached responses
    # across different patched pipelines, while preserving normal runtime cache behavior.
    runtime_salt = f"{id(retrieve)}:{id(ask_llm)}"
    return f"{q}::{json.dumps(f, sort_keys=True) if f else 'N'}::{k}::{fm}::{pm}::{runtime_salt}"

SYSTEM_PROMPT = """You are a financial analyst specializing in Indian life insurance.
Answer based ONLY on excerpts. Rules: 1. Mention company, quarter, FY. 2. Use markdown tables for comparisons. 3. monetary values in ₹ Cr. 4. Cite sources with company + L-page when available.
"""

_FORMAT_WORDS = re.compile(
    r'\b(in\s+)?'
    r'(table|tabular|summary|bullet|list|detailed|brief|short|chart|graph|paragraph|point|points)\s*'
    r'(format|form|style|way|manner)?\.?\s*',
    re.I
)
_SEARCH_NOISE_WORDS = re.compile(
    r'\b(compare|comparison|show|list|rank|ranking|across|between|for|all|companies|company[-\s]*wise|each|metric|metrics|cite|sources?|with|and|the|of|to|page|pages|l-page)\b',
    re.I,
)
_LPAGE_TOKEN_RE = re.compile(r'\bL-\d+[A-Z]?(?:-[A-Z]-[A-Z]{2})?\b', re.I)
_TERM_LPAGE_CACHE: Dict[str, List[str]] = {}
_RETRIEVAL_STOPWORDS = {
    "query", "this", "that", "from", "into", "with", "without", "using",
    "about", "what", "which", "where", "when", "who", "whom",
    "month", "months", "quarter", "year", "quarters", "years",
    "highest", "lowest", "top", "bottom", "best", "worst",
    "value", "values", "reference", "references", "ranking", "rank",
    "company", "companies", "wise", "across", "between",
}
_GENERIC_METRIC_WORDS = {
    "ratio", "schedule", "account", "statement", "data", "business",
    "investment", "investments", "page", "pages", "quarterly", "annual",
    "total", "aggregate", "details",
}

def _contains_term(query_text: str, term: str) -> bool:
    t = (term or "").strip().lower()
    if len(t) < 2:
        return False
    return re.search(rf'(?<!\w){re.escape(t)}(?!\w)', query_text.lower()) is not None

def _estimate_text_tokens(text: str) -> int:
    """
    Token estimate for budgeting during retrieval/LLM context packing.
    Uses a conservative lexical heuristic (better than plain chars/4 for mixed table text).
    """
    if not text:
        return 0
    lexical = re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)
    approx = int(len(lexical) * 1.05)  # small safety margin
    char_floor = len(text) // 5
    return max(approx, char_floor)

def _load_term_to_page_map() -> Dict[str, str]:
    try:
        from pathlib import Path
        term_path = Path(PROCESSED_OUTPUT_DIR) / "master_term_to_page.json"
        if term_path.exists():
            with open(term_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
    except Exception:
        logger.exception("[RAG] Failed to load master_term_to_page.json")
    return {}

def _load_page_definitions_map() -> Dict[str, List[str]]:
    try:
        from pathlib import Path
        defs_path = Path(PROCESSED_OUTPUT_DIR) / "master_page_definitions.json"
        if defs_path.exists():
            with open(defs_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    out: Dict[str, List[str]] = {}
                    for lpage, terms in data.items():
                        if isinstance(terms, list):
                            out[lpage.upper()] = [str(t).lower() for t in terms]
                        else:
                            out[lpage.upper()] = [str(terms).lower()]
                    return out
    except Exception:
        logger.exception("[RAG] Failed to load master_page_definitions.json")
    return {}

def _infer_lpages_from_processed_docs(query_terms: List[str], top_n: int = 1) -> Dict[str, List[str]]:
    """
    Infer likely L-pages for query terms from processed document content.
    This is data-driven and avoids hardcoded term-to-page mappings.
    """
    try:
        from pathlib import Path
        processed_dir = Path(PROCESSED_OUTPUT_DIR)
        doc_files = list(processed_dir.glob("*_Q*_FY*.json"))
        if not doc_files:
            return {}

        result: Dict[str, List[str]] = {}
        term_counts: Dict[str, Dict[str, int]] = {t: {} for t in query_terms}
        for doc in doc_files:
            try:
                with open(doc, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue

            for page in data.get("pages", []):
                lpage = (page.get("page_label_normalized") or page.get("page_label") or "").upper()
                if not lpage.startswith("L-"):
                    continue
                text_parts = []
                text_parts.extend(page.get("text_blocks", []))
                for tbl in page.get("tables", []):
                    raw = tbl.get("raw_text")
                    if raw:
                        text_parts.append(raw)
                page_text = "\n".join(text_parts).lower()
                if not page_text:
                    continue

                for term in query_terms:
                    if term in page_text:
                        term_counts[term][lpage] = term_counts[term].get(lpage, 0) + 1

        for term, counts in term_counts.items():
            ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
            if not ranked:
                _TERM_LPAGE_CACHE[term] = []
                result[term] = []
                continue
            top_count = ranked[0][1]
            strong = [lp for lp, c in ranked if c >= max(2, int(top_count * 0.6))]
            _TERM_LPAGE_CACHE[term] = strong[:top_n]
            result[term] = _TERM_LPAGE_CACHE[term]
        return result
    except Exception:
        logger.exception("[RAG] Failed to infer L-pages from processed docs")
        return {}

def _unique_terms(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for item in items:
        key = item.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item.strip())
    return out

def _extract_period_tokens(text: str) -> List[str]:
    tokens: List[str] = []
    q_match = re.findall(r'\bQ[1-4]\b', text, flags=re.I)
    fy_match = re.findall(r'\bFY\d{2}\b', text, flags=re.I)
    tokens.extend([q.upper() for q in q_match])
    tokens.extend([fy.upper() for fy in fy_match])
    return _unique_terms(tokens)

def _extract_query_terms_for_relevance(text: str) -> List[str]:
    cleaned = _SEARCH_NOISE_WORDS.sub(" ", text.lower())
    words = re.findall(r'\b[a-z]{3,}\b', cleaned)
    return _unique_terms([w for w in words if w not in _RETRIEVAL_STOPWORDS])

def _candidate_lpages_from_terms(terms: List[str], query_text: str) -> Set[str]:
    explicit_lpages = [lp.upper() for lp in _LPAGE_TOKEN_RE.findall(query_text)]
    target_lpages: Set[str] = set(explicit_lpages)
    if not terms:
        return target_lpages

    query_lower = query_text.lower()
    query_words = set(terms)
    page_scores: Dict[str, int] = {}

    # Strong signal: exact (boundary-aware) term map match
    term_to_page = _load_term_to_page_map()
    for term, lp in term_to_page.items():
        term_l = str(term).lower().strip()
        if len(term_l) < 3:
            continue
        if _contains_term(query_lower, term_l):
            lpage = str(lp).upper()
            page_scores[lpage] = page_scores.get(lpage, 0) + 5

    # Medium signal: definition overlap / phrase match
    defs_map = _load_page_definitions_map()
    for lpage, defs_terms in defs_map.items():
        best_score = 0
        for dt in defs_terms:
            dt_l = str(dt).lower().strip()
            if not dt_l:
                continue
            dt_words = {
                w for w in re.findall(r'\b[a-z]{3,}\b', dt_l)
                if w not in _RETRIEVAL_STOPWORDS and w not in _GENERIC_METRIC_WORDS
            }
            overlap = query_words & dt_words
            phrase_hit = len(dt_l) >= 5 and _contains_term(query_lower, dt_l)
            local_score = (4 if phrase_hit else 0) + len(overlap)
            if local_score > best_score:
                best_score = local_score
        if best_score >= 2:
            page_scores[lpage.upper()] = max(page_scores.get(lpage.upper(), 0), best_score)

    metric_terms = [t for t in terms if t not in _GENERIC_METRIC_WORDS]
    max_pages = min(12, max(3, len(metric_terms) * 2))

    ranked_pages = sorted(page_scores.items(), key=lambda kv: kv[1], reverse=True)
    for lpage, _ in ranked_pages:
        target_lpages.add(lpage)
        if len(target_lpages) >= max_pages:
            break

    return target_lpages

def _score_chunk_relevance(chunk: Dict[str, Any], terms: List[str], target_lpages: Set[str]) -> int:
    meta = chunk.get("metadata", {})
    text = (chunk.get("text") or "").lower()
    section = str(meta.get("section", "")).lower()
    lpage = str(meta.get("page_label", "")).upper()
    score = 0

    if lpage and any(lpage == t or lpage.startswith(f"{t}-") or t.startswith(f"{lpage}-") for t in target_lpages):
        score += 3

    hits = 0
    for t in terms:
        if t in text:
            hits += 1
        elif t in section:
            hits += 1
        if hits >= 3:
            break
    score += hits

    # Boost high-similarity chunks slightly.
    sim = float(chunk.get("score", 0.0))
    if sim >= 0.75:
        score += 1
    return score

def _prune_and_balance_chunks(
    question: str,
    search_q: str,
    chunks: List[Dict[str, Any]],
    top_k: int,
    filters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Reduce retrieval noise by keeping chunks aligned to intent terms/L-pages, then
    balancing by company so broad comparisons don't over-return irrelevant pages.
    """
    if not chunks:
        return chunks

    terms = _extract_query_terms_for_relevance(f"{question} {search_q}")
    target_lpages = _candidate_lpages_from_terms(terms, f"{question} {search_q}")

    scored = []
    for c in chunks:
        rel = _score_chunk_relevance(c, terms, target_lpages)
        item = dict(c)
        item["_rel"] = rel
        scored.append(item)

    # If at least one chunk matches intent, drop obvious noise.
    if any(s["_rel"] > 0 for s in scored):
        scored = [s for s in scored if s["_rel"] > 0]

    scored.sort(key=lambda x: (x["_rel"], x.get("score", 0.0)), reverse=True)

    by_company: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for s in scored:
        co = s.get("metadata", {}).get("company_code", "__unknown__")
        by_company[co].append(s)

    metric_count = len(set(terms))
    lpage_intent_count = len(target_lpages)

    # Dynamic cap: allow deeper coverage for multi-metric comparisons.
    # Single metric: ~2/company; 2 metrics: ~4/company; 3+ metrics: ~5/company.
    if lpage_intent_count >= 3 or metric_count >= 9:
        per_company_cap = 5
    elif lpage_intent_count == 2 or metric_count >= 6:
        per_company_cap = 4
    else:
        per_company_cap = 2

    # If user selected specific company/company set, skip aggressive balancing.
    if filters and "company_code" in filters:
        per_company_cap = min(max(per_company_cap, 3), top_k)
    elif len(by_company) <= 1:
        # Single-company queries should not be aggressively capped; keep ranking depth.
        per_company_cap = top_k

    selected: List[Dict[str, Any]] = []
    selected_ids: Set[str] = set()

    def _chunk_uid(c: Dict[str, Any]) -> str:
        meta = c.get("metadata", {})
        return str(meta.get("chunk_id") or f"{meta.get('source_file','')}::{meta.get('page_number','')}::{c.get('text','')[:80]}")

    def _lpage_match(page_label: str, target: str) -> bool:
        p = (page_label or "").upper()
        t = (target or "").upper()
        return p == t or p.startswith(f"{t}-") or t.startswith(f"{p}-")

    # First pass per company: one best chunk per detected L-page intent.
    for company_chunks in by_company.values():
        company_selected: List[Dict[str, Any]] = []
        if target_lpages:
            for tlp in sorted(target_lpages):
                match = next(
                    (
                        c for c in company_chunks
                        if _lpage_match(str(c.get("metadata", {}).get("page_label", "")), tlp)
                        and _chunk_uid(c) not in selected_ids
                    ),
                    None,
                )
                if match:
                    uid = _chunk_uid(match)
                    selected_ids.add(uid)
                    company_selected.append(match)
                if len(company_selected) >= per_company_cap:
                    break

        # Always ensure at least one chunk/company.
        if not company_selected and company_chunks:
            best = company_chunks[0]
            uid = _chunk_uid(best)
            if uid not in selected_ids:
                selected_ids.add(uid)
                company_selected.append(best)

        # Second pass for this company: fill remaining top-ranked chunks to cap.
        if len(company_selected) < per_company_cap:
            for c in company_chunks:
                uid = _chunk_uid(c)
                if uid in selected_ids:
                    continue
                selected_ids.add(uid)
                company_selected.append(c)
                if len(company_selected) >= per_company_cap:
                    break

        selected.extend(company_selected)

    # Global hard cap tuned to "intent-coverage per company" for broad compare.
    if by_company:
        dynamic_cap = min(top_k, max(len(by_company) * per_company_cap, len(by_company)))
        selected = selected[:dynamic_cap]

    # Cleanup helper field
    for s in selected:
        s.pop("_rel", None)

    return selected if selected else chunks[:top_k]

def _compact_vector_query(text: str) -> str:
    """
    Build compact vector query with only retrieval-relevant keywords:
    period + L-page + metric terms.
    """
    q_lower = text.lower()

    def _norm_words(s: str) -> set:
        ws = re.findall(r'\b[a-z]{3,}\b', s.lower())
        out = set()
        for w in ws:
            if w.endswith("s") and len(w) > 4:
                w = w[:-1]
            out.add(w)
        return out

    tokens: List[str] = []
    explicit_lpages = [lp.upper() for lp in _LPAGE_TOKEN_RE.findall(text)]
    tokens.extend(_extract_period_tokens(text))
    tokens.extend(explicit_lpages)

    query_words = _norm_words(_SEARCH_NOISE_WORDS.sub(" ", q_lower))
    query_words = {w for w in query_words if w not in _RETRIEVAL_STOPWORDS}

    page_scores: Dict[str, int] = {}
    anchor_terms: Set[str] = set()

    # Exact term mapping from index-derived term map (boundary-aware)
    term_to_page = _load_term_to_page_map()
    for term, lpage in term_to_page.items():
        term_l = str(term).lower().strip()
        if len(term_l) < 3:
            continue
        if _contains_term(q_lower, term_l):
            lp = str(lpage).upper()
            page_scores[lp] = page_scores.get(lp, 0) + 5
            anchor_terms.add(term_l)

    # Fuzzy mapping using index-derived page definitions (strict overlap)
    defs_map = _load_page_definitions_map()
    matched_words_from_defs: Set[str] = set()
    for lpage, terms in defs_map.items():
        best_term = ""
        best_score = 0
        best_overlap_words: Set[str] = set()
        for term in terms:
            term_l = str(term).lower().strip()
            if not term_l:
                continue
            term_words = {
                w for w in _norm_words(term_l)
                if w not in _RETRIEVAL_STOPWORDS and w not in _GENERIC_METRIC_WORDS
            }
            overlap_words = query_words & term_words
            phrase_hit = len(term_l) >= 5 and _contains_term(q_lower, term_l)
            score = (4 if phrase_hit else 0) + len(overlap_words)
            if score > best_score:
                best_score = score
                best_term = term_l
                best_overlap_words = overlap_words

        if best_score >= 2:
            lp = str(lpage).upper()
            page_scores[lp] = max(page_scores.get(lp, 0), best_score)
            if best_term:
                anchor_terms.add(best_term)
            matched_words_from_defs.update(best_overlap_words)

    metric_terms = [w for w in query_words if w not in _GENERIC_METRIC_WORDS]
    max_pages = min(12, max(3, len(metric_terms) * 2))

    for lp, _score in sorted(page_scores.items(), key=lambda kv: kv[1], reverse=True):
        tokens.append(lp)
        if len({t for t in tokens if t.upper().startswith("L-")}) >= max_pages:
            break

    # Keep high-signal anchor terms and compact raw metric terms
    for t in sorted(anchor_terms, key=len):
        tokens.append(t)

    raw_metric_words = [
        w for w in re.findall(r'\b[a-z]{3,}\b', _SEARCH_NOISE_WORDS.sub(" ", q_lower))
        if w not in _RETRIEVAL_STOPWORDS and w not in _GENERIC_METRIC_WORDS
    ]
    for w in raw_metric_words[:10]:
        tokens.append(w)

    # Corpus-driven L-page inference for remaining query terms (non-hardcoded).
    term_candidates = [
        w for w in metric_terms
        if w not in matched_words_from_defs and w not in anchor_terms
    ]
    inferred = _infer_lpages_from_processed_docs(term_candidates, top_n=2 if len(metric_terms) >= 6 else 1)
    inferred_added = 0
    inferred_cap = min(6, max(2, len(metric_terms)))
    for term in term_candidates:
        for lp in inferred.get(term, []):
            if inferred_added >= inferred_cap:
                break
            tokens.append(lp)
            inferred_added += 1
        if inferred_added >= inferred_cap:
            break

    tokens = _unique_terms(tokens)
    if tokens:
        return " ".join(tokens)

    fallback = _SEARCH_NOISE_WORDS.sub(" ", text)
    fallback = re.sub(r'\s{2,}', ' ', fallback).strip(" .,?!")
    return fallback or text

def _refine_user_request(question: str, free_model: Optional[str] = None, complexity: str = "simple") -> Dict[str, Any]:
    """
    Refine user question by:
    1. Extracting format instructions
    2. Creating optimized search query for vector DB retrieval
    3. Creating analysis instructions for LLM summarization
    
    Uses LLM with project context to intelligently rewrite queries, with rule-based fallback.
    For simple queries, skips the LLM call entirely and uses fast rule-based refinement.
    """
    # Extract format instructions
    format_matches = _FORMAT_WORDS.findall(question)
    format_inst = " ".join(m[1] for m in format_matches).strip() if format_matches else ""
    
    # Skip LLM optimizer for simple queries — go straight to rule-based (fast path)
    if complexity == "simple":
        logger.info("[RAG] Simple query detected, using fast rule-based refinement (skipping LLM optimizer)")
        return _rule_based_refinement(question, format_inst)
    
    # Check optimizer cache for complex queries (avoid repeated LLM calls)
    opt_cache_key = _get_optimizer_cache_key(question)
    if opt_cache_key in _optimizer_cache:
        logger.info("[RAG] Optimizer cache hit, reusing previous LLM rewrite")
        cached = _optimizer_cache[opt_cache_key]
        # Re-apply current format instruction on cache hit
        if format_inst and format_inst not in cached.get("format_instruction", ""):
            cached = {**cached, "format_instruction": f"{cached['format_instruction']} {format_inst}"}
        return cached
    
    # Try LLM-based intelligent query rewriting with project context (complex queries only)
    try:
        # Load actual L-page definitions from the system
        from pathlib import Path
        master_defs_path = Path(PROCESSED_OUTPUT_DIR) / "master_page_definitions.json"
        lpage_definitions = {}
        if master_defs_path.exists():
            with open(master_defs_path, 'r', encoding='utf-8') as f:
                lpage_definitions = json.load(f)
        
        # Create dynamic L-page reference — compact format to fit ALL definitions
        lpage_reference = " | ".join([f"{lpage}: {terms[0] if isinstance(terms, list) else terms}" 
                                     for lpage, terms in sorted(lpage_definitions.items())])
        
        project_context = f"""You are a query optimizer for an IRDAI insurance financial reports analysis system.

PROJECT CONTEXT:
- This system compares financial data across 6 Indian life insurance companies
- Data comes from quarterly IRDAI public disclosure reports (L-forms)
- Available L-page definitions (from actual data):
{lpage_reference}

KEY PRINCIPLES:
1. SEARCH QUERY OPTIMIZATION:
   - Focus on L-page identifiers and document section names
   - Include relevant financial terms that appear in documents
   - Remove comparison words ("all companies", "compare", "each company")
   - Keep it concise and focused on retrieval

2. TERMINOLOGY FLEXIBILITY:
   - User may use informal terms (e.g., "regular premium" instead of "first year premium")
   - Don't hardcode mappings - let the LLM discover actual terms from retrieved data
   - In analysis instruction, tell LLM to: "identify and extract relevant columns/metrics from the data"
   - Let LLM figure out what "regular premium" means by looking at actual table headers

3. ANALYSIS INSTRUCTION:
   - Tell LLM WHAT to do, not HOW to map terms
   - Example: "Extract all premium-related columns from the data and present in table format"
   - NOT: "Extract first year, renewal, single premium" (too prescriptive)
   - Let LLM be smart about finding the right data based on user intent

VECTOR DB RETRIEVAL RULES:
- Vector DB stores individual company chunks (no "all companies" concept)
- Search for document sections (L-pages) and general financial terms
- Good: "L-4 premium schedule", "L-32 solvency", "L-39 claims"
- Avoid: specific column names (let LLM discover those from data)

EXAMPLE:
User: "show regular premium for all companies"
Search Query: "L-4 premium schedule"
Analysis: "Extract premium data from L-4 schedule for each company. Identify and include all premium types/columns present in the data. Present in table format."
"""

        rewrite_prompt = f"""{project_context}

USER QUESTION: {question}

Generate THREE items:

1. SEARCH_QUERY: Optimized for vector DB retrieval
   - Focus on L-page identifiers and section names
   - Include general financial terms (premium, solvency, claims, etc.)
   - Remove comparison/aggregation words
   - Keep it concise (max 15 words)

2. ANALYSIS_INSTRUCTION: Instructions for LLM to analyze retrieved data
   - Tell LLM to discover and extract relevant data from what's retrieved
   - Don't prescribe specific column names - let LLM figure it out
   - Specify format requirements (table, comparison, etc.)
   - Keep it flexible and intent-focused (max 40 words)
   
3. ALT_QUERIES: 2-3 alternative search terms for multi-query retrieval (only if needed to broaden search)

Return ONLY valid JSON:
{{"search_query": "...", "analysis_instruction": "...", "alt_queries": ["...", "..."]}}"""

        logger.debug(f"[RAG] Rewriting query with LLM: '{question}'")
        # Use free model for query rewriting — optimizer output is small (~50 tokens)
        response = ask_llm("You are a query optimization expert.", rewrite_prompt, use_paid=False, free_model=free_model)
        
        # Parse JSON response (handle markdown code blocks)
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            search_q = result.get('search_query', '').strip()
            analysis_inst = result.get('analysis_instruction', '').strip()
            alt_queries = result.get('alt_queries', [])
            if not isinstance(alt_queries, list): alt_queries = []
            
            # Validate results
            if search_q and len(search_q) > 5 and len(search_q) < 200:
                if analysis_inst and len(analysis_inst) > 10:
                    search_q = _compact_vector_query(f"{search_q} {question}")
                    logger.info(f"[RAG] LLM query rewrite successful")
                    logger.info(f"  Original: '{question}'")
                    logger.info(f"  Search: '{search_q}'")
                    logger.info(f"  Analysis: '{analysis_inst}'")
                    
                    # Combine format instruction with analysis instruction
                    if format_inst:
                        analysis_inst = f"{analysis_inst} {format_inst}"
                    
                    result_dict = {
                        "search_query": search_q,
                        "format_instruction": analysis_inst,
                        "alt_queries": alt_queries
                    }
                    
                    # Store in optimizer cache
                    _optimizer_cache[opt_cache_key] = result_dict
                    if len(_optimizer_cache) > _MAX_OPTIMIZER_CACHE:
                        _optimizer_cache.pop(next(iter(_optimizer_cache)))
                    
                    return result_dict
        
        raise ValueError("Invalid LLM response format")
        
    except Exception as e:
        logger.warning(f"[RAG] LLM query rewrite failed ({e}), using rule-based fallback")
    
    # FALLBACK: Rule-based enhancement
    return _rule_based_refinement(question, format_inst)


def _rule_based_refinement(question: str, format_inst: str = "") -> Dict[str, Any]:
    """Fast rule-based query refinement. Used directly for simple queries and as fallback for complex ones."""
    stripped = _FORMAT_WORDS.sub(' ', question).strip()
    stripped = re.sub(r'\s{2,}', ' ', stripped).strip(' .,?!')
    search_q = _compact_vector_query(stripped or question)
    
    # Create analysis instruction from original question
    analysis_inst = question
    if format_inst:
        analysis_inst = f"{question} {format_inst}"
    
    if search_q != (stripped or question):
        logger.info(f"[RAG] Rule-based compact query: '{stripped or question}' → '{search_q}'")
    
    return {
        "search_query": search_q,
        "format_instruction": analysis_inst,
        "alt_queries": []
    }

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


_COMPLEX_KEYWORDS = re.compile(r'\b(compare|vs\.?|versus|all\s+companies|company[-\s]*wise|each\s+company|rank|ranking|which\s+company|across|between)\b', re.I)
_SUPERLATIVE_KEYWORDS = re.compile(r'\b(highest|lowest|top|bottom|best|worst|most|least|trend|growth)\b', re.I)
_ANALYTICAL_COMPLEX_KEYWORDS = re.compile(r'\bclaim\s+settlement\s+ratio\b', re.I)

def _format_source_ref(chunk: Dict[str, Any]) -> str:
    meta = chunk["metadata"]
    file_name = meta.get("source_file", "unknown")
    company = meta.get("company", "unknown")
    period = meta.get("period_label", "unknown")
    lpage = meta.get("page_label") or f"Page {meta.get('page_number', 'N/A')}"
    section = meta.get("section", "unknown")
    return f"{file_name} | {company} | {period} | {lpage} | {section}"

def classify_complexity(q: str) -> str:
    if _ANALYTICAL_COMPLEX_KEYWORDS.search(q): return "complex"
    if _COMPLEX_KEYWORDS.search(q): return "complex"
    cos = get_indexed_companies()
    mentioned = sum(1 for c in cos if c.lower() in q.lower())
    if mentioned > 1: return "complex"
    if _SUPERLATIVE_KEYWORDS.search(q) and mentioned == 0: return "complex"
    return "simple"

def _build_query_plan(
    question: str,
    filters: Optional[Dict[str, Any]],
    top_k: Optional[int],
    free_model: Optional[str],
    paid_model: Optional[str],
) -> QueryPlan:
    """
    Build a typed plan for query processing. This is the first extraction point
    for modularizing rag_pipeline into planner/retriever/summarizer components.
    """
    complexity = classify_complexity(question)
    refined = _refine_user_request(question, free_model=free_model, complexity=complexity)
    search_q, format_inst = refined["search_query"], refined["format_instruction"]

    merged_filters = {**(_extract_auto_filters(question)), **(filters or {})}
    use_paid = complexity == "complex"
    model_name = (paid_model or LLM_MODEL_PAID) if use_paid else (free_model or LLM_MODEL_FREE)
    effective_top_k = top_k or (TOP_K_COMPLEX if use_paid else TOP_K_SIMPLE)

    if use_paid and ENABLE_MULTI_QUERY:
        queries = [search_q] + refined.get("alt_queries", [])
    else:
        queries = [search_q]
        if use_paid and not ENABLE_MULTI_QUERY:
            logger.info("[RAG] Multi-query generation disabled (ENABLE_MULTI_QUERY=False)")
    queries = list(dict.fromkeys(q.strip() for q in queries if q.strip()))[:4]

    return QueryPlan(
        question=question,
        search_query=search_q,
        format_instruction=format_inst,
        complexity=complexity,
        use_paid=use_paid,
        model_name=model_name,
        top_k=effective_top_k,
        merged_filters=merged_filters,
        queries=queries,
        free_model=free_model,
        paid_model=paid_model,
    )

def answer_question(question: str, filters: Optional[Dict[str, Any]] = None, top_k: int = None, free_model: Optional[str] = None, paid_model: Optional[str] = None) -> Dict[str, Any]:
    import time
    overall_start = time.time()
    
    question = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', question.strip())[:2000]
    cache_key = _get_cache_key(question, filters, top_k, free_model, paid_model)
    if cache_key in _response_cache: 
        logger.info("[RAG] Cache hit, returning cached response")
        return _response_cache[cache_key]

    logger.info(f"[RAG] Processing question: '{question[:100]}...'")

    plan = _build_query_plan(
        question=question,
        filters=filters,
        top_k=top_k,
        free_model=free_model,
        paid_model=paid_model,
    )

    logger.info(f"[RAG] Complexity: {plan.complexity}, Model: {plan.model_name}, Top-K: {plan.top_k}")

    query_gen_start = time.time()
    queries = plan.queries
    query_gen_time = time.time() - query_gen_start
    logger.info(f"[RAG] Query setup took {query_gen_time:.2f}s, using {len(queries)} queries")
    
    # Retrieval
    retrieval_start = time.time()
    from src.retriever import retrieve_multi
    if len(queries) == 1:
        chunks = retrieve(queries[0], filters=plan.merged_filters, top_k=plan.top_k)
    else:
        chunks = retrieve_multi(queries, filters=plan.merged_filters, top_k=plan.top_k)
    retrieval_time = time.time() - retrieval_start
    logger.info(f"[RAG] Retrieval took {retrieval_time:.2f}s, found {len(chunks)} chunks")

    # Company top-up (only for complex queries)
    if plan.use_paid and (indexed := get_indexed_companies()):
        topup_start = time.time()
        chunks = top_up_missing_companies(plan.search_query, chunks, indexed, plan.merged_filters)
        topup_time = time.time() - topup_start
        logger.info(f"[RAG] Company top-up took {topup_time:.2f}s, total chunks: {len(chunks)}")

    pre_prune_count = len(chunks)
    chunks = _prune_and_balance_chunks(
        question=question,
        search_q=plan.search_query,
        chunks=chunks,
        top_k=plan.top_k,
        filters=plan.merged_filters,
    )
    if len(chunks) != pre_prune_count:
        logger.warning(f"[RAG] Relevance pruning truncated chunks: {pre_prune_count} -> {len(chunks)}")

    debug_terms = _extract_query_terms_for_relevance(f"{question} {plan.search_query}")
    debug_lpages = sorted(_candidate_lpages_from_terms(debug_terms, f"{question} {plan.search_query}"))
    chunks_per_company: Dict[str, int] = {}
    for c in chunks:
        co = c.get("metadata", {}).get("company_code", "unknown")
        chunks_per_company[co] = chunks_per_company.get(co, 0) + 1

    if not chunks:
        logger.warning("[RAG] No chunks found")
        return {"answer": "No relevant info found.", "sources": [], "chunks_used": 0, "confidence": "none", "model_used": plan.model_name}

    # Context assembly budget guard:
    # keep both char and token budgets to reduce overflow risk on mixed table text.
    total_chars = sum(len(c["text"]) for c in chunks)
    total_tokens = sum(_estimate_text_tokens(c["text"]) for c in chunks)
    char_budget = LLM_MAX_INPUT_CHARS
    token_budget = max(1024, LLM_MAX_INPUT_CHARS // 4)
    if total_chars > char_budget or total_tokens > token_budget:
        original_count = len(chunks)
        kept = []
        running_chars = 0
        running_tokens = 0
        for c in chunks:
            c_chars = len(c["text"])
            c_tokens = _estimate_text_tokens(c["text"])
            if running_chars + c_chars > char_budget:
                break
            if running_tokens + c_tokens > token_budget:
                break
            kept.append(c)
            running_chars += c_chars
            running_tokens += c_tokens
        chunks = kept
        logger.warning(
            "[RAG] Input budget guard truncated chunks %s -> %s (chars %s/%s, tokens %s/%s)",
            original_count, len(chunks), running_chars, char_budget, running_tokens, token_budget
        )

    ctx = "\n\n---\n\n".join(
        [
            f"Source: {c['metadata']['source_file']} | Company: {c['metadata']['company']} | Period: {c['metadata']['period_label']} | L-Page: {c['metadata'].get('page_label') or 'N/A'} | Section: {c['metadata']['section']}\n\n{c['text']}"
            for c in chunks
        ]
    )
    fmt = f"\nFormat Instruction: {plan.format_instruction}" if plan.format_instruction else ""
    summary_query = f"Question: {question}{fmt}"
    
    # LLM call
    llm_start = time.time()
    logger.info(f"[RAG] Calling LLM with {len(ctx)} chars of context...")
    answer = ask_llm(
        SYSTEM_PROMPT,
        f"{summary_query}\n\nExcerpts:\n{ctx}",
        use_paid=plan.use_paid,
        free_model=plan.free_model,
        paid_model=plan.paid_model,
    )
    llm_time = time.time() - llm_start
    logger.info(f"[RAG] LLM response took {llm_time:.2f}s")

    source_refs = []
    seen = set()
    for chunk in chunks:
        ref = _format_source_ref(chunk)
        if ref not in seen:
            source_refs.append(ref)
            seen.add(ref)
    res = {
        "answer": answer,
        "sources": source_refs,
        "chunks_used": len(chunks),
        "confidence": get_confidence_level(chunks),
        "model_used": plan.model_name,
        "query_debug": {
            "vector_query": plan.search_query,
            "summary_query": summary_query,
            "intent_terms": debug_terms,
            "resolved_lpages": debug_lpages,
            "chunks_per_company": chunks_per_company,
            "context_chars": sum(len(c["text"]) for c in chunks),
            "context_tokens_est": sum(_estimate_text_tokens(c["text"]) for c in chunks),
        },
    }
    _response_cache[cache_key] = res
    if len(_response_cache) > _MAX_CACHE_SIZE: _response_cache.pop(next(iter(_response_cache)))
    
    overall_time = time.time() - overall_start
    logger.info(f"[RAG] Total time: {overall_time:.2f}s (query_gen: {query_gen_time:.2f}s, retrieval: {retrieval_time:.2f}s, llm: {llm_time:.2f}s)")
    
    return res
