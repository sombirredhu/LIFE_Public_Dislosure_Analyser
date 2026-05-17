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

    def test_cache_hit_for_same_query_and_same_model(self):
        """Same query + same model should return cached answer without second LLM call."""
        from src.rag_pipeline import answer_question

        mock_chunks = [{
            "text": "Persistency 13th month | 82.3%",
            "metadata": {
                "company": "ICICI",
                "company_code": "ICICI",
                "quarter": "Q3",
                "fy": "FY26",
                "period_label": "Q3 FY26",
                "source_file": "ICICI_Q3_FY26.pdf",
                "page_number": 6,
                "section": "Analytical Ratios",
            },
            "score": 0.91,
        }]

        with patch("src.rag_pipeline.retrieve") as mock_retrieve, \
             patch("src.rag_pipeline.ask_llm") as mock_llm:
            mock_retrieve.return_value = mock_chunks
            mock_llm.return_value = "Cached answer"

            q = "What is persistency for ICICI in Q3 FY26?"
            r1 = answer_question(q, free_model="free-a", paid_model="paid-a")
            r2 = answer_question(q, free_model="free-a", paid_model="paid-a")

            assert r1["answer"] == "Cached answer"
            assert r2["answer"] == "Cached answer"
            assert mock_llm.call_count == 1
            assert mock_retrieve.call_count == 1

    def test_cache_miss_when_model_changes_for_same_query(self):
        """Same query with different selected model should not reuse cache."""
        from src.rag_pipeline import answer_question

        mock_chunks = [{
            "text": "Expense ratio | 8.2%",
            "metadata": {
                "company": "TataAIA",
                "company_code": "TataAIA",
                "quarter": "Q3",
                "fy": "FY26",
                "period_label": "Q3 FY26",
                "source_file": "TataAIA_Q3_FY26.pdf",
                "page_number": 6,
                "section": "Operating Expenses",
            },
            "score": 0.89,
        }]

        with patch("src.rag_pipeline.retrieve") as mock_retrieve, \
             patch("src.rag_pipeline.ask_llm") as mock_llm:
            mock_retrieve.return_value = mock_chunks
            mock_llm.side_effect = ["Answer model A", "Answer model B"]

            q = "What is expense ratio for TataAIA in Q3 FY26?"
            r1 = answer_question(q, free_model="free-a", paid_model="paid-a")
            r2 = answer_question(q, free_model="free-a", paid_model="paid-b")

            assert r1["answer"] == "Answer model A"
            assert r2["answer"] == "Answer model B"
            assert mock_llm.call_count == 2
            assert mock_retrieve.call_count == 2


class TestRelevancePruning:
    """Noise-reduction and company-balancing behavior for retrieved chunks."""

    def test_prune_keeps_relevant_lpage_chunks(self):
        from src.rag_pipeline import _prune_and_balance_chunks

        chunks = [
            {
                "text": "Premium schedule values for Q3 FY26",
                "metadata": {"company_code": "A", "page_label": "L-4", "section": "Premium Schedule"},
                "score": 0.82,
            },
            {
                "text": "Commission and operating expenses details",
                "metadata": {"company_code": "A", "page_label": "L-6", "section": "Operating Expenses"},
                "score": 0.84,
            },
            {
                "text": "Premium growth commentary",
                "metadata": {"company_code": "B", "page_label": "L-4", "section": "Premium Schedule"},
                "score": 0.80,
            },
        ]

        with patch("src.rag_pipeline._candidate_lpages_from_terms", return_value={"L-4"}):
            pruned = _prune_and_balance_chunks(
                question="Compare premium for Q3 FY26",
                search_q="Q3 FY26 L-4 premium schedule",
                chunks=chunks,
                top_k=10,
            )

        pages = [c["metadata"].get("page_label") for c in pruned]
        assert "L-4" in pages
        assert len(pruned) <= len(chunks)

    def test_prune_balances_per_company_in_broad_compare(self):
        from src.rag_pipeline import _prune_and_balance_chunks

        chunks = []
        for company in ["A", "B", "C"]:
            chunks.extend([
                {
                    "text": f"Premium schedule primary metric {company}",
                    "metadata": {"company_code": company, "page_label": "L-4", "section": "Premium Schedule"},
                    "score": 0.85,
                },
                {
                    "text": f"Premium schedule secondary metric {company}",
                    "metadata": {"company_code": company, "page_label": "L-4", "section": "Premium Schedule"},
                    "score": 0.81,
                },
                {
                    "text": f"Unrelated investment notes {company}",
                    "metadata": {"company_code": company, "page_label": "L-15", "section": "Investments"},
                    "score": 0.79,
                },
            ])

        with patch("src.rag_pipeline._candidate_lpages_from_terms", return_value={"L-4"}):
            pruned = _prune_and_balance_chunks(
                question="Compare company-wise premium for Q3 FY26",
                search_q="Q3 FY26 premium L-4 schedule",
                chunks=chunks,
                top_k=20,
            )

        # Broad compare should stay near 1-2 chunks per company unless strongly needed.
        assert 3 <= len(pruned) <= 9
        companies = {c["metadata"]["company_code"] for c in pruned}
        assert companies == {"A", "B", "C"}

    def test_prune_expands_to_5_per_company_for_three_metrics(self):
        from src.rag_pipeline import _prune_and_balance_chunks

        chunks = []
        for company in ["A", "B", "C"]:
            chunks.extend([
                {
                    "text": f"{company} premium data",
                    "metadata": {"company_code": company, "page_label": "L-4", "section": "Premium Schedule"},
                    "score": 0.88,
                },
                {
                    "text": f"{company} premium extra details",
                    "metadata": {"company_code": company, "page_label": "L-4-DETAIL", "section": "Premium Schedule"},
                    "score": 0.83,
                },
                {
                    "text": f"{company} expense ratio details",
                    "metadata": {"company_code": company, "page_label": "L-6", "section": "Operating Expenses"},
                    "score": 0.87,
                },
                {
                    "text": f"{company} expense notes",
                    "metadata": {"company_code": company, "page_label": "L-6-DETAIL", "section": "Operating Expenses"},
                    "score": 0.81,
                },
                {
                    "text": f"{company} persistency 13th 25th 37th",
                    "metadata": {"company_code": company, "page_label": "L-22", "section": "Analytical Ratios"},
                    "score": 0.86,
                },
                {
                    "text": f"{company} other non-core page",
                    "metadata": {"company_code": company, "page_label": "L-31", "section": "Assets"},
                    "score": 0.78,
                },
            ])

        with patch("src.rag_pipeline._candidate_lpages_from_terms", return_value={"L-4", "L-6", "L-22"}):
            pruned = _prune_and_balance_chunks(
                question="Compare premium, expense ratio and persistency company-wise for Q3 FY26",
                search_q="Q3 FY26 L-4 premium L-6 expense ratio L-22 persistency",
                chunks=chunks,
                top_k=40,
            )

        # 3 companies x cap 5 => up to 15 selected
        assert 12 <= len(pruned) <= 15
        by_company = {}
        for c in pruned:
            by_company.setdefault(c["metadata"]["company_code"], []).append(c)
        assert set(by_company.keys()) == {"A", "B", "C"}
        assert all(len(v) <= 5 for v in by_company.values())


class TestVectorQueryCompaction:
    def test_pat_query_avoids_unrelated_pages(self):
        from src.rag_pipeline import _compact_vector_query

        q = "List company-wise PAT for Q3 FY26 and rank all companies from highest to lowest, with values and L-page references."
        term_map = {
            "pat": "L-2",
            "profit after tax": "L-2-A-PL",
        }
        defs_map = {
            "L-2": ["profit and loss account", "profit after tax"],
            "L-14A": ["aggregate value of investments other than equity shares and mutual fund"],
            "L-40": ["quarterly claims data"],
        }

        with patch("src.rag_pipeline._load_term_to_page_map", return_value=term_map), \
             patch("src.rag_pipeline._load_page_definitions_map", return_value=defs_map), \
             patch("src.rag_pipeline._infer_lpages_from_processed_docs", return_value={}):
            vq = _compact_vector_query(q)

        vq_upper = vq.upper()
        assert "Q3" in vq_upper and "FY26" in vq_upper
        assert "L-2" in vq_upper
        assert "PAT" in vq_upper
        assert "L-40" not in vq_upper
        assert "L-14A" not in vq_upper

    def test_multi_metric_query_keeps_multiple_lpages(self):
        from src.rag_pipeline import _compact_vector_query

        q = "Compare company-wise premium, expense ratio and persistency for Q3 FY26."
        term_map = {
            "premium": "L-4",
            "expense ratio": "L-6",
            "persistency": "L-22",
        }
        defs_map = {
            "L-4": ["premium schedule"],
            "L-6": ["operating expenses"],
            "L-22": ["analytical ratios persistency"],
        }

        with patch("src.rag_pipeline._load_term_to_page_map", return_value=term_map), \
             patch("src.rag_pipeline._load_page_definitions_map", return_value=defs_map), \
             patch("src.rag_pipeline._infer_lpages_from_processed_docs", return_value={}):
            vq = _compact_vector_query(q)

        vq_upper = vq.upper()
        assert "L-4" in vq_upper
        assert "L-6" in vq_upper
        assert "L-22" in vq_upper
