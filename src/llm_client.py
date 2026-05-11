"""
LLM Client - wrapper around OpenRouter API using the openai SDK.
Supports two-tier model routing: free model for simple queries, paid for complex.
"""

import logging
import time
from typing import List, Dict, Any, Optional

import httpx
from openai import OpenAI, RateLimitError, APITimeoutError, APIError

from src.config import (
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    LLM_MODEL_FREE,
    LLM_MODEL_PAID,
    LLM_MAX_TOKENS_SIMPLE,
    LLM_MAX_TOKENS_COMPLEX,
    LLM_TEMPERATURE,
)

logger = logging.getLogger(__name__)


def fetch_available_models() -> List[Dict[str, Any]]:
    """
    Fetch all models available on OpenRouter via GET /api/v1/models.

    Returns a list of dicts, each with:
        id, name, context_length, is_free, prompt_price, completion_price

    Returns [] on error (API key missing, network issue, etc.).
    """
    if not OPENROUTER_API_KEY:
        logger.warning("[MODELS] OPENROUTER_API_KEY not set — cannot fetch models")
        return []

    try:
        url = f"{OPENROUTER_BASE_URL}/models"
        headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}"}
        resp = httpx.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json().get("data", [])

        models = []
        for m in data:
            pricing = m.get("pricing", {})
            prompt_price = pricing.get("prompt", "?") 
            completion_price = pricing.get("completion", "?")
            is_free = str(prompt_price) == "0" and str(completion_price) == "0"
            models.append({
                "id":               m["id"],
                "name":             m.get("name", m["id"]),
                "context_length":   m.get("context_length", 0),
                "is_free":          is_free,
                "prompt_price":     prompt_price,
                "completion_price": completion_price,
            })

        free_count = sum(1 for m in models if m["is_free"])
        logger.info("[MODELS] Fetched %d models (%d free) from OpenRouter", len(models), free_count)
        return models

    except Exception:
        logger.exception("[MODELS] Failed to fetch models from OpenRouter")
        return []


def ask_llm(
    system_prompt: str,
    user_message: str,
    use_paid: bool = False,
    max_retries: int = 3,
    free_model: Optional[str] = None,
    paid_model: Optional[str] = None,
) -> str:
    """
    Send a message to OpenRouter and get a response.

    Args:
        system_prompt: System instructions
        user_message:  User's question or prompt
        use_paid:      False → free model + LLM_MAX_TOKENS_SIMPLE
                       True  → paid model + LLM_MAX_TOKENS_COMPLEX
        max_retries:   Retry attempts with exponential backoff
        free_model:    Override free model ID (falls back to LLM_MODEL_FREE)
        paid_model:    Override paid model ID (falls back to LLM_MODEL_PAID)

    Returns:
        LLM response text

    Raises:
        ValueError: If OPENROUTER_API_KEY is not configured
        APIError:   If all retries fail
    """
    if not OPENROUTER_API_KEY:
        raise ValueError(
            "OPENROUTER_API_KEY is not set. "
            "Please copy .env.example to .env and fill in your key."
        )

    model = (paid_model or LLM_MODEL_PAID) if use_paid else (free_model or LLM_MODEL_FREE)
    max_tokens = LLM_MAX_TOKENS_COMPLEX if use_paid else LLM_MAX_TOKENS_SIMPLE

    logger.info("[LLM] Calling model=%s | max_tokens=%d | use_paid=%s", model, max_tokens, use_paid)

    client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=OPENROUTER_API_KEY)

    last_error = None

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                temperature=LLM_TEMPERATURE,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_message},
                ],
                timeout=30,
            )

            choice = response.choices[0]

            if choice.finish_reason == "length":
                logger.warning(
                    "Response truncated (finish_reason='length'). "
                    "Model: %s | max_tokens: %d. "
                    "Consider raising LLM_MAX_TOKENS_COMPLEX or reducing chunk count.",
                    model, max_tokens,
                )

            usage = response.usage
            logger.info(
                "LLM call complete — model: %s | prompt_tokens: %s | completion_tokens: %s",
                model,
                usage.prompt_tokens if usage else "?",
                usage.completion_tokens if usage else "?",
            )

            return choice.message.content

        except RateLimitError as e:
            last_error = e
            wait_time = 2 ** attempt
            logger.warning("Rate limit hit. Waiting %ds before retry %d/%d...", wait_time, attempt + 1, max_retries)
            time.sleep(wait_time)

        except APITimeoutError as e:
            last_error = e
            wait_time = 2 ** attempt
            logger.warning("Request timeout. Retrying %d/%d...", attempt + 1, max_retries)
            time.sleep(wait_time)

        except APIError as e:
            logger.exception("[LLM] API error on attempt %d/%d | model=%s", attempt + 1, max_retries, model)
            raise

    logger.error("[LLM] All %d retries exhausted | model=%s | last_error=%s", max_retries, model, last_error)
    raise last_error


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    question = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "What is 2+2? Answer in one sentence."
    print(f"Question: {question}\n")

    try:
        print("Calling OpenRouter (free model)...")
        response = ask_llm("You are a helpful assistant. Answer concisely.", question)
        print(f"\n✓ Response:\n{response}")
    except ValueError as e:
        print(f"\n✗ Configuration error: {e}")
        print("Copy .env.example to .env and set OPENROUTER_API_KEY")
    except Exception as e:
        print(f"\n✗ Error: {e}")
