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
from src.rag_pipeline import answer_question
from src.ingestor import ingest_pdf
from src.embedder import *

from src.logging_config import setup_logging

logger = logging.getLogger(__name__)
def _check_password() -> bool:
    """
    Authentication gate — blocks the app until the correct password is entered.
    Password is stored in .streamlit/secrets.toml (local) or Streamlit Cloud Secrets.
    If no APP_PASSWORD secret is configured, authentication is skipped (dev mode).
    """
    # If no password configured, skip auth (allows easy local dev)
    try:
        expected = st.secrets["APP_PASSWORD"]
    except (KeyError, FileNotFoundError):
        return True  # No auth configured — allow access

    # Already authenticated this session
    if st.session_state.get("authenticated"):
        return True

    st.markdown("### 🔒 Authentication Required")
    st.markdown(f"Enter the password to access **{APP_TITLE}**")

    password = st.text_input("Password", type="password", key="auth_password_input")

    if st.button("Login", type="primary"):
        if password == expected:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("❌ Incorrect password. Please try again.")

    st.stop()  # Block everything below until authenticated
    return False  # unreachable, but keeps type checker happy



def render_css():
    """Apply custom CSS to the app."""
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
    """Render app header."""
    st.markdown(f'<div class="main-header">📊 {APP_TITLE}</div>', unsafe_allow_html=True)
    st.markdown("*RAG-powered multi-company financial report analyzer*")
    st.markdown("---")



def render_sidebar():
    """Sidebar: live model selector with free/paid split."""
    with st.sidebar:
        st.header("⚙️ Model Settings")

        models = _get_models()

        if models:
            free_ids  = ["openrouter/free"] + [m["id"] for m in models if m["is_free"] and m["id"] != "openrouter/free"]
            
            # ── Filter paid models: ONLY show models with output cost < $3/MTok ──
            # This filters out expensive models like:
            # - Claude Opus ($25/MTok output)
            # - GPT-5.x ($15-75/MTok output)
            # - Claude Sonnet 4.6 ($15/MTok output)
            # Keeps affordable models like:
            # - DeepSeek ($0.28-2.19/MTok output)
            # - Gemini Flash ($0.40-1.50/MTok output)
            # - Claude Haiku ($5/MTok output - but excluded by $3 limit)
            
            def is_affordable_model(model):
                """
                Only show Google models with output cost under $3 per million tokens.
                Other models are not working, so we filter them out.
                """
                # Check output/completion price
                try:
                    # First check if it's a Google model
                    model_id_lower = model["id"].lower()
                    model_name_lower = model.get("name", "").lower()
                    
                    # Only allow Google models (google/ prefix or "google" in name)
                    if not ("google/" in model_id_lower or "google" in model_name_lower or "gemini" in model_id_lower):
                        return False
                    
                    completion_price = model.get("completion_price", "999")
                    # Handle both string and numeric prices
                    if isinstance(completion_price, str):
                        # Remove any currency symbols or extra text
                        completion_price = completion_price.replace("$", "").strip()
                        if completion_price == "?" or not completion_price:
                            return False
                    completion_price = float(completion_price)
                    
                    # OpenRouter returns price per token, convert to per-MTok for comparison
                    price_per_mtok = completion_price * 1_000_000
                    
                    # Only show if output cost is under $3/MTok
                    if price_per_mtok >= 3.0:
                        return False
                    
                    return True
                except (ValueError, TypeError):
                    # If we can't parse the price, exclude it to be safe
                    return False
            
            def get_model_sort_key(model):
                """
                Sort models by priority:
                1. Fast models first (highest priority)
                2. Reasoning models second
                3. Then by price (cheapest first)
                
                Returns tuple: (fast_priority, reasoning_priority, price)
                Lower values = higher priority in sort
                """
                model_id_lower = model["id"].lower()
                model_name_lower = model.get("name", "").lower()
                
                # Priority 1: Fast models (0 = fast, 1 = not fast)
                is_fast = 0 if ("fast" in model_id_lower or "fast" in model_name_lower) else 1
                
                # Priority 2: Reasoning models (0 = reasoning, 1 = not reasoning)
                is_reasoning = 0 if any(keyword in model_id_lower or keyword in model_name_lower 
                                       for keyword in ["reasoner", "reasoning", "r1", "o1", "o3", "deepseek"]) else 1
                
                # Priority 3: Price (lower is better)
                try:
                    completion_price = float(model.get("completion_price", 999))
                    price_per_mtok = completion_price * 1_000_000
                except (ValueError, TypeError):
                    price_per_mtok = 999.0  # Put unparseable prices at the end
                
                return (is_fast, is_reasoning, price_per_mtok)
            
            # Filter affordable models and sort by: fast > reasoning > cheap
            affordable_models = [m for m in models if not m["is_free"] and is_affordable_model(m)]
            affordable_models_sorted = sorted(affordable_models, key=get_model_sort_key)
            paid_ids = [m["id"] for m in affordable_models_sorted]

            # ── Free model ────────────────────────────────────────────────
            st.subheader("🆓 Free Model")
            # Always default to openrouter/free (best free model auto-selection)
            free_default = "openrouter/free"
            free_idx = free_ids.index(free_default) if free_default in free_ids else 0
            selected_free = st.selectbox(
                "Select free model",
                options=free_ids,
                index=free_idx,
                help="openrouter/free automatically selects the best available free model",
                key="free_model_select",
            )
            st.session_state["free_model"] = selected_free

            # ── Paid model (GOOGLE ONLY) ──────────────────────────────
            st.subheader("💰 Paid Model (Google Only)")
            st.caption("🔒 Only Google models <$3/MTok • Sorted: Fast → Reasoning → Cheapest")
            
            # Auto-select best model (first in sorted list) if no preference set
            if paid_ids:
                # If user hasn't selected or default not in list, use best model (first)
                paid_default = st.session_state.get("paid_model", LLM_MODEL_PAID)
                if paid_default not in paid_ids:
                    paid_default = paid_ids[0]  # Best model (fast/reasoning/cheap)
                paid_idx = paid_ids.index(paid_default)
            else:
                paid_idx = 0
                
            selected_paid = st.selectbox(
                "Select paid model",
                options=paid_ids,
                index=paid_idx,
                help="Google models only (others not working) • Sorted: Fast → Reasoning → Cheapest • All <$3/MTok",
                key="paid_model_select",
            )
            st.session_state["paid_model"] = selected_paid
            
            # Show info about selected model
            if paid_ids:
                selected_model = next((m for m in affordable_models_sorted if m["id"] == selected_paid), None)
                if selected_model:
                    # Convert price from per-token to per-million-tokens for display
                    try:
                        completion_price = float(selected_model['completion_price'])
                        # OpenRouter returns price per token, multiply by 1M for per-MTok display
                        price_per_mtok = completion_price * 1_000_000
                        st.caption(f"💡 {selected_model['name']} • Output: ${price_per_mtok:.2f}/MTok")
                    except (ValueError, TypeError):
                        st.caption(f"💡 {selected_model['name']}")

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




def _warm_up_models():
    """Pre-load the embedding model and ChromaDB connection on first run.
    Uses st.cache_resource so it survives Streamlit reruns."""
    model = get_embedding_model()
    collection = get_or_create_collection()
    logger.info("[WARMUP] Embedding model + ChromaDB ready")
    return model, collection


def _get_models():
    """Fetch and cache OpenRouter model list for 1 hour."""
    return fetch_available_models()



def _auto_reindex_if_needed():
    """
    Auto-reindex on startup: if ChromaDB is empty but data/pdfs/ has PDF files,
    automatically re-ingest them. This handles Streamlit Community Cloud restarts
    where the ephemeral filesystem wipes vectordb/ but PDFs in the repo survive.
    """
    # Only run once per session
    if st.session_state.get("_auto_reindex_done"):
        return
    st.session_state["_auto_reindex_done"] = True

    stats = get_collection_stats()
    if stats["total_chunks"] > 0:
        return  # DB already has data, nothing to do

    # Check if there are PDFs waiting to be indexed
    pdf_dir = Path(PDF_INPUT_DIR)
    pdf_dir.mkdir(parents=True, exist_ok=True)
    pdf_files = list(pdf_dir.glob("*.pdf"))

    if not pdf_files:
        return  # No PDFs either, nothing to rebuild

    # --- Auto-reindex ---
    logger.info("[AUTO-REINDEX] ChromaDB empty but %d PDFs found — rebuilding index", len(pdf_files))

    banner = st.container()
    with banner:
        st.warning(
            f"⚡ **Auto-rebuilding index** — ChromaDB was empty but {len(pdf_files)} PDF(s) found in `data/pdfs/`. "
            f"This happens after a server restart. Please wait..."
        )
        progress = st.progress(0)
        status = st.empty()

        for idx, pdf_file in enumerate(pdf_files, 1):
            status.markdown(f"📄 Indexing **{pdf_file.name}** ({idx}/{len(pdf_files)})...")
            try:
                result = ingest_pdf(str(pdf_file), force_reindex=True)
                if result["status"] == "success":
                    logger.info("[AUTO-REINDEX] ✓ %s — %d chunks", pdf_file.name, result["chunks_created"])
                else:
                    logger.warning("[AUTO-REINDEX] ⚠ %s — %s", pdf_file.name, result["message"])
            except Exception as e:
                logger.exception("[AUTO-REINDEX] ✗ %s failed", pdf_file.name)
            progress.progress(idx / len(pdf_files))

        progress.empty()
        status.empty()
        st.success(f"✅ Auto-reindex complete — {len(pdf_files)} PDF(s) rebuilt into ChromaDB.")
        logger.info("[AUTO-REINDEX] Complete — %d files processed", len(pdf_files))



