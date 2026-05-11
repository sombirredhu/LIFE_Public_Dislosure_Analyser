"""
Tests for input token budget guard (truncation) and finish_reason='length' warning.
"""

import logging
import pytest
from unittest.mock import patch, MagicMock

from src.rag_pipeline import answer_question
from src.llm_client import ask_llm


# ── Input token budget guard in answer_question() ────────────────────────────

def _make_chunks(n: int, char_size: int = 5000):
    """Generate n fake chunks each with char_size characters of text."""
    return [
        {
            "text": "A" * char_size,
            "metadata": {
                "chunk_id":     f"LIC_Q1_FY25_page1_chunk{i}",
                "company":      "LIC",
                "company_code": "LIC",
                "quarter":      "Q1",
                "fy":           "FY25",
                "period_label": "Q1 FY2024-25",
                "source_file":  "LIC_Q1_FY25.pdf",
                "page_number":  i,
                "page_label":   "",
                "section":      "unknown",
                "content_type": "text",
                "char_count":   char_size,
                "ingested_at":  "2024-01-01T00:00:00",
            },
            "score": 0.8 - (i * 0.01),
        }
        for i in range(n)
    ]


def test_truncation_fires_when_input_exceeds_limit(caplog):
    """
    When total input chars > LLM_MAX_INPUT_CHARS, a WARNING must be logged
    and the chunk list must be reduced.
    """
    # 30 chunks × 5000 chars = 150,000 chars — exceeds default 120,000 limit
    big_chunk_list = _make_chunks(30, char_size=5000)

    with patch("src.rag_pipeline.retrieve", return_value=big_chunk_list), \
         patch("src.rag_pipeline.get_indexed_companies", return_value=[]), \
         patch("src.rag_pipeline.ask_llm", return_value="mocked answer"):

        with caplog.at_level(logging.WARNING, logger="src.rag_pipeline"):
            result = answer_question("What is LIC's GWP?")

    assert "truncated" in caplog.text.lower() or "exceeded" in caplog.text.lower()
    assert result["chunks_used"] < 30


def test_no_truncation_when_within_limit():
    """When total chars are within limit, all chunks are used."""
    small_chunk_list = _make_chunks(5, char_size=1000)  # 5,000 chars total

    with patch("src.rag_pipeline.retrieve", return_value=small_chunk_list), \
         patch("src.rag_pipeline.get_indexed_companies", return_value=[]), \
         patch("src.rag_pipeline.ask_llm", return_value="mocked answer"):

        result = answer_question("What is LIC's GWP?")

    assert result["chunks_used"] == 5


# ── finish_reason='length' warning in ask_llm() ──────────────────────────────

def test_finish_reason_length_logs_warning(caplog):
    """
    When OpenRouter returns finish_reason='length', ask_llm must log a WARNING.
    """
    mock_choice = MagicMock()
    mock_choice.finish_reason = "length"
    mock_choice.message.content = "truncated response"

    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 100
    mock_usage.completion_tokens = 50

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = mock_usage

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch("src.llm_client.OpenAI", return_value=mock_client), \
         patch("src.llm_client.OPENROUTER_API_KEY", "test-key"):

        with caplog.at_level(logging.WARNING, logger="src.llm_client"):
            text = ask_llm("system", "user")

    assert text == "truncated response"
    assert "length" in caplog.text.lower() or "truncat" in caplog.text.lower()


def test_finish_reason_stop_no_warning(caplog):
    """Normal stop reason must NOT trigger a truncation warning."""
    mock_choice = MagicMock()
    mock_choice.finish_reason = "stop"
    mock_choice.message.content = "complete answer"

    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 50
    mock_usage.completion_tokens = 20

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = mock_usage

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch("src.llm_client.OpenAI", return_value=mock_client), \
         patch("src.llm_client.OPENROUTER_API_KEY", "test-key"):

        with caplog.at_level(logging.WARNING, logger="src.llm_client"):
            text = ask_llm("system", "user")

    assert text == "complete answer"
    assert "length" not in caplog.text.lower()
