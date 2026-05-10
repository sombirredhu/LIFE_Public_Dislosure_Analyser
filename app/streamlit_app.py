"""
Streamlit Web UI for Insurance PD Report Analyzer.
Three tabs: Ask Questions, Upload Reports, Index Status.
"""

import sys
from pathlib import Path
import streamlit as st
import pandas as pd
from datetime import datetime
import time

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.rag_pipeline import answer_question
from src.ingestor import ingest_pdf
from src.embedder import get_collection_stats, delete_file_chunks, get_or_create_collection
from src.config import APP_TITLE, COMPANY_CODES, MAX_UPLOAD_SIZE_MB


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
    
    # Question input
    question = st.text_area(
        "Enter your question:",
        placeholder="Example: Which company had the highest gross written premium in Q1 FY25?",
        height=100
    )
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        company_filter = st.multiselect(
            "Filter by Company (optional)",
            options=COMPANY_CODES,
            default=[]
        )
    
    with col2:
        quarter_filter = st.selectbox(
            "Filter by Quarter (optional)",
            options=["All", "Q1", "Q2", "Q3", "Q4"],
            index=0
        )
    
    with col3:
        fy_filter = st.selectbox(
            "Filter by FY (optional)",
            options=["All", "FY25", "FY26", "FY27"],
            index=0
        )
    
    # Submit button
    if st.button("🔍 Get Answer", type="primary", use_container_width=True):
        if not question.strip():
            st.error("Please enter a question.")
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
                    filters=filters if filters else None
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
                elif confidence == 'low':
                    badge_class = 'confidence-low'
                    badge_text = '⚠ Low Confidence'
                else:
                    badge_class = 'confidence-low'
                    badge_text = '✗ No Data'
                
                st.markdown(f'<span class="{badge_class}">{badge_text}</span>', unsafe_allow_html=True)
                st.markdown("")
                
                # Answer text
                st.markdown(result['answer'])
                
                # Sources
                if result['sources']:
                    st.markdown("---")
                    st.markdown("**📚 Sources:**")
                    for source in result['sources']:
                        st.markdown(f"- {source}")
                
                # Metadata
                with st.expander("ℹ️ Query Details"):
                    st.write(f"**Chunks Used:** {result['chunks_used']}")
                    st.write(f"**Confidence:** {result['confidence']}")
                    if filters:
                        st.write(f"**Filters Applied:** {filters}")
            
            except Exception as e:
                st.error(f"Error: {str(e)}")
                st.exception(e)


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
        
        # Show files
        for file in uploaded_files:
            st.write(f"- {file.name} ({file.size / 1024:.1f} KB)")
        
        # Upload button
        if st.button("🚀 Start Ingestion", type="primary"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            results = []
            
            for i, uploaded_file in enumerate(uploaded_files):
                status_text.text(f"Processing {i+1}/{len(uploaded_files)}: {uploaded_file.name}")
                
                # Save to temp file
                temp_path = Path(f"/tmp/{uploaded_file.name}")
                with open(temp_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # Ingest
                result = ingest_pdf(str(temp_path))
                results.append(result)
                
                # Update progress
                progress_bar.progress((i + 1) / len(uploaded_files))
                
                # Clean up temp file
                temp_path.unlink()
            
            status_text.empty()
            progress_bar.empty()
            
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
                    st.success(f"✓ {result['source_file']}: {result['chunks_created']} chunks in {result['duration_seconds']}s")
                elif result['status'] == 'skipped':
                    st.info(f"⊘ {result['source_file']}: Already indexed")
                else:
                    st.error(f"✗ {result['source_file']}: {result['message']}")
    
    # Show indexed files
    st.markdown("---")
    st.subheader("📚 Indexed Files")
    
    stats = get_collection_stats()
    
    if stats['total_chunks'] == 0:
        st.info("No files indexed yet.")
    else:
        # Get all files with metadata
        collection = get_or_create_collection()
        all_data = collection.get()
        
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
            
            if st.button("Delete Selected File", type="secondary"):
                deleted_count = delete_file_chunks(file_to_delete)
                st.success(f"Deleted {deleted_count} chunks from {file_to_delete}")
                st.rerun()


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
    all_data = collection.get()
    
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
        if st.checkbox("I understand this will delete all indexed data"):
            collection = get_or_create_collection()
            collection.delete(where={})
            st.success("All data cleared from ChromaDB")
            st.rerun()


def main():
    """Main app."""
    render_header()
    
    # Tabs
    tab1, tab2, tab3 = st.tabs(["💬 Ask a Question", "📤 Upload Reports", "📊 Index Status"])
    
    with tab1:
        render_tab_ask_question()
    
    with tab2:
        render_tab_upload()
    
    with tab3:
        render_tab_index_status()


if __name__ == "__main__":
    main()
