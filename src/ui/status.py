import streamlit as st
import pandas as pd

from src.embedder import get_collection_stats, get_or_create_collection, invalidate_metadata_cache

def render_tab_index_status():
    """Tab 3: Index Status."""
    st.header("📊 Index Status")
    invalidate_metadata_cache()
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
        st.dataframe(matrix_df, width="stretch")
    
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



