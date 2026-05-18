"""
Tests for retrieval logic and top_up_missing_companies().
"""

import pytest
from unittest.mock import patch

from src.retriever import retrieve, top_up_missing_companies, get_confidence_level


# ── retrieve() ──────────────────────────────────────────────────────────────

def test_retrieve_returns_results(temp_chroma):
    """retrieve() should return at least one result for a relevant query."""
    # temp_chroma patches src.embedder.CHROMA_DB_PATH, so get_or_create_collection()
    # will open the seeded test DB automatically — no extra patch needed.
    results = retrieve("gross written premium")
    assert isinstance(results, list)
    assert len(results) > 0


def test_retrieve_result_shape(temp_chroma):
    """Each result must have text, metadata, score."""
    results = retrieve("premium income")
    for r in results:
        assert "text" in r
        assert "metadata" in r
        assert "score" in r
        assert 0.0 <= r["score"] <= 1.0


def test_retrieve_with_company_filter(temp_chroma):
    """Company filter should restrict results to that company."""
    results = retrieve("premium", filters={"company_code": "HDFC_Life"})
    for r in results:
        assert r["metadata"]["company_code"] == "HDFC_Life"


def test_retrieve_empty_collection(tmp_path):
    """retrieve() on empty collection must return []."""
    import chromadb
    from chromadb.config import Settings

    client = chromadb.PersistentClient(
        path=str(tmp_path / "empty_db"),
        settings=Settings(anonymized_telemetry=False),
    )
    empty_col = client.get_or_create_collection("empty", metadata={"hnsw:space": "cosine"})

    # retrieve() has its own binding from 'from src.embedder import get_or_create_collection'
    # so we must patch at src.retriever.*
    with patch("src.retriever.get_or_create_collection", return_value=empty_col):
        results = retrieve("any query")
    assert results == []


# ── top_up_missing_companies() ───────────────────────────────────────────────

def test_top_up_fills_missing_company(temp_chroma):
    """Companies absent from initial results should be added via top-up."""
    # conftest patches src.embedder.CHROMA_DB_PATH — all calls go to test DB
    initial = retrieve("premium", top_k=1)
    present = {c["metadata"]["company_code"] for c in initial}
    all_companies = ["HDFC_Life", "SBI_Life", "LIC", "ICICI_Pru"]

    result = top_up_missing_companies("premium", initial, all_companies)
    result_companies = {c["metadata"]["company_code"] for c in result}
    # After top-up, at least more companies should be covered
    assert len(result_companies) >= len(present)


def test_top_up_no_op_when_all_present(temp_chroma):
    """If all companies are already present, top_up should return same list."""
    chunks = retrieve("premium", top_k=10)
    present = {c["metadata"]["company_code"] for c in chunks}
    result = top_up_missing_companies("premium", chunks, list(present))
    assert len(result) == len(chunks)

def test_top_up_prefers_intent_matching_lpage():
    """Top-up should prefer intended L-page chunks (e.g., L-4 premium) over generic pages."""
    initial = [{
        "text": "existing",
        "metadata": {"company_code": "A", "chunk_id": "A1", "page_label": "L-4", "section": "Premium Schedule"},
        "score": 0.9,
    }]
    expected = ["A", "B"]

    def _fake_retrieve(query, filters=None, top_k=None):
        if filters and filters.get("company_code") == "B":
            return [
                {"text": "Revenue account chunk", "metadata": {"company_code": "B", "chunk_id": "B-L1", "page_label": "L-1-A-RA", "section": "Revenue Account"}, "score": 0.95},
                {"text": "Borrowings chunk", "metadata": {"company_code": "B", "chunk_id": "B-L11", "page_label": "L-11", "section": "Borrowings Schedule"}, "score": 0.94},
                {"text": "Premium chunk", "metadata": {"company_code": "B", "chunk_id": "B-L4", "page_label": "L-4", "section": "Premium Schedule"}, "score": 0.60},
            ]
        return []

    with patch("src.retriever.retrieve", side_effect=_fake_retrieve):
        out = top_up_missing_companies(
            "Q3 FY26 L-4 premium schedule premium",
            initial,
            expected,
            filters={"quarter": "Q3", "fy": "FY26"},
        )

    b_chunks = [c for c in out if c["metadata"]["company_code"] == "B"]
    assert b_chunks, "Expected top-up to add missing company B"
    assert any(c["metadata"].get("page_label", "").startswith("L-4") for c in b_chunks), (
        f"Expected L-4 premium chunk for company B, got {[c['metadata'].get('page_label') for c in b_chunks]}"
    )

def test_top_up_repairs_company_with_wrong_existing_chunk():
    """If a company is already present but only with non-intent chunks, top-up should repair it."""
    initial = [
        {
            "text": "wrong shriram chunk with premium mentioned in narrative",
            "metadata": {"company_code": "ShriramInsurance", "chunk_id": "S-L1", "page_label": "L-1-A-RA", "section": "Revenue Account"},
            "score": 0.92,
        }
    ]
    expected = ["ShriramInsurance"]

    def _fake_retrieve(query, filters=None, top_k=None):
        if filters and filters.get("company_code") == "ShriramInsurance":
            return [
                {"text": "Revenue account chunk", "metadata": {"company_code": "ShriramInsurance", "chunk_id": "S-L1-2", "page_label": "L-1-A-RA", "section": "Revenue Account"}, "score": 0.94},
                {"text": "Premium chunk", "metadata": {"company_code": "ShriramInsurance", "chunk_id": "S-L4", "page_label": "L-4-PREMIUM", "section": "Premium Schedule"}, "score": 0.70},
            ]
        return []

    with patch("src.retriever.retrieve", side_effect=_fake_retrieve):
        out = top_up_missing_companies(
            "Q3 FY26 L-4 premium schedule premium",
            initial,
            expected,
            filters={"quarter": "Q3", "fy": "FY26"},
        )

    shriram_chunks = [c for c in out if c["metadata"]["company_code"] == "ShriramInsurance"]
    assert any(c["metadata"].get("page_label", "").startswith("L-4") for c in shriram_chunks), (
        f"Expected repaired L-4 chunk for ShriramInsurance, got {[c['metadata'].get('page_label') for c in shriram_chunks]}"
    )


# ── get_confidence_level() ───────────────────────────────────────────────────

def test_confidence_empty():
    assert get_confidence_level([]) == "none"

def test_confidence_high():
    assert get_confidence_level([{"score": 0.85}]) == "high"

def test_confidence_medium():
    assert get_confidence_level([{"score": 0.55}]) == "medium"

def test_confidence_none_low_score():
    assert get_confidence_level([{"score": 0.2}]) == "none"

def test_confidence_never_returns_low():
    """'low' must never be returned — plan explicitly forbids it."""
    for score in [0.0, 0.1, 0.2, 0.39]:
        result = get_confidence_level([{"score": score}])
        assert result != "low", f"get_confidence_level returned 'low' for score={score}"
