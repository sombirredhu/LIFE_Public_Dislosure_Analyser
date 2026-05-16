import streamlit as st
import pandas as pd
import logging
import json
import time
import tempfile
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

def _score_paid_model(model: dict) -> tuple:
    model_id   = model["id"].lower()
    model_name = model.get("name", "").lower()

    try:
        price_per_mtok = float(model.get("completion_price", 999)) * 1_000_000
    except (ValueError, TypeError):
        price_per_mtok = 999.0

    if price_per_mtok < 1.0:
        price_bucket = 0
    elif price_per_mtok < 3.0:
        price_bucket = 1
    elif price_per_mtok < 10.0:
        price_bucket = 2
    else:
        price_bucket = 3

    fast_keywords = ["flash", "turbo", "fast", "mini", "haiku", "instant", "lite"]
    speed_rank = 0 if any(k in model_id or k in model_name for k in fast_keywords) else 1

    reasoning_keywords = ["thinking", "reasoning", "reasoner", "r1", "o1", "o3", "deepseek"]
    reasoning_rank = 0 if any(k in model_id or k in model_name for k in reasoning_keywords) else 1

    context = model.get("context_length", 0) or 0

    return (price_bucket, speed_rank, reasoning_rank, -context, price_per_mtok)

def _model_label(model: dict) -> str:
    try:
        price_per_mtok = float(model.get("completion_price", 0)) * 1_000_000
        price_str = f"${price_per_mtok:.2f}/MTok"
    except (ValueError, TypeError):
        price_str = "?"

    ctx = model.get("context_length", 0) or 0
    ctx_str = f"{ctx // 1000}K ctx" if ctx >= 1000 else ""
    name = model.get("name", model["id"])

    parts = [name]
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

            paid_models = [m for m in models if not m["is_free"] and _parse_price(m) < 15.0]
            paid_models_sorted = sorted(paid_models, key=_score_paid_model)

            st.subheader("🤖 Model for Complex Queries")
            st.caption("**Default:** `openrouter/free` (auto-picks best free model)  \nPaid models sorted: Cheapest → Fastest → Best reasoning")

            all_options = ["openrouter/free"] + [m["id"] for m in paid_models_sorted]
            all_labels = ["🆓 openrouter/free  (auto best-free)"] + [f"💰 {_model_label(m)}" for m in paid_models_sorted]
            label_to_id = dict(zip(all_labels, all_options))

            prev = st.session_state.get("selected_model_label", all_labels[0])
            if prev not in all_labels:
                prev = all_labels[0]

            chosen_label = st.selectbox("Select model", options=all_labels, index=all_labels.index(prev), key="unified_model_select")
            chosen_id = label_to_id[chosen_label]
            st.session_state["selected_model_label"] = chosen_label

            if chosen_id == "openrouter/free":
                st.session_state["free_model"]  = "openrouter/free"
                st.session_state["paid_model"]  = "openrouter/free"
                st.info("🆓 Using free tier — ideal for simple queries.")
            else:
                st.session_state["free_model"]  = "openrouter/free"
                st.session_state["paid_model"]  = chosen_id
                sel = next((m for m in paid_models_sorted if m["id"] == chosen_id), None)
                if sel:
                    price = _parse_price(sel)
                    ctx = (sel.get("context_length") or 0) // 1000
                    st.success(f"💰 **Paid model selected**  \n`{sel.get('name', chosen_id)}`  \nOutput: **${price:.2f}/MTok** · Context: **{ctx}K tokens**")

            if st.button("🔄 Refresh Model List", width="stretch"):
                st.cache_data.clear()
                st.rerun()
        else:
            st.warning("Could not fetch models from OpenRouter. Using defaults from .env.")
            st.code(f"Free:  {LLM_MODEL_FREE}\nPaid: {LLM_MODEL_PAID}")
            st.session_state.setdefault("free_model", LLM_MODEL_FREE)
            st.session_state.setdefault("paid_model", LLM_MODEL_PAID)

        st.divider()
        st.caption("Model list cached for 1 hour.")

def _warm_up_models():
    collection = get_or_create_collection()
    logger.info("[WARMUP] ChromaDB ready (embeddings via OpenRouter API)")
    return None, collection

def _get_models():
    return fetch_available_models()

def _auto_reindex_if_needed():
    if st.session_state.get("_auto_reindex_done"):
        return
    st.session_state["_auto_reindex_done"] = True

    stats = get_collection_stats()
    if stats["total_chunks"] > 0:
        return

    pdf_dir = Path(PDF_INPUT_DIR)
    pdf_dir.mkdir(parents=True, exist_ok=True)
    pdf_files = list(pdf_dir.glob("*.pdf"))

    if not pdf_files:
        return

    logger.info("[AUTO-REINDEX] ChromaDB empty but %d PDFs found — rebuilding index", len(pdf_files))

    warning_placeholder = st.empty()
    progress_placeholder = st.empty()
    status_placeholder = st.empty()
    
    warning_placeholder.warning(f"⚡ **Auto-rebuilding index** — ChromaDB was empty but {len(pdf_files)} PDF(s) found in `data/pdfs/`. This happens after a server restart. Please wait...")
    
    for idx, pdf_file in enumerate(pdf_files, 1):
        progress_placeholder.progress(idx / len(pdf_files))
        status_placeholder.markdown(f"📄 Indexing **{pdf_file.name}** ({idx}/{len(pdf_files)})...")
        try:
            result = ingest_pdf(str(pdf_file), force_reindex=True)
            if result["status"] == "success":
                logger.info("[AUTO-REINDEX] ✓ %s — %d chunks", pdf_file.name, result["chunks_created"])
            else:
                logger.warning("[AUTO-REINDEX] ⚠ %s — %s", pdf_file.name, result["message"])
        except Exception as e:
            logger.exception("[AUTO-REINDEX] ✗ %s failed", pdf_file.name)
    
    # Clear all placeholders
    warning_placeholder.empty()
    progress_placeholder.empty()
    status_placeholder.empty()
    
    logger.info("[AUTO-REINDEX] Complete — %d files processed", len(pdf_files))
