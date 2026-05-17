import streamlit as st
import pandas as pd
import logging
import json
import time
import tempfile
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config import *
from src.embedder import get_or_create_collection, get_collection_stats
from src.ingestor import ingest_pdf
from src.llm_client import fetch_available_models
from src.logging_config import setup_logging

logger = logging.getLogger(__name__)

def _check_password() -> bool:
    """Check password authentication using session state only."""
    try: 
        expected = st.secrets["APP_PASSWORD"]
    except (KeyError, FileNotFoundError): 
        # No password configured, allow access
        return True
    
    # Check if already authenticated in this session
    if st.session_state.get("authenticated", False): 
        return True
    
    # Show login form
    st.markdown(f"### 🔒 Enter password to access **{APP_TITLE}**")
    
    # Use a form to handle enter key properly
    with st.form("login_form"):
        pwd = st.text_input("Password", type="password", key="auth_password_input")
        submitted = st.form_submit_button("Login", type="primary", use_container_width=True)
        
        if submitted:
            if pwd == expected:
                st.session_state["authenticated"] = True
                st.success("✅ Login successful!")
                time.sleep(0.3)
                st.rerun()
            else: 
                st.error("❌ Incorrect password.")
    
    st.info("ℹ️ **Note:** You'll need to login again after refreshing the browser.")
    st.stop()
    return False

def render_css():
    st.markdown("""
    <style>
        .main-header {
            font-size: 2.5rem;
            font-weight: bold;
            color: var(--primary-color, #1f77b4);
            margin-bottom: 0.5rem;
        }
        .confidence-high {
            background-color: rgba(40, 167, 69, 0.2);
            color: #28a745;
            padding: 0.25rem 0.5rem;
            border-radius: 0.25rem;
            font-weight: bold;
        }
        .confidence-medium {
            background-color: rgba(255, 193, 7, 0.2);
            color: #ffc107;
            padding: 0.25rem 0.5rem;
            border-radius: 0.25rem;
            font-weight: bold;
        }
        .confidence-low {
            background-color: rgba(220, 53, 69, 0.2);
            color: #dc3545;
            padding: 0.25rem 0.5rem;
            border-radius: 0.25rem;
            font-weight: bold;
        }
    </style>
    """, unsafe_allow_html=True)

def render_header():
    st.markdown(f'<div class="main-header">📊 {APP_TITLE}</div>', unsafe_allow_html=True)
    st.markdown("*RAG-powered multi-company financial report analyzer*")
    st.markdown("---")

def _categorize_model(model: dict) -> str:
    """Categorize models into Fast, Light, Balance, or Heavy."""
    model_id = model["id"].lower()
    model_name = model.get("name", "").lower()
    
    # Heavy: Most capable models for very complex work
    heavy_keywords = ["opus", "o1", "o3", "reasoning", "reasoner", "r1", "deepseek-r1", "gpt-4-turbo", "claude-3-opus"]
    if any(k in model_id or k in model_name for k in heavy_keywords):
        return "heavy"
    
    # Fast: Models explicitly marked as "fast"
    if re.search(r"\bfast\b", f"{model_id} {model_name}"):
        return "ultra_light"
    
    # Light: Fast, efficient models
    light_keywords = ["haiku", "flash", "mini", "instant", "lite", "gemini-2.0-flash", "gpt-4o-mini"]
    if any(k in model_id or k in model_name for k in light_keywords):
        return "light"
    
    # Balance: Balanced models for moderately complex work (default)
    return "balance"

def _is_useful_for_financial_rag(model: dict) -> bool:
    """Keep only analysis-oriented text models suitable for financial RAG."""
    model_id = model.get("id", "").lower()
    model_name = model.get("name", "").lower()
    combined = f"{model_id} {model_name}"

    # Exclude modalities and task-specific families that are not useful for this RAG benchmark.
    excluded_keywords = [
        "image", "vision", "audio", "speech", "transcribe", "tts", "whisper",
        "embedding", "rerank", "moderation", "guard", "safety",
        "code", "coder", "diffusion", "sdxl", "stable-diffusion",
        "preview", "experimental", "roleplay", "story", "creative"
    ]
    if any(k in combined for k in excluded_keywords):
        return False

    # Exclude common non-general or niche families that are usually poor for finance analysis.
    excluded_prefixes = [
        "gryphe/", "undi95/", "neversleep/", "sao10k/", "mancer/",
        "infermatic/", "koboldai/", "nothingiisreal/", "alpindale/",
    ]
    if any(model_id.startswith(prefix) for prefix in excluded_prefixes):
        return False

    # Prefer models explicitly positioned for chat/instruct/reasoning/general assistant use.
    include_keywords = [
        "chat", "instruct", "assistant", "reason", "reasoning", "think",
        "gpt", "claude", "gemini", "llama", "qwen", "mistral", "command", "deepseek",
        "fast",
    ]
    if not any(k in combined for k in include_keywords):
        return False

    # Require at least moderate context for meaningful multi-chunk financial comparisons.
    context_length = model.get("context_length", 0) or 0
    if context_length < 32000:
        return False

    return True

def _score_paid_model(model: dict) -> tuple:
    """Score models for sorting: Category → Cheapest → Fastest → Best reasoning."""
    model_id = model["id"].lower()
    model_name = model.get("name", "").lower()
    
    # Category ranking (fast=0, light=1, balance=2, heavy=3)
    category = _categorize_model(model)
    category_rank = {"ultra_light": 0, "light": 1, "balance": 2, "heavy": 3}[category]
    
    # Price calculation
    try:
        price_per_mtok = float(model.get("completion_price", 999)) * 1_000_000
    except (ValueError, TypeError):
        price_per_mtok = 999.0
    
    try:
        prompt_price_per_mtok = float(model.get("prompt_price", 999)) * 1_000_000
    except (ValueError, TypeError):
        prompt_price_per_mtok = 999.0
    
    # Speed ranking (lower is faster)
    fast_keywords = ["flash", "turbo", "fast", "mini", "haiku", "instant", "lite"]
    speed_rank = 0 if any(k in model_id or k in model_name for k in fast_keywords) else 1
    
    # Reasoning capability (lower is better)
    reasoning_keywords = ["thinking", "reasoning", "reasoner", "r1", "o1", "o3", "deepseek"]
    reasoning_rank = 0 if any(k in model_id or k in model_name for k in reasoning_keywords) else 1
    
    context = model.get("context_length", 0) or 0
    
    # Sort by: Category → Exact output price → Exact input price → Speed → Reasoning → Context
    return (category_rank, price_per_mtok, prompt_price_per_mtok, speed_rank, reasoning_rank, -context, model_name)

def _model_family_key(model_id: str) -> str:
    """Normalize model id into a family key to compare old/new variants."""
    key = model_id.lower().strip()
    key = key.split(":")[0]
    key = re.sub(r"[-_]?(\d{4}[-_]?\d{2}[-_]?\d{2})$", "", key)  # trailing date
    key = re.sub(r"[-_]?v?\d+(\.\d+)*$", "", key)  # trailing versions like -2.5 / v3
    key = re.sub(r"[-_](latest|stable|preview|beta|alpha|exp)$", "", key)
    return key

def _model_version_score(model: dict) -> tuple:
    """Higher score means newer model variant."""
    model_id = model.get("id", "").lower()
    model_name = model.get("name", "").lower()
    combined = f"{model_id} {model_name}"

    date_match = re.search(r"(20\d{2})[-_]?([01]\d)[-_]?([0-3]\d)", combined)
    date_score = int("".join(date_match.groups())) if date_match else 0

    nums = re.findall(r"\d+(?:\.\d+)?", combined)
    numeric_score = max([float(n) for n in nums], default=0.0)

    preview_penalty = -1 if ("preview" in combined or "beta" in combined or "alpha" in combined) else 0
    ctx_score = model.get("context_length", 0) or 0

    return (date_score, numeric_score, preview_penalty, ctx_score)

def _latest_paid_models_only(models: List[dict]) -> List[dict]:
    """Keep only latest model per family for paid models."""
    grouped: Dict[str, List[dict]] = {}
    for m in models:
        fam = _model_family_key(m.get("id", ""))
        grouped.setdefault(fam, []).append(m)

    latest = []
    for fam_models in grouped.values():
        latest.append(max(fam_models, key=_model_version_score))
    return latest

def _model_label(model: dict) -> str:
    """Generate a display label for a model with category, price, and context."""
    try:
        price_per_mtok = float(model.get("completion_price", 0)) * 1_000_000
        price_str = f"${price_per_mtok:.2f}/MTok"
    except (ValueError, TypeError):
        price_str = "?"

    ctx = model.get("context_length", 0) or 0
    ctx_str = f"{ctx // 1000}K ctx" if ctx >= 1000 else ""
    name = model.get("name", model["id"])
    
    # Add category badge
    category = _categorize_model(model)
    category_emoji = {"ultra_light": "⚡⚡", "light": "⚡", "balance": "⚖️", "heavy": "🔥"}
    category_label = {"ultra_light": "Fast", "light": "Light", "balance": "Balance", "heavy": "Heavy"}
    badge = f"{category_emoji[category]} {category_label[category]}"

    parts = [badge, name]
    if price_str:
        parts.append(price_str)
    if ctx_str:
        parts.append(ctx_str)
    return " · ".join(parts)

def render_sidebar():
    with st.sidebar:
        st.header("⚙️ Model Settings")
        models = _get_models()

        if models:
            def _parse_price(model) -> float:
                try:
                    return float(model.get("completion_price", 999)) * 1_000_000
                except (ValueError, TypeError):
                    return 999.0

            useful_models = [m for m in models if _is_useful_for_financial_rag(m)]
            free_models = sorted([m for m in useful_models if m["is_free"]], key=lambda m: (m.get("name", m["id"]).lower(), m["id"].lower()))
            paid_models_raw = [m for m in useful_models if not m["is_free"] and _parse_price(m) < 15.0]
            paid_models = _latest_paid_models_only(paid_models_raw)

            ultra_light_sorted = sorted([m for m in paid_models if _categorize_model(m) == "ultra_light"], key=lambda m: _score_paid_model(m)[1:])
            light_sorted = sorted([m for m in paid_models if _categorize_model(m) == "light"], key=lambda m: _score_paid_model(m)[1:])
            balance_sorted = sorted([m for m in paid_models if _categorize_model(m) == "balance"], key=lambda m: _score_paid_model(m)[1:])
            heavy_sorted = sorted([m for m in paid_models if _categorize_model(m) == "heavy"], key=lambda m: _score_paid_model(m)[1:])

            st.subheader("🤖 Model Selection")

            category_options = ["Free", "Light", "Balance", "Heavy", "Fast"]
            prev_category = st.session_state.get("selected_category", "Free")
            if prev_category not in category_options:
                prev_category = "Free"

            selected_category = st.selectbox(
                "1️⃣ Select Category",
                options=category_options,
                index=category_options.index(prev_category),
                key="category_select"
            )
            st.session_state["selected_category"] = selected_category

            if selected_category == "Free":
                category_models = free_models
                category_name = "Free"
                chosen_key = "selected_free_model_label"
            else:
                if selected_category == "Light":
                    category_models = light_sorted
                elif selected_category == "Balance":
                    category_models = balance_sorted
                elif selected_category == "Heavy":
                    category_models = heavy_sorted
                else:
                    category_models = ultra_light_sorted
                category_name = selected_category
                chosen_key = "selected_paid_model_label"

            if not category_models:
                st.warning(f"No models available in {category_name} category.")
            else:
                if selected_category != "Free":
                    st.caption("Sorting: Cheapest → Fastest → Best reasoning")

                model_labels = [_model_label(m) for m in category_models]
                label_to_model = dict(zip(model_labels, category_models))

                prev_label = st.session_state.get(chosen_key, model_labels[0])
                if prev_label not in model_labels:
                    prev_label = model_labels[0]

                chosen_label = st.selectbox(
                    "2️⃣ Select Model",
                    options=model_labels,
                    index=model_labels.index(prev_label),
                    key="model_select_in_category"
                )
                st.session_state[chosen_key] = chosen_label

                chosen_model = label_to_model[chosen_label]
                chosen_id = chosen_model["id"]
                st.session_state["selected_model_label"] = chosen_id

                if selected_category == "Free":
                    st.session_state["free_model"] = chosen_id
                    st.session_state["paid_model"] = chosen_id
                else:
                    st.session_state["free_model"] = "openrouter/free"
                    st.session_state["paid_model"] = chosen_id

                price = _parse_price(chosen_model)
                ctx = (chosen_model.get("context_length") or 0) // 1000
                st.success(
                    f"✅ Model Selected: `{chosen_model.get('name', chosen_id)}`  \n"
                    f"Category: **{category_name}** · Output: **${price:.2f}/MTok** · Context: **{ctx}K tokens**"
                )

            if st.button("🔄 Refresh Model List", use_container_width=True):
                st.cache_data.clear()
                st.rerun()
        else:
            st.warning("Could not fetch models from OpenRouter. Using defaults from .env.")
            st.code(f"Free:  {LLM_MODEL_FREE}\nPaid: {LLM_MODEL_PAID}")
            st.session_state.setdefault("free_model", LLM_MODEL_FREE)
            st.session_state.setdefault("paid_model", LLM_MODEL_PAID)

        st.divider()
        st.caption("Model list cached for 1 hour.")
        st.caption("Filtered to text models suitable for financial comparison and summarization.")

def _warm_up_models():
    collection = get_or_create_collection()
    logger.info("[WARMUP] ChromaDB ready (embeddings via OpenRouter API)")
    return None, collection

@st.cache_data(ttl=3600)  # Cache for 1 hour
def _get_models():
    return fetch_available_models()

def _auto_reindex_if_needed():
    """Auto-reindex on start is disabled to prevent timeouts and crashes on Streamlit Cloud."""
    return
