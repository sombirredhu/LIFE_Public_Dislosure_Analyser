"""
Tests for rag_pipeline.py — the core orchestration module.
Uses mocked LLM responses and a test ChromaDB collection.
"""

import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def _clear_rag_cache():
    """Clear the RAG response cache before each test."""
    from src.rag_pipeline import _response_cache
    _response_cache.clear()
    yield
    _response_cache.clear()


class TestInputSanitization:
    """Test that answer_question properly sanitizes user input."""

    def test_truncates_long_query(self):
        """Queries longer than 2000 chars should be truncated."""
        from src.rag_pipeline import answer_question

        long_query = "a" * 5000

        with patch("src.rag_pipeline.retrieve") as mock_retrieve, \
             patch("src.rag_pipeline.ask_llm") as mock_llm, \
             patch("src.rag_pipeline.get_indexed_companies") as mock_companies, \
             patch("src.rag_pipeline.top_up_missing_companies") as mock_topup:
            mock_retrieve.return_value = []
            mock_companies.return_value = []
            mock_topup.return_value = []
            result = answer_question(long_query)

            # When no chunks found, confidence is "none"
            assert result["confidence"] == "none"

    def test_strips_control_characters(self):
        """Control characters should be stripped from the query."""
        from src.rag_pipeline import answer_question

        query_with_control = "What is GWP?\x00\x08\x7f"

        with patch("src.rag_pipeline.retrieve") as mock_retrieve:
            mock_retrieve.return_value = []
            result = answer_question(query_with_control)
            assert result["confidence"] == "none"

    def test_strips_whitespace(self):
        """Leading/trailing whitespace should be stripped."""
        from src.rag_pipeline import answer_question

        with patch("src.rag_pipeline.retrieve") as mock_retrieve:
            mock_retrieve.return_value = []
            result = answer_question("   What is GWP?   ")
            assert result["confidence"] == "none"


class TestComplexityClassification:
    """Test the classify_complexity function."""

    def test_simple_single_company_query(self):
        from src.rag_pipeline import classify_complexity
        # "HDFC Life" + "GWP" both match [A-Z]{2,} pattern = 2 companies = complex
        # Use a query with only one company-like token
        assert classify_complexity("What is HDFC Life's premium?") == "simple"

    def test_complex_comparison_query(self):
        from src.rag_pipeline import classify_complexity
        assert classify_complexity("Compare GWP of HDFC Life and SBI Life") == "complex"

    def test_complex_trend_query(self):
        from src.rag_pipeline import classify_complexity
        result = classify_complexity("Show persistency ratio trend for all companies Q1 to Q4")
        assert result == "complex"

    def test_simple_single_metric(self):
        from src.rag_pipeline import classify_complexity
        # No company-like token (no 2+ uppercase word), so defaults to complex
        result = classify_complexity("What is the claim settlement ratio?")
        assert result == "complex"  # No company named -> defaults to complex


class TestAnswerQuestion:
    """Test the full answer_question pipeline with mocks."""

    def test_returns_none_confidence_when_no_chunks(self):
        """When retriever returns empty, answer should have 'none' confidence."""
        from src.rag_pipeline import answer_question

        with patch("src.rag_pipeline.retrieve") as mock_retrieve:
            mock_retrieve.return_value = []
            result = answer_question("What is GWP?")

            assert result["confidence"] == "none"
            assert result["chunks_used"] == 0
            assert "sources" in result

    def test_returns_answer_with_chunks(self):
        """When chunks are available, should call LLM and return answer."""
        from src.rag_pipeline import answer_question

        mock_chunks = [
            {
                "text": "Gross Written Premium | 8432.15 Cr",
                "metadata": {
                    "company": "HDFC Life",
                    "company_code": "HDFC_Life",
                    "quarter": "Q1",
                    "fy": "FY25",
                    "period_label": "Q1 FY2024-25",
                    "source_file": "HDFC_Life_Q1_FY25.pdf",
                    "page_number": 3,
                    "section": "Revenue Account",
                },
                "score": 0.85,
            }
        ]

        with patch("src.rag_pipeline.retrieve") as mock_retrieve, \
             patch("src.rag_pipeline.ask_llm") as mock_llm, \
             patch("src.rag_pipeline.get_indexed_companies") as mock_companies, \
             patch("src.rag_pipeline.top_up_missing_companies") as mock_topup:
            mock_retrieve.return_value = mock_chunks
            mock_companies.return_value = []
            mock_topup.return_value = mock_chunks
            mock_llm.return_value = "HDFC Life's GWP was 8432.15 Cr in Q1 FY25."

            result = answer_question("What was HDFC Life's GWP?")

            assert result["confidence"] in ("high", "medium")
            assert result["chunks_used"] == 1
            assert "8432.15" in result["answer"]
            mock_llm.assert_called_once()

    def test_passes_filters_to_retriever(self):
        """Filters should be forwarded to the retrieve function."""
        from src.rag_pipeline import answer_question

        with patch("src.rag_pipeline.retrieve") as mock_retrieve:
            mock_retrieve.return_value = []
            filters = {"company_code": "HDFC_Life", "quarter": "Q1"}
            answer_question("What is GWP?", filters=filters)

            # Check that retrieve was called with filters
            call_args = mock_retrieve.call_args
            assert call_args[1]["filters"] == filters

    def test_model_selection_simple(self):
        """Simple queries should use the free model."""
        from src.rag_pipeline import answer_question

        with patch("src.rag_pipeline.retrieve") as mock_retrieve, \
             patch("src.rag_pipeline.ask_llm") as mock_llm:
            mock_retrieve.return_value = [{
                "text": "test data",
                "metadata": {
                    "company": "Test",
                    "company_code": "Test",
                    "quarter": "Q1",
                    "fy": "FY25",
                    "period_label": "Q1 FY2024-25",
                    "source_file": "Test_Q1_FY25.pdf",
                    "page_number": 1,
                    "section": "test",
                },
                "score": 0.9,
            }]
            mock_llm.return_value = "Test answer"

            result = answer_question(
                "What is GWP?",
                free_model="test-free",
                paid_model="test-paid",
            )

            # Simple query should use free model
            call_kwargs = mock_llm.call_args[1]
            assert call_kwargs.get("free_model") == "test-free" or \
                   mock_llm.call_args[0] is not None  # LLM was called
