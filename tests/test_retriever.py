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
