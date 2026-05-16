import streamlit as st
import pandas as pd
import logging
import time
import tempfile
from pathlib import Path
from typing import List

from src.config import MAX_UPLOAD_SIZE_MB
from src.ingestor import ingest_pdf
from src.embedder import (
    get_collection_stats, get_or_create_collection,
    delete_file_chunks
)
from src.background_worker import get_worker, JobStatus

logger = logging.getLogger(__name__)

def render_tab_upload():
    """Tab 2: Upload Reports."""
    st.header("📤 Upload Reports")
    
    st.markdown("""
    Upload IRDAI Public Disclosure PDF reports. Files must follow the naming convention:
    
    **Format:** `{COMPANY_CODE}_{QUARTER}_{FY}.pdf`
    
    **Examples:** `HDFC_Life_Q1_FY25.pdf`, `SBI_Life_Q2_FY25.pdf`
    """)
    
    # Processing mode selector
    st.markdown("### ⚙️ Processing Mode")
    processing_mode = st.radio(
        "Choose how to process files:",
        options=["Parallel", "Sequential"],
        index=0,
        horizontal=True,
        help="Parallel: Process multiple files simultaneously (faster). Sequential: Process one file at a time (more stable)."
    )
    
    if processing_mode == "Parallel":
        st.info("🚀 **Parallel Mode**: Files will be processed simultaneously using multiple CPU cores for faster ingestion.")
    else:
        st.info("📝 **Sequential Mode**: Files will be processed one by one in order. Slower but more stable for large files.")
    
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
            # Resolve PDF storage dir — cloud-safe with multiple fallbacks.
            # Never reference the module-level PDF_INPUT_DIR directly inside
            # the function to avoid UnboundLocalError on Streamlit Cloud.
            import os as _os
            _pdf_dir_str = (
                _os.getenv("PDF_INPUT_DIR")          # set in Cloud secrets
                or _os.getenv("TMPDIR")              # macOS/Linux temp
                or "/tmp/pdfs"                       # universal fallback
            )
            temp_paths = []
            try:
                _persistent = Path(_pdf_dir_str)
                _persistent.mkdir(parents=True, exist_ok=True)
            except (PermissionError, OSError) as _e:
                _persistent = Path(tempfile.gettempdir()) / "pdfs"
                _persistent.mkdir(parents=True, exist_ok=True)
                logger.warning("[UPLOAD] Fallback to %s: %s", _persistent, _e)

            for uploaded_file in uploaded_files:
                temp_path = Path(tempfile.gettempdir()) / uploaded_file.name
                file_bytes = uploaded_file.getbuffer()
                with open(temp_path, "wb") as f:
                    f.write(file_bytes)
                temp_paths.append(str(temp_path))

                # Best-effort persist (silent fail on read-only FS)
                try:
                    with open(_persistent / uploaded_file.name, "wb") as f:
                        f.write(file_bytes)
                    logger.info("[UPLOAD] Persisted %s → %s", uploaded_file.name, _persistent)
                except OSError as exc:
                    logger.warning("[UPLOAD] Could not persist %s: %s", uploaded_file.name, exc)

            results = []
            
            # PARALLEL MODE: Use background worker for parallel processing
            if processing_mode == "Parallel":
                # Auto-detect CPU cores and use them efficiently
                import os
                cpu_count = os.cpu_count() or 2
                max_workers = max(2, cpu_count - 1)  # Leave 1 core free for system
                
                st.info(f"🚀 Processing with {max_workers} parallel workers (detected {cpu_count} CPU cores)")
                
                worker = get_worker(max_workers=max_workers)
                
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
                
                # Collect results
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
                
                # Clear completed jobs from worker
                worker.clear_completed_jobs()
            
            # SEQUENTIAL MODE: Process files one by one
            else:
                st.info(f"📝 Processing {len(temp_paths)} files sequentially...")
                
                progress_bar = st.progress(0)
                status_placeholder = st.empty()
                
                for idx, temp_path in enumerate(temp_paths, 1):
                    filename = Path(temp_path).name
                    
                    # Update status
                    status_placeholder.markdown(f"### 📊 Processing Status\n\n**🔄 Processing file {idx}/{len(temp_paths)}:** {filename}")
                    
                    # Process file
                    result = ingest_pdf(temp_path, force_reindex=False)
                    results.append(result)
                    
                    # Update progress
                    progress_bar.progress(idx / len(temp_paths))
                    
                    # Show immediate result
                    if result['status'] == 'success':
                        status_placeholder.success(f"✓ {filename}: {result['chunks_created']} chunks in {result['duration_seconds']}s")
                    elif result['status'] == 'skipped':
                        status_placeholder.info(f"⊘ {filename}: Already indexed")
                    else:
                        status_placeholder.error(f"✗ {filename}: {result['message']}")
                    
                    time.sleep(0.5)  # Brief pause to show result
                
                status_placeholder.empty()
                progress_bar.empty()
            
            # Clean up temp files
            for temp_path in temp_paths:
                Path(temp_path).unlink(missing_ok=True)
            
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
            
            # Clear completed jobs from worker (only exists in parallel mode)
            if processing_mode == "Parallel":
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



