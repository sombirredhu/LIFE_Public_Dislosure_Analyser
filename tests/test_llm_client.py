"""
Tests for llm_client.py — the OpenRouter API wrapper.
All tests use mocked HTTP responses — no real API calls.
"""

import pytest
from unittest.mock import patch, MagicMock
from openai import RateLimitError, APITimeoutError


class TestAskLLM:
    """Test the ask_llm function with mocked OpenAI client."""

    def _make_mock_response(self, content="Test response", finish_reason="stop"):
        """Create a mock OpenAI ChatCompletion response."""
        mock_choice = MagicMock()
        mock_choice.message.content = content
        mock_choice.finish_reason = finish_reason

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 100
        mock_usage.completion_tokens = 50

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage
        return mock_response

    def test_raises_on_missing_api_key(self):
        """Should raise ValueError when API key is not set."""
        from src.llm_client import ask_llm

        with patch("src.llm_client.OPENROUTER_API_KEY", ""):
            with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
                ask_llm("system prompt", "user message")

    def test_returns_response_text(self):
        """Should return the LLM response content."""
        from src.llm_client import ask_llm

        with patch("src.llm_client.OPENROUTER_API_KEY", "test-key"), \
             patch("src.llm_client.OpenAI") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.chat.completions.create.return_value = self._make_mock_response("Hello world")

            result = ask_llm("Be helpful", "Say hello")
            assert result == "Hello world"

    def test_uses_free_model_by_default(self):
        """When use_paid=False, should use the free model."""
        from src.llm_client import ask_llm

        with patch("src.llm_client.OPENROUTER_API_KEY", "test-key"), \
             patch("src.llm_client.OpenAI") as MockClient, \
             patch("src.llm_client.LLM_MODEL_FREE", "free-model"):
            mock_instance = MockClient.return_value
            mock_instance.chat.completions.create.return_value = self._make_mock_response()

            ask_llm("system", "user", use_paid=False)

            call_kwargs = mock_instance.chat.completions.create.call_args[1]
            assert call_kwargs["model"] == "free-model"

    def test_uses_paid_model_when_requested(self):
        """When use_paid=True, should use the paid model."""
        from src.llm_client import ask_llm

        with patch("src.llm_client.OPENROUTER_API_KEY", "test-key"), \
             patch("src.llm_client.OpenAI") as MockClient, \
             patch("src.llm_client.LLM_MODEL_PAID", "paid-model"):
            mock_instance = MockClient.return_value
            mock_instance.chat.completions.create.return_value = self._make_mock_response()

            ask_llm("system", "user", use_paid=True)

            call_kwargs = mock_instance.chat.completions.create.call_args[1]
            assert call_kwargs["model"] == "paid-model"

    def test_override_model_ids(self):
        """Custom free_model and paid_model should override defaults."""
        from src.llm_client import ask_llm

        with patch("src.llm_client.OPENROUTER_API_KEY", "test-key"), \
             patch("src.llm_client.OpenAI") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.chat.completions.create.return_value = self._make_mock_response()

            ask_llm("system", "user", use_paid=False, free_model="custom-free")

            call_kwargs = mock_instance.chat.completions.create.call_args[1]
            assert call_kwargs["model"] == "custom-free"

    def test_retries_on_rate_limit(self):
        """Should retry with backoff on RateLimitError."""
        from src.llm_client import ask_llm

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {}
        mock_response.json.return_value = {"error": {"message": "rate limited"}}

        with patch("src.llm_client.OPENROUTER_API_KEY", "test-key"), \
             patch("src.llm_client.OpenAI") as MockClient, \
             patch("src.llm_client.time") as mock_time:
            mock_instance = MockClient.return_value

            rate_error = RateLimitError(
                message="Rate limited",
                response=mock_response,
                body={"error": {"message": "rate limited"}}
            )

            # Fail twice, succeed on third attempt
            mock_instance.chat.completions.create.side_effect = [
                rate_error,
                rate_error,
                self._make_mock_response("Success after retry"),
            ]

            result = ask_llm("system", "user", max_retries=3)
            assert result == "Success after retry"
            assert mock_instance.chat.completions.create.call_count == 3


class TestFetchModels:
    """Test the fetch_available_models function."""

    def test_returns_empty_without_key(self):
        """Should return [] when API key is missing."""
        from src.llm_client import fetch_available_models

        with patch("src.llm_client.OPENROUTER_API_KEY", ""):
            result = fetch_available_models()
            assert result == []

    def test_returns_parsed_models(self):
        """Should parse the OpenRouter model list response."""
        from src.llm_client import fetch_available_models

        mock_data = {
            "data": [
                {
                    "id": "test/model-1",
                    "name": "Test Model 1",
                    "context_length": 4096,
                    "pricing": {"prompt": "0", "completion": "0"},
                },
                {
                    "id": "test/model-2",
                    "name": "Test Model 2",
                    "context_length": 8192,
                    "pricing": {"prompt": "0.001", "completion": "0.002"},
                },
            ]
        }

        with patch("src.llm_client.OPENROUTER_API_KEY", "test-key"), \
             patch("src.llm_client.httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_data
            mock_resp.raise_for_status = MagicMock()
            mock_httpx.get.return_value = mock_resp

            models = fetch_available_models()

            assert len(models) == 2
            assert models[0]["id"] == "test/model-1"
            assert models[0]["is_free"] is True
            assert models[1]["is_free"] is False

    def test_returns_empty_on_network_error(self):
        """Should return [] gracefully on network errors."""
        from src.llm_client import fetch_available_models

        with patch("src.llm_client.OPENROUTER_API_KEY", "test-key"), \
             patch("src.llm_client.httpx") as mock_httpx:
            mock_httpx.get.side_effect = Exception("Network error")

            result = fetch_available_models()
            assert result == []
