import logging
import time
from typing import List, Dict, Any, Optional
import httpx
from openai import OpenAI, RateLimitError, APITimeoutError, APIError
from src.config import (
    OPENROUTER_API_KEY, OPENROUTER_BASE_URL,
    LLM_MODEL_FREE, LLM_MODEL_PAID,
    LLM_MAX_TOKENS_SIMPLE, LLM_MAX_TOKENS_COMPLEX,
    LLM_TEMPERATURE,
)

logger = logging.getLogger(__name__)

def fetch_available_models() -> List[Dict[str, Any]]:
    if not OPENROUTER_API_KEY: return []
    try:
        resp = httpx.get(f"{OPENROUTER_BASE_URL}/models", headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"}, timeout=10)
        resp.raise_for_status()
        models = []
        for m in resp.json().get("data", []):
            p, c = m.get("pricing", {}).get("prompt", "?"), m.get("pricing", {}).get("completion", "?")
            models.append({"id": m["id"], "name": m.get("name", m["id"]), "context_length": m.get("context_length", 0), "is_free": str(p) == "0" and str(c) == "0", "prompt_price": p, "completion_price": c})
        return models
    except Exception:
        logger.exception("Failed to fetch models")
        return []

_openai_client = None
_openai_client_sig = None

def _get_openai_client() -> OpenAI:
    global _openai_client, _openai_client_sig
    current_sig = (OPENROUTER_BASE_URL, OPENROUTER_API_KEY, id(OpenAI))
    if _openai_client is None or _openai_client_sig != current_sig:
        if not OPENROUTER_API_KEY: raise ValueError("OPENROUTER_API_KEY is not set")
        _openai_client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=OPENROUTER_API_KEY)
        _openai_client_sig = current_sig
    return _openai_client

def ask_llm(system_prompt: str, user_message: str, use_paid: bool = False, max_retries: int = 3, free_model: Optional[str] = None, paid_model: Optional[str] = None) -> str:
    model = (paid_model or LLM_MODEL_PAID) if use_paid else (free_model or LLM_MODEL_FREE)
    max_tokens = LLM_MAX_TOKENS_COMPLEX if use_paid else LLM_MAX_TOKENS_SIMPLE
    client = _get_openai_client()
    last_err = None
    
    for attempt in range(max_retries):
        try:
            logger.debug(f"[LLM] Calling {model} (attempt {attempt+1}/{max_retries}, max_tokens={max_tokens})")
            start_time = time.time()
            
            res = client.chat.completions.create(
                model=model, 
                max_tokens=max_tokens, 
                temperature=LLM_TEMPERATURE, 
                messages=[
                    {"role": "system", "content": system_prompt}, 
                    {"role": "user", "content": user_message}
                ], 
                timeout=60  # Increased from 30 to 60 seconds
            )
            
            duration = time.time() - start_time
            logger.info(f"[LLM] Success: {model} responded in {duration:.2f}s")
            try:
                fr = res.choices[0].finish_reason
                if fr == "length":
                    logger.warning("[LLM] Response reached output length limit (finish_reason='length')")
            except Exception:
                pass
            return res.choices[0].message.content
            
        except (RateLimitError, APITimeoutError) as e:
            last_err = e
            wait_time = 2 ** attempt
            logger.warning(f"[LLM] {type(e).__name__} on attempt {attempt+1}, waiting {wait_time}s before retry")
            time.sleep(wait_time)
            
        except APIError as e:
            logger.exception("LLM API error | model=%s", model)
            raise
    
    logger.error(f"[LLM] Failed after {max_retries} attempts")
    raise last_err
