import streamlit as st
import pandas as pd
import logging
import json
import time
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.vector_visualizer import get_visualization_stats, visualize_vectors

logger = logging.getLogger(__name__)

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



