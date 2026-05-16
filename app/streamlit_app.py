"""
Streamlit Web UI for Insurance PD Report Analyzer.
Three tabs: Ask Questions, Upload Reports, Index Status.
"""

import logging
import sys
import tempfile
from pathlib import Path
import streamlit as st
import pandas as pd
from datetime import datetime
import time

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.logging_config import setup_logging
setup_logging()  # initialise file + console handlers before any other import logs

from src.rag_pipeline import answer_question
from src.ingestor import ingest_pdf
from src.embedder import get_collection_stats, delete_file_chunks, get_or_create_collection, get_indexed_companies, get_available_quarters, get_available_fys
from src.llm_client import fetch_available_models
from src.config import APP_TITLE, MAX_UPLOAD_SIZE_MB, LLM_MODEL_FREE, LLM_MODEL_PAID
from src.definitions_manager import (
    add_page_definition, add_calculation, delete_page_definition, 
    delete_calculation, get_all_definitions, search_definitions, merge_with_pdf_definitions
)
from src.vector_visualizer import visualize_vectors, get_visualization_stats
from src.background_worker import get_worker, JobStatus

logger = logging.getLogger(__name__)


@st.cache_data(ttl=3600, show_spinner=False)
def _get_models():
    """Fetch and cache OpenRouter model list for 1 hour."""
    return fetch_available_models()


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
                """Only show models with output cost under $3 per million tokens."""
                # Check output/completion price
                try:
                    completion_price = model.get("completion_price", "999")
                    # Handle both string and numeric prices
                    if isinstance(completion_price, str):
                        # Remove any currency symbols or extra text
                        completion_price = completion_price.replace("$", "").strip()
                        if completion_price == "?" or not completion_price:
                            return False
                    completion_price = float(completion_price)
                    
                    # Only show if output cost is under $3/MTok
                    if completion_price >= 3.0:
                        return False
                    
                    return True
                except (ValueError, TypeError):
                    # If we can't parse the price, exclude it to be safe
                    return False
            
            def get_reasoning_score(model):
                """
                Assign reasoning score to models for auto-selection.
                Higher score = better reasoning capability.
                """
                model_id_lower = model["id"].lower()
                
                # Tier 1: Dedicated reasoning models (score 90-100)
                if "reasoner" in model_id_lower or "reasoning" in model_id_lower:
                    return 95
                if "r1" in model_id_lower or "o1" in model_id_lower or "o3" in model_id_lower:
                    return 90
                
                # Tier 2: Advanced models with good reasoning (score 70-89)
                if "deepseek" in model_id_lower and "v3" in model_id_lower:
                    return 85
                if "gemini" in model_id_lower and ("pro" in model_id_lower or "ultra" in model_id_lower):
                    return 80
                if "qwen" in model_id_lower and ("turbo" in model_id_lower or "plus" in model_id_lower):
                    return 75
                
                # Tier 3: Standard models (score 50-69)
                if "deepseek" in model_id_lower:
                    return 65
                if "gemini" in model_id_lower and "flash" in model_id_lower:
                    return 60
                if "llama" in model_id_lower and "3" in model_id_lower:
                    return 55
                
                # Tier 4: Basic models (score <50)
                return 40
            
            # Filter affordable models and sort by reasoning score (best first)
            affordable_models = [m for m in models if not m["is_free"] and is_affordable_model(m)]
            affordable_models_sorted = sorted(affordable_models, key=get_reasoning_score, reverse=True)
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

            # ── Paid model (AFFORDABLE ONLY) ──────────────────────────────
            st.subheader("💰 Paid Model (Affordable)")
            st.caption("🔒 Only models with output cost <$3/MTok shown • Sorted by reasoning quality")
            
            # Auto-select best reasoning model (first in sorted list) if no preference set
            if paid_ids:
                # If user hasn't selected or default not in list, use best reasoning model (first)
                paid_default = st.session_state.get("paid_model", LLM_MODEL_PAID)
                if paid_default not in paid_ids:
                    paid_default = paid_ids[0]  # Best reasoning model
                paid_idx = paid_ids.index(paid_default)
            else:
                paid_idx = 0
                
            selected_paid = st.selectbox(
                "Select paid model",
                options=paid_ids,
                index=paid_idx,
                help="Models sorted by reasoning quality (best first) • All under $3/MTok output",
                key="paid_model_select",
            )
            st.session_state["paid_model"] = selected_paid
            
            # Show info about selected model
            if paid_ids:
                selected_model = next((m for m in affordable_models_sorted if m["id"] == selected_paid), None)
                if selected_model:
                    st.caption(f"💡 {selected_model['name']} • Output: ${selected_model['completion_price']}/MTok")

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


# Page config
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 0.5rem;
    }
    .confidence-high {
        background-color: #d4edda;
        color: #155724;
        padding: 0.25rem 0.5rem;
        border-radius: 0.25rem;
        font-weight: bold;
    }
    .confidence-medium {
        background-color: #fff3cd;
        color: #856404;
        padding: 0.25rem 0.5rem;
        border-radius: 0.25rem;
        font-weight: bold;
    }
    .confidence-low {
        background-color: #f8d7da;
        color: #721c24;
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


def render_tab_ask_question():
    """Tab 1: Ask a Question."""
    st.header("💬 Ask a Question")
    
    # Check if data exists
    stats = get_collection_stats()
    if stats['total_chunks'] == 0:
        st.warning("⚠️ No data indexed yet. Please upload PDF files in the 'Upload Reports' tab first.")
        return
    
    # Show quick stats
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Indexed Files", stats['unique_files'])
    with col2:
        st.metric("Total Chunks", stats['total_chunks'])
    with col3:
        st.metric("Companies", len(stats['chunks_by_company']))
    
    st.markdown("---")
    
    # Quick help for definition commands
    with st.expander("💡 Quick Commands for Definitions"):
        st.markdown("""
        You can manage definitions directly from chat:
        
        **Add Page Definition:**
        - `define GWP as L-4`
        - `add definition: Premium Schedule = L-5`
        
        **Add Calculation:**
        - `define Margin % = Margin / ANP`
        - `add calculation: ROE = Net Profit / Equity`
        
        **Search Definition:**
        - `what is GWP?`
        - `define GWP` (without adding anything)
        
        Or use the **Definitions** tab for full management interface.
        """)
    
    # Question input
    question = st.text_area(
        "Enter your question:",
        placeholder="Example: Which company had the highest gross written premium in Q1 FY25?",
        height=100
    )
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        available_companies = get_indexed_companies()
        company_filter = st.multiselect(
            "Filter by Company (optional)",
            options=available_companies,
            default=[]
        )
    
    with col2:
        available_quarters = get_available_quarters()
        quarter_options = ["All"] + available_quarters if available_quarters else ["All"]
        quarter_filter = st.selectbox(
            "Filter by Quarter (optional)",
            options=quarter_options,
            index=0
        )
    
    with col3:
        available_fys = get_available_fys()
        fy_options = ["All"] + available_fys if available_fys else ["All"]
        fy_filter = st.selectbox(
            "Filter by FY (optional)",
            options=fy_options,
            index=0
        )
    
    # Submit button
    if st.button("🔍 Get Answer", type="primary", use_container_width=True):
        if not question.strip():
            st.error("Please enter a question.")
            return
        
        # Check if this is a definition command
        def_result = _process_definition_command(question)
        if def_result:
            if def_result["success"]:
                st.success(def_result["message"])
            else:
                st.error(def_result["message"])
            return
        
        # Build filters
        filters = {}
        if company_filter:
            if len(company_filter) == 1:
                filters["company_code"] = company_filter[0]
            else:
                filters["company_code"] = {"$in": company_filter}
        
        if quarter_filter != "All":
            filters["quarter"] = quarter_filter
        
        if fy_filter != "All":
            filters["fy"] = fy_filter
        
        # Get answer
        with st.spinner("🤔 Thinking..."):
            try:
                result = answer_question(
                    question,
                    filters=filters if filters else None,
                    free_model=st.session_state.get("free_model"),
                    paid_model=st.session_state.get("paid_model"),
                )
                
                # Display answer
                st.markdown("### 📝 Answer")
                
                # Confidence badge
                confidence = result['confidence']
                if confidence == 'high':
                    badge_class = 'confidence-high'
                    badge_text = '✓ High Confidence'
                elif confidence == 'medium':
                    badge_class = 'confidence-medium'
                    badge_text = '⚠ Medium Confidence'
                else:
                    badge_class = 'confidence-low'
                    badge_text = '✗ No Data'

                model_used = result.get('model_used', '')
                model_tier = 'paid' if 'free' not in model_used.lower() else 'free'
                model_label = f"🆓 Free model" if model_tier == 'free' else f"💰 Paid model"

                col_badge, col_model = st.columns([2, 1])
                with col_badge:
                    st.markdown(f'<span class="{badge_class}">{badge_text}</span>', unsafe_allow_html=True)
                with col_model:
                    st.caption(f"{model_label}: `{model_used}`")
                st.markdown("")
                
                # Answer text
                st.markdown(result['answer'])
                
                # Sources
                if result['sources']:
                    st.markdown("---")
                    st.markdown("**📚 Sources:**")
                    for source in result['sources']:
                        st.markdown(f"- {source}")
                
                # Copy button
                st.code(result['answer'], language=None)

                # Metadata
                with st.expander("ℹ️ Query Details"):
                    st.write(f"**Chunks Used:** {result['chunks_used']}")
                    st.write(f"**Confidence:** {result['confidence']}")
                    st.write(f"**Model Used:** {result.get('model_used', 'N/A')}")
                    if filters:
                        st.write(f"**Filters Applied:** {filters}")
            
            except Exception as e:
                logger.exception("[UI] answer_question failed | question=%r | filters=%s", question[:100], filters)
                st.error(f"Error: {str(e)}")
                st.exception(e)


def _process_definition_command(text: str) -> Optional[Dict[str, Any]]:
    """
    Process definition commands from chat.
    
    Supported patterns:
    - "define GWP as L-4"
    - "add definition: Premium Schedule = L-5"
    - "define Margin % = Margin / ANP"
    - "what is GWP?"
    
    Returns:
        Dict with success and message, or None if not a definition command
    """
    import re
    
    text_lower = text.lower().strip()
    
    # Pattern 1: "define X as L-Y" or "add definition: X = L-Y"
    page_pattern1 = re.compile(r'(?:define|add definition:?)\s+(.+?)\s+(?:as|=)\s+(l-\d+)', re.IGNORECASE)
    match = page_pattern1.search(text)
    if match:
        term = match.group(1).strip()
        lpage = match.group(2).strip().upper()
        success, message = add_page_definition(term, lpage)
        return {"success": success, "message": message}
    
    # Pattern 2: "define X = formula" (calculation)
    calc_pattern = re.compile(r'(?:define|add calculation:?)\s+(.+?)\s*=\s*(.+)', re.IGNORECASE)
    match = calc_pattern.search(text)
    if match:
        # Check if it's not an L-page definition
        if not match.group(2).strip().upper().startswith('L-'):
            calc_name = match.group(1).strip()
            formula = match.group(2).strip()
            success, message = add_calculation(calc_name, formula)
            return {"success": success, "message": message}
    
    # Pattern 3: "what is X?" or "define X" (search)
    search_pattern = re.compile(r'(?:what is|define)\s+(.+?)[\?]?$', re.IGNORECASE)
    match = search_pattern.search(text)
    if match and len(text.split()) <= 5:  # Only for short queries
        term = match.group(1).strip()
        result = search_definitions(term)
        
        if result["found"]:
            msg_parts = [f"**{term}**"]
            if result["type"] in ["page", "both"]:
                msg_parts.append(f"📄 Page: {result['lpage']}")
                if result["related_terms"]:
                    msg_parts.append(f"Related: {', '.join(result['related_terms'])}")
            if result["type"] in ["calculation", "both"]:
                msg_parts.append(f"🧮 Formula: {result['formula']}")
            
            return {"success": True, "message": "\n".join(msg_parts)}
        else:
            return {"success": False, "message": f"No definition found for '{term}'"}
    
    return None


def render_tab_upload():
    """Tab 2: Upload Reports."""
    st.header("📤 Upload Reports")
    
    st.markdown("""
    Upload IRDAI Public Disclosure PDF reports. Files must follow the naming convention:
    
    **Format:** `{COMPANY_CODE}_{QUARTER}_{FY}.pdf`
    
    **Examples:** `HDFC_Life_Q1_FY25.pdf`, `SBI_Life_Q2_FY25.pdf`
    """)
    
    # File uploader
    uploaded_files = st.file_uploader(
        "Choose PDF files",
        type=['pdf'],
        accept_multiple_files=True,
        help=f"Maximum file size: {MAX_UPLOAD_SIZE_MB}MB per file"
    )
    
    if uploaded_files:
        st.markdown("---")
        st.subheader("📋 Files to Upload")

        # Filename validator
        import re as _re
        _valid_pattern = _re.compile(r'^.+_(Q[1-4])_(FY\d{2})\.pdf$')
        invalid_files = [f.name for f in uploaded_files if not _valid_pattern.match(f.name)]
        if invalid_files:
            st.error(
                f"❌ Invalid filename(s) — must follow `{{COMPANY_CODE}}_{{QUARTER}}_{{FY}}.pdf`:\n"
                + "\n".join(f"  • {n}" for n in invalid_files)
            )
            return

        # Show files
        for file in uploaded_files:
            st.write(f"- {file.name} ({file.size / 1024:.1f} KB)")
        
        # Upload button
        if st.button("🚀 Start Ingestion", type="primary"):
            # OPTIMIZATION 1 & 2: Use background worker for parallel processing
            # Auto-detect CPU cores and use them efficiently
            import os
            cpu_count = os.cpu_count() or 2
            max_workers = max(2, cpu_count - 1)  # Leave 1 core free for system
            
            st.info(f"🚀 Processing with {max_workers} parallel workers (detected {cpu_count} CPU cores)")
            
            worker = get_worker(max_workers=max_workers)
            
            # Save uploaded files to temp directory
            temp_paths = []
            for uploaded_file in uploaded_files:
                temp_path = Path(tempfile.gettempdir()) / uploaded_file.name
                with open(temp_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                temp_paths.append(str(temp_path))
            
            # Submit all files to background worker
            job_ids = worker.submit_batch(temp_paths)
            
            # Show progress with live updates and detailed status
            progress_bar = st.progress(0)
            status_placeholder = st.empty()  # Single placeholder that gets replaced
            
            # Poll for completion with detailed updates
            while True:
                jobs = {jid: worker.get_job_status(jid) for jid in job_ids}
                
                # Count statuses
                completed = sum(1 for j in jobs.values() if j.status in [JobStatus.COMPLETED, JobStatus.FAILED])
                processing = [j for j in jobs.values() if j.status == JobStatus.PROCESSING]
                pending = [j for j in jobs.values() if j.status == JobStatus.PENDING]
                total = len(jobs)
                
                # Update progress bar
                progress_bar.progress(completed / total)
                
                # Build status text (replaces previous content)
                status_lines = ["### 📊 Processing Status\n"]
                
                # Processing files
                if processing:
                    status_lines.append(f"**🔄 Processing ({len(processing)} files):**\n")
                    for job in processing:
                        stage = "Starting..."
                        if job.progress >= 0.9:
                            stage = "Storing embeddings..."
                        elif job.progress >= 0.6:
                            stage = "Generating embeddings..."
                        elif job.progress >= 0.4:
                            stage = "Chunking document..."
                        elif job.progress >= 0.2:
                            stage = "Parsing PDF..."
                        
                        status_lines.append(f"- {job.filename}: {stage} ({int(job.progress * 100)}%)\n")
                    status_lines.append("\n")
                
                # Pending files
                if pending:
                    status_lines.append(f"**⏳ Waiting ({len(pending)} files):**\n")
                    for job in pending[:3]:  # Show first 3
                        status_lines.append(f"- {job.filename}\n")
                    if len(pending) > 3:
                        status_lines.append(f"- ... and {len(pending) - 3} more\n")
                    status_lines.append("\n")
                
                # Completed files
                completed_jobs = [j for j in jobs.values() if j.status == JobStatus.COMPLETED]
                if completed_jobs:
                    status_lines.append(f"**✅ Completed ({len(completed_jobs)} files)**\n\n")
                
                # Failed files
                failed_jobs = [j for j in jobs.values() if j.status == JobStatus.FAILED]
                if failed_jobs:
                    status_lines.append(f"**❌ Failed ({len(failed_jobs)} files):**\n")
                    for job in failed_jobs:
                        status_lines.append(f"- {job.filename}: {job.error}\n")
                    status_lines.append("\n")
                
                status_lines.append(f"**Overall Progress: {completed}/{total} files**")
                
                # Replace entire status (not append!)
                status_placeholder.markdown("".join(status_lines))
                
                # Check if all done
                if completed == total:
                    break
                
                time.sleep(0.3)  # Update every 300ms for smooth progress
            
            status_placeholder.empty()
            progress_bar.empty()
            
            # Clean up temp files
            for temp_path in temp_paths:
                Path(temp_path).unlink(missing_ok=True)
            
            # Collect results
            results = []
            for job_id in job_ids:
                job = worker.get_job_status(job_id)
                if job.status == JobStatus.COMPLETED and job.result:
                    results.append(job.result)
                elif job.status == JobStatus.FAILED:
                    results.append({
                        "status": "error",
                        "source_file": job.filename,
                        "message": job.error or "Unknown error"
                    })
            
            # Show results
            st.markdown("---")
            st.subheader("✅ Ingestion Results")
            
            success_count = sum(1 for r in results if r['status'] == 'success')
            skipped_count = sum(1 for r in results if r['status'] == 'skipped')
            error_count = sum(1 for r in results if r['status'] == 'error')
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Success", success_count)
            with col2:
                st.metric("Skipped", skipped_count)
            with col3:
                st.metric("Errors", error_count)
            
            # Detailed results
            for result in results:
                if result['status'] == 'success':
                    page_def_warn = " ⚠️ No L-page index found" if not result.get('page_definitions_found') else ""
                    st.success(f"✓ {result['source_file']}: {result['chunks_created']} chunks in {result['duration_seconds']}s{page_def_warn}")
                elif result['status'] == 'skipped':
                    st.info(f"⊘ {result['source_file']}: Already indexed")
                else:
                    st.error(f"✗ {result['source_file']}: {result['message']}")
            
            # Clear completed jobs from worker
            worker.clear_completed_jobs()
    
    # Show indexed files
    st.markdown("---")
    st.subheader("📚 Indexed Files")
    
    stats = get_collection_stats()
    
    if stats['total_chunks'] == 0:
        st.info("No files indexed yet.")
    else:
        # Get all files with metadata
        collection = get_or_create_collection()
        all_data = collection.get(include=["metadatas"])

        if all_data['ids']:
            # Build dataframe
            files_data = {}
            for metadata in all_data['metadatas']:
                source = metadata['source_file']
                if source not in files_data:
                    files_data[source] = {
                        'Company': metadata['company'],
                        'Quarter': metadata['quarter'],
                        'FY': metadata['fy'],
                        'Period': metadata['period_label'],
                        'Chunks': 0,
                        'Ingested At': metadata.get('ingested_at', 'Unknown')
                    }
                files_data[source]['Chunks'] += 1
            
            df = pd.DataFrame.from_dict(files_data, orient='index')
            df.index.name = 'File'
            df = df.reset_index()
            
            # Format ingested_at
            df['Ingested At'] = pd.to_datetime(df['Ingested At']).dt.strftime('%Y-%m-%d %H:%M')
            
            st.dataframe(df, use_container_width=True)
            
            # Delete file option
            st.markdown("---")
            st.subheader("🗑️ Delete File from Index")
            
            file_to_delete = st.selectbox(
                "Select file to delete",
                options=list(files_data.keys())
            )
            
            col_del, col_reindex = st.columns(2)
            with col_del:
                if st.button("🗑️ Delete Selected File", type="secondary"):
                    deleted_count = delete_file_chunks(file_to_delete)
                    st.success(f"Deleted {deleted_count} chunks from {file_to_delete}")
                    st.rerun()
            with col_reindex:
                if st.button("🔄 Re-index Selected File", type="secondary"):
                    from src.config import PDF_INPUT_DIR
                    import os
                    pdf_path = os.path.join(PDF_INPUT_DIR, file_to_delete)
                    if os.path.exists(pdf_path):
                        with st.spinner(f"Re-indexing {file_to_delete}..."):
                            result = ingest_pdf(pdf_path, force_reindex=True)
                        if result['status'] == 'success':
                            st.success(f"Re-indexed: {result['chunks_created']} chunks")
                        else:
                            st.error(f"Re-index failed: {result['message']}")
                        st.rerun()
                    else:
                        st.error(f"PDF not found in {PDF_INPUT_DIR}. Upload the file again.")


def render_tab_index_status():
    """Tab 3: Index Status."""
    st.header("📊 Index Status")
    
    stats = get_collection_stats()
    
    # Summary stats
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Chunks", stats['total_chunks'])
    with col2:
        st.metric("Unique Files", stats['unique_files'])
    with col3:
        st.metric("Companies", len(stats['chunks_by_company']))
    
    if stats['total_chunks'] == 0:
        st.info("No data indexed yet. Upload PDF files in the 'Upload Reports' tab.")
        return
    
    # Chunks by company
    st.markdown("---")
    st.subheader("📈 Chunks by Company")
    
    company_df = pd.DataFrame(
        list(stats['chunks_by_company'].items()),
        columns=['Company', 'Chunks']
    ).sort_values('Chunks', ascending=False)
    
    st.bar_chart(company_df.set_index('Company'))
    
    # Coverage matrix
    st.markdown("---")
    st.subheader("🗓️ Coverage Matrix")
    
    collection = get_or_create_collection()
    all_data = collection.get(include=["metadatas"])

    if all_data['ids']:
        # Build coverage matrix
        coverage = {}
        for metadata in all_data['metadatas']:
            company = metadata['company']
            period = f"{metadata['quarter']} {metadata['fy']}"
            
            if company not in coverage:
                coverage[company] = set()
            coverage[company].add(period)
        
        # Get all unique periods
        all_periods = sorted(set(p for periods in coverage.values() for p in periods))
        
        # Build matrix
        matrix_data = []
        for company in sorted(coverage.keys()):
            row = {'Company': company}
            for period in all_periods:
                row[period] = '✅' if period in coverage[company] else '❌'
            matrix_data.append(row)
        
        matrix_df = pd.DataFrame(matrix_data)
        st.dataframe(matrix_df, use_container_width=True)
    
    # Clear all button
    st.markdown("---")
    st.subheader("⚠️ Danger Zone")
    
    if st.button("🗑️ Clear All Data", type="secondary"):
        confirm = st.text_input(
            "This will delete ALL indexed data. Type **CONFIRM** to proceed:",
            key="clear_confirm"
        )
        if confirm == "CONFIRM":
            collection = get_or_create_collection()
            all_ids = collection.get()["ids"]
            if all_ids:
                collection.delete(ids=all_ids)
            st.success("All data cleared from ChromaDB")
            st.rerun()
        elif confirm:
            st.warning("Type CONFIRM exactly (all caps) to proceed.")


def render_tab_vector_visualization():
    """Tab 5: Vector Database 3D Visualization."""
    st.header("🎨 Vector Database 3D Visualization")
    
    st.markdown("""
    Visualize your vector embeddings in 3D space. Each company is shown in a different color.
    This helps you understand how documents are distributed in the semantic space.
    """)
    
    # Get stats
    stats = get_visualization_stats()
    
    if stats['total_vectors'] == 0:
        st.warning("⚠️ No data in vector database. Please upload PDF files first.")
        return
    
    # Show stats
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Vectors", stats['total_vectors'])
    with col2:
        st.metric("Companies", len(stats['companies']))
    with col3:
        st.metric("Embedding Dimension", stats['embedding_dimension'])
    
    st.markdown("---")
    
    # Visualization controls
    col_method, col_samples = st.columns(2)
    
    with col_method:
        method = st.selectbox(
            "Dimensionality Reduction Method",
            options=['PCA', 't-SNE'],
            index=0,
            help="PCA is faster, t-SNE often gives better visual separation"
        )
    
    with col_samples:
        max_samples = st.number_input(
            "Max Samples to Visualize",
            min_value=100,
            max_value=stats['total_vectors'],
            value=min(2000, stats['total_vectors']),
            step=100,
            help="Reduce for faster rendering. t-SNE is slower with more samples."
        )
    
    # Company distribution
    with st.expander("📊 Vectors by Company"):
        for company, count in sorted(stats['vectors_by_company'].items()):
            percentage = (count / stats['total_vectors']) * 100
            st.write(f"**{company}**: {count} vectors ({percentage:.1f}%)")
    
    # Generate visualization button
    if st.button("🎨 Generate 3D Visualization", type="primary", use_container_width=True):
        with st.spinner(f"Creating 3D visualization using {method}... This may take a moment."):
            try:
                # Create visualization
                fig = visualize_vectors(
                    method=method.lower(),
                    max_samples=int(max_samples),
                    title=f"Vector Database 3D Visualization ({method})"
                )
                
                # Display plot
                st.plotly_chart(fig, use_container_width=True)
                
                # Info
                st.success("✓ Visualization created! Interact with the plot:")
                st.markdown("""
                - **Rotate**: Click and drag
                - **Zoom**: Scroll or pinch
                - **Pan**: Right-click and drag
                - **Hover**: See document details
                - **Legend**: Click to show/hide companies
                """)
                
                # Download option
                st.markdown("---")
                st.markdown("**💾 Download Visualization**")
                
                # Save to HTML
                html_str = fig.to_html(include_plotlyjs='cdn')
                st.download_button(
                    label="📥 Download as HTML",
                    data=html_str,
                    file_name=f"vector_visualization_{method.lower()}.html",
                    mime="text/html",
                    help="Download interactive HTML file to share or view offline"
                )
            
            except Exception as e:
                st.error(f"Failed to create visualization: {str(e)}")
                logger.exception("Visualization failed")
    
    # Help section
    st.markdown("---")
    with st.expander("ℹ️ Understanding the Visualization"):
        st.markdown("""
        ### What am I looking at?
        
        Each point represents a chunk of text from your documents. Points that are close together 
        have similar semantic meaning.
        
        ### Colors
        - Each company has a unique color
        - This helps you see how documents from different companies are distributed
        
        ### Dimensionality Reduction
        
        **PCA (Principal Component Analysis)**:
        - Fast and deterministic
        - Preserves global structure
        - Good for getting a quick overview
        
        **t-SNE (t-Distributed Stochastic Neighbor Embedding)**:
        - Slower but often better visual separation
        - Preserves local structure (similar items stay close)
        - Good for finding clusters
        
        ### Interpretation
        
        - **Clusters**: Groups of points indicate similar content
        - **Separation**: Companies with distinct content will be more separated
        - **Overlap**: Similar content across companies will overlap
        - **Outliers**: Isolated points may be unique or unusual content
        """)


def render_tab_definitions():
    """Tab 4: Manage Definitions."""
    st.header("📚 Manage Definitions")
    
    st.markdown("""
    Define custom terms and calculations to help the system understand your queries better.
    
    **Two types of definitions:**
    - **Page Definitions**: Map terms to L-pages (e.g., GWP → L-4)
    - **Calculations**: Define formulas (e.g., Margin % = Margin / ANP)
    """)
    
    # Merge with PDF definitions button
    col_merge, col_space = st.columns([1, 3])
    with col_merge:
        if st.button("🔄 Sync with PDF Definitions", help="Merge definitions extracted from uploaded PDFs"):
            merge_with_pdf_definitions()
            st.success("✓ Synced with PDF definitions")
            st.rerun()
    
    st.markdown("---")
    
    # Two columns: Add definitions | View/Delete definitions
    col_add, col_view = st.columns([1, 1])
    
    # ===== LEFT COLUMN: Add Definitions =====
    with col_add:
        st.subheader("➕ Add New Definition")
        
        def_type = st.radio(
            "Definition Type",
            options=["Page Definition", "Calculation"],
            horizontal=True,
            key="def_type_radio"
        )
        
        if def_type == "Page Definition":
            st.markdown("**Map a term to an L-page**")
            
            term_input = st.text_input(
                "Term",
                placeholder="e.g., GWP, Premium Schedule",
                key="page_term_input"
            )
            
            lpage_input = st.text_input(
                "L-Page",
                placeholder="e.g., L-4",
                key="lpage_input"
            )
            
            if st.button("➕ Add Page Definition", type="primary", use_container_width=True):
                if term_input and lpage_input:
                    success, message = add_page_definition(term_input, lpage_input)
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
                else:
                    st.warning("Please fill in both fields")
        
        else:  # Calculation
            st.markdown("**Define a calculation formula**")
            
            calc_name = st.text_input(
                "Calculation Name",
                placeholder="e.g., Margin %, ROE",
                key="calc_name_input"
            )
            
            calc_formula = st.text_area(
                "Formula",
                placeholder="e.g., Margin / ANP, Net Profit / Equity",
                height=100,
                key="calc_formula_input"
            )
            
            if st.button("➕ Add Calculation", type="primary", use_container_width=True):
                if calc_name and calc_formula:
                    success, message = add_calculation(calc_name, calc_formula)
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
                else:
                    st.warning("Please fill in both fields")
    
    # ===== RIGHT COLUMN: View/Delete Definitions =====
    with col_view:
        st.subheader("📋 Current Definitions")
        
        all_defs = get_all_definitions()
        
        # Tabs for Page Definitions and Calculations
        tab_page, tab_calc = st.tabs(["📄 Page Definitions", "🧮 Calculations"])
        
        with tab_page:
            if not all_defs["page_definitions"]:
                st.info("No page definitions yet. Add some or sync with PDF definitions.")
            else:
                st.markdown(f"**{all_defs['metadata']['total_page_terms']} terms mapped to {len(all_defs['page_definitions'])} L-pages**")
                
                for lpage in sorted(all_defs["page_definitions"].keys()):
                    terms = all_defs["page_definitions"][lpage]
                    
                    with st.expander(f"**{lpage}** ({len(terms)} terms)"):
                        for term in sorted(terms):
                            col_term, col_del = st.columns([4, 1])
                            with col_term:
                                st.markdown(f"• {term}")
                            with col_del:
                                if st.button("🗑️", key=f"del_page_{lpage}_{term}", help=f"Delete '{term}'"):
                                    success, message = delete_page_definition(term)
                                    if success:
                                        st.success(message)
                                        st.rerun()
                                    else:
                                        st.error(message)
        
        with tab_calc:
            if not all_defs["calculations"]:
                st.info("No calculations defined yet. Add some above.")
            else:
                st.markdown(f"**{len(all_defs['calculations'])} calculations defined**")
                
                for calc_name in sorted(all_defs["calculations"].keys()):
                    formula = all_defs["calculations"][calc_name]
                    
                    col_calc, col_del = st.columns([4, 1])
                    with col_calc:
                        st.markdown(f"**{calc_name}**")
                        st.code(formula, language=None)
                    with col_del:
                        if st.button("🗑️", key=f"del_calc_{calc_name}", help=f"Delete '{calc_name}'"):
                            success, message = delete_calculation(calc_name)
                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)
    
    # ===== BOTTOM: Search Definitions =====
    st.markdown("---")
    st.subheader("🔍 Search Definitions")
    
    search_query = st.text_input(
        "Search for a term or calculation",
        placeholder="e.g., GWP, Margin %, Premium",
        key="search_def_input"
    )
    
    if search_query:
        result = search_definitions(search_query)
        
        if result["found"]:
            st.success(f"✓ Found: **{search_query}**")
            
            if result["type"] in ["page", "both"]:
                st.markdown(f"**📄 Page Definition:** {result['lpage']}")
                if result["related_terms"]:
                    st.markdown(f"**Related terms:** {', '.join(result['related_terms'])}")
            
            if result["type"] in ["calculation", "both"]:
                st.markdown(f"**🧮 Calculation Formula:**")
                st.code(result["formula"], language=None)
        else:
            st.warning(f"No definition found for '{search_query}'")
    
    # Metadata
    if all_defs["metadata"]["last_updated"]:
        st.caption(f"Last updated: {all_defs['metadata']['last_updated']}")


def main():
    """Main app."""
    render_sidebar()
    render_header()

    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "💬 Ask a Question", 
        "📤 Upload Reports", 
        "📊 Index Status",
        "📚 Definitions",
        "🎨 3D Visualization"
    ])

    with tab1:
        render_tab_ask_question()

    with tab2:
        render_tab_upload()

    with tab3:
        render_tab_index_status()
    
    with tab4:
        render_tab_definitions()
    
    with tab5:
        render_tab_vector_visualization()


if __name__ == "__main__":
    main()
