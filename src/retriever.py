"""
Retriever - searches ChromaDB for relevant chunks based on query.
Supports filtering by company, quarter, FY, and other metadata.
Implements parallel top-up to guarantee every indexed company appears in results.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from src.config import TOP_K_SIMPLE, SIMILARITY_THRESHOLD
from src.embedder import get_or_create_collection, get_embedding_model

logger = logging.getLogger(__name__)


def _normalize_filters(filters: Dict[str, Any]) -> Dict[str, Any]:
    """
    ChromaDB 1.x requires exactly one operator at the top level of a where clause.
    A flat dict with multiple keys raises ValueError.
    Wrap multiple conditions in $and so ChromaDB accepts them.

    Examples:
        {"quarter": "Q3"}                          → unchanged (single key)
        {"quarter": "Q3", "fy": "FY26"}            → {"$and": [{"quarter": "Q3"}, {"fy": "FY26"}]}
        {"company_code": {"$in": [...]}, "fy": …}  → {"$and": [{"company_code": {"$in": [...]}}, {"fy": …}]}
    """
    if not filters or len(filters) == 1:
        return filters
    return {"$and": [{k: v} for k, v in filters.items()]}


def retrieve(
    query: str,
    filters: Optional[Dict[str, Any]] = None,
    top_k: int = None,
) -> List[Dict[str, Any]]:
    """
    Search ChromaDB for chunks relevant to the query.

    Args:
        query:   Search query string
        filters: Optional metadata filters
        top_k:   Number of results (defaults to TOP_K_SIMPLE)

    Returns:
        List of dicts with keys: text, metadata, score
    """
    if top_k is None:
        top_k = TOP_K_SIMPLE

    collection = get_or_create_collection()
    model = get_embedding_model()

    total_in_db = collection.count()
    if total_in_db == 0:
        return []

    # Clamp top_k to what actually exists (avoids ChromaDB errors)
    top_k = min(top_k, total_in_db)

    normalized = _normalize_filters(filters) if filters else None
    logger.debug(
        "[RETRIEVE] query=%r | raw_filters=%s | normalized=%s | top_k=%d",
        query[:80], filters, normalized, top_k,
    )

    query_embedding = model.encode(query).tolist()

    query_params: Dict[str, Any] = {
        "query_embeddings": [query_embedding],
        "n_results": top_k,
    }
    if normalized:
        query_params["where"] = normalized

    results = collection.query(**query_params)

    chunks: List[Dict[str, Any]] = []

    if results["ids"] and results["ids"][0]:
        for i in range(len(results["ids"][0])):
            distance = results["distances"][0][i]
            score = 1.0 - distance  # cosine distance → cosine similarity

            if score < SIMILARITY_THRESHOLD:
                continue

            chunks.append({
                "text":     results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "score":    round(score, 4),
            })

    if chunks:
        logger.info(
            "[RETRIEVE] Found %d chunks | top_score=%.4f | query=%r",
            len(chunks), chunks[0]["score"], query[:60],
        )
    else:
        logger.warning(
            "[RETRIEVE] No chunks above threshold %.2f | query=%r | filters=%s",
            SIMILARITY_THRESHOLD, query[:60], filters,
        )

    return chunks


def top_up_missing_companies(
    query: str,
    chunks: List[Dict[str, Any]],
    expected_companies: List[str],
    filters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Ensure every indexed company has at least one chunk in the result set.
    Fetches missing companies IN PARALLEL using ThreadPoolExecutor.

    Args:
        query:              Original search query
        chunks:             Already-retrieved chunks
        expected_companies: All company_codes currently in ChromaDB
        filters:            Any original filters (except company) to preserve

    Returns:
        Extended chunk list with top-up results merged in
    """
    present = {c["metadata"]["company_code"] for c in chunks}
    missing = [co for co in expected_companies if co not in present]

    if not missing:
        return chunks

    logger.info("Top-up: fetching %d missing companies in parallel: %s", len(missing), missing)

    def _fetch_one(company_code: str) -> List[Dict[str, Any]]:
        company_filter: Dict[str, Any] = {"company_code": company_code}
        if filters:
            combined = {**filters, **company_filter}
        else:
            combined = company_filter
        return retrieve(query, filters=combined, top_k=2)

    top_up_chunks: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        future_map = {pool.submit(_fetch_one, co): co for co in missing}
        for future in as_completed(future_map):
            company = future_map[future]
            try:
                result = future.result()
                top_up_chunks.extend(result)
            except Exception as exc:
                logger.warning("Top-up fetch failed for %s: %s", company, exc)

    return chunks + top_up_chunks


def get_confidence_level(chunks: List[Dict[str, Any]]) -> str:
    """
    Determine confidence level based on top chunk similarity score.
    Returns: "high" | "medium" | "none"  — "low" is NOT returned (pre-filtered by SIMILARITY_THRESHOLD).
    """
    if not chunks:
        return "none"

    top_score = chunks[0]["score"]

    if top_score >= 0.7:
        return "high"
    if top_score >= 0.4:
        return "medium"
    return "none"


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "gross written premium"

    print(f"Query: {query}")
    print(f"Retrieving top {TOP_K_SIMPLE} chunks...\n")

    results = retrieve(query)

    if not results:
        print("No results found above similarity threshold")
    else:
        print(f"✓ Found {len(results)} relevant chunks\n")
        print(f"Confidence: {get_confidence_level(results)}\n")

        for i, chunk in enumerate(results[:3], 1):
            print(f"Result {i}:")
            print(f"  Score:   {chunk['score']}")
            print(f"  Source:  {chunk['metadata']['source_file']}")
            print(f"  Company: {chunk['metadata']['company']}")
            print(f"  Period:  {chunk['metadata']['period_label']}")
            print(f"  Page:    {chunk['metadata']['page_number']}")
            print(f"  Section: {chunk['metadata']['section']}")
            print(f"  Type:    {chunk['metadata']['content_type']}")
            print(f"  Preview: {chunk['text'][:150]}...")
            print()
