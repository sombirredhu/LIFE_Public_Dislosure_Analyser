import streamlit as st
import logging
from src.vector_visualizer import get_visualization_stats, visualize_vectors

logger = logging.getLogger(__name__)

def render_tab_vector_visualization():
    st.header("🎨 Vector Database Visualization")
    st.markdown("Visualize vector embeddings using **PCA**. Each company is shown in a different color so you can see how documents cluster in semantic space.")
    stats = get_visualization_stats()
    if stats['total_vectors'] == 0:
        st.warning("⚠️ No data in vector database. Please upload PDF files first.")
        return
    col1, col2, col3 = st.columns(3)
    with col1: st.metric("Total Vectors", stats['total_vectors'])
    with col2: st.metric("Companies", len(stats['companies']))
    with col3: st.metric("Embedding Dimension", stats['embedding_dimension'])
    st.markdown("---")
    col_dims, col_samples = st.columns(2)
    with col_dims:
        dims_choice = st.radio("Plot Dimensions", options=["3D (interactive, rotatable)", "2D (flat scatter)"], index=0, key="viz_dims", help="3D lets you rotate; 2D is faster to render.")
        n_dims = 3 if dims_choice.startswith("3D") else 2
    with col_samples:
        max_samples = st.number_input("Max Samples", min_value=100, max_value=stats['total_vectors'], value=min(2000, stats['total_vectors']), step=100, help="Fewer samples = faster rendering.", key="viz_max_samples")
    with st.expander("📊 Vectors by Company"):
        for company, count in sorted(stats['vectors_by_company'].items()):
            pct = (count / stats['total_vectors']) * 100
            st.write(f"**{company}**: {count} vectors ({pct:.1f}%)")
    dim_label = f"{n_dims}D"
    if st.button(f"🎨 Generate {dim_label} Visualization", type="primary", use_container_width=True):
        with st.spinner(f"Running PCA → creating {dim_label} plot…"):
            try:
                fig = visualize_vectors(max_samples=int(max_samples), title=f"Vector DB {dim_label} — PCA", n_dims=n_dims)
                st.plotly_chart(fig, use_container_width=True)
                st.success(f"✓ {dim_label} visualization ready! Hover over points for details.")
                if n_dims == 3: st.caption("💡 Rotate: click & drag · Zoom: scroll · Pan: right-click drag · Legend: click to hide/show")
                st.markdown("---")
                html_str = fig.to_html(include_plotlyjs='cdn')
                st.download_button(label="📥 Download as HTML", data=html_str, file_name=f"vector_viz_pca_{dim_label.lower()}.html", mime="text/html")
            except Exception as e:
                st.error(f"Failed to create visualization: {e}")
                logger.exception("Visualization failed")
    st.markdown("---")
    with st.expander("ℹ️ Understanding the Visualization"):
        st.markdown("**Each point** = one chunk of text. Points close together share semantic meaning.\n\n**Colors** = companies.\n\n**PCA (Principal Component Analysis)**\n- Fast and deterministic\n- Preserves global structure\n- 3D mode is interactive")
