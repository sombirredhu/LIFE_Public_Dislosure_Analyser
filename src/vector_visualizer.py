"""
Vector Visualizer - Creates 3D visualization of vector embeddings.
Uses dimensionality reduction (PCA/t-SNE/UMAP) to project high-dimensional vectors to 3D.
Each company gets a unique color for easy identification.
"""

import logging
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
import plotly.graph_objects as go
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE

from src.embedder import get_or_create_collection

logger = logging.getLogger(__name__)

# Color palette for companies (distinct colors)
COMPANY_COLORS = [
    '#FF6B6B',  # Red
    '#4ECDC4',  # Teal
    '#45B7D1',  # Blue
    '#FFA07A',  # Light Salmon
    '#98D8C8',  # Mint
    '#F7DC6F',  # Yellow
    '#BB8FCE',  # Purple
    '#85C1E2',  # Sky Blue
    '#F8B739',  # Orange
    '#52B788',  # Green
    '#E63946',  # Dark Red
    '#457B9D',  # Steel Blue
    '#F4A261',  # Sandy Brown
    '#2A9D8F',  # Teal Green
    '#E76F51',  # Burnt Orange
]


def reduce_dimensions(embeddings: np.ndarray, method: str = 'pca', n_components: int = 3) -> np.ndarray:
    """
    Reduce high-dimensional embeddings to 3D for visualization.
    
    Args:
        embeddings: Array of shape (n_samples, n_features)
        method: 'pca', 'tsne', or 'umap'
        n_components: Number of dimensions (default 3 for 3D plot)
    
    Returns:
        Reduced embeddings of shape (n_samples, n_components)
    """
    logger.info(f"Reducing {embeddings.shape[0]} embeddings from {embeddings.shape[1]}D to {n_components}D using {method.upper()}")
    
    if method.lower() == 'pca':
        reducer = PCA(n_components=n_components, random_state=42)
        reduced = reducer.fit_transform(embeddings)
        variance_explained = sum(reducer.explained_variance_ratio_) * 100
        logger.info(f"PCA variance explained: {variance_explained:.2f}%")
    
    elif method.lower() == 'tsne':
        # t-SNE is slower but often better for visualization
        perplexity = min(30, embeddings.shape[0] - 1)  # Adjust perplexity for small datasets
        reducer = TSNE(n_components=n_components, random_state=42, perplexity=perplexity)
        reduced = reducer.fit_transform(embeddings)
        logger.info("t-SNE reduction completed")
    
    elif method.lower() == 'umap':
        try:
            import umap
            n_neighbors = min(15, embeddings.shape[0] - 1)
            reducer = umap.UMAP(n_components=n_components, random_state=42, n_neighbors=n_neighbors)
            reduced = reducer.fit_transform(embeddings)
            logger.info("UMAP reduction completed")
        except ImportError:
            logger.warning("UMAP not installed, falling back to PCA")
            return reduce_dimensions(embeddings, method='pca', n_components=n_components)
    
    else:
        raise ValueError(f"Unknown method: {method}. Use 'pca', 'tsne', or 'umap'")
    
    return reduced


def get_vector_data(max_samples: Optional[int] = None) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
    """
    Fetch embeddings and metadata from ChromaDB.
    
    Args:
        max_samples: Maximum number of samples to fetch (None for all)
    
    Returns:
        Tuple of (embeddings array, metadata list)
    """
    collection = get_or_create_collection()
    total = collection.count()
    
    if total == 0:
        raise ValueError("No data in vector database")
    
    # Limit samples if specified
    n_samples = min(max_samples, total) if max_samples else total
    
    logger.info(f"Fetching {n_samples} vectors from ChromaDB")
    
    # Get data from collection
    results = collection.get(
        limit=n_samples,
        include=["embeddings", "metadatas"]
    )
    
    embeddings = np.array(results["embeddings"])
    metadatas = results["metadatas"]
    
    logger.info(f"Fetched {embeddings.shape[0]} embeddings of dimension {embeddings.shape[1]}")
    
    return embeddings, metadatas


def create_3d_plot(
    embeddings_3d: np.ndarray,
    metadatas: List[Dict[str, Any]],
    title: str = "Vector Database 3D Visualization"
) -> go.Figure:
    """
    Create interactive 3D scatter plot with Plotly.
    
    Args:
        embeddings_3d: 3D embeddings array of shape (n_samples, 3)
        metadatas: List of metadata dicts for each embedding
        title: Plot title
    
    Returns:
        Plotly Figure object
    """
    # Group by company and assign colors
    company_to_color = {}
    companies = sorted(set(m["company"] for m in metadatas))
    
    for i, company in enumerate(companies):
        company_to_color[company] = COMPANY_COLORS[i % len(COMPANY_COLORS)]
    
    logger.info(f"Creating 3D plot for {len(companies)} companies")
    
    # Create figure
    fig = go.Figure()
    
    # Add trace for each company
    for company in companies:
        # Filter data for this company
        indices = [i for i, m in enumerate(metadatas) if m["company"] == company]
        
        x = embeddings_3d[indices, 0]
        y = embeddings_3d[indices, 1]
        z = embeddings_3d[indices, 2]
        
        # Create hover text
        hover_texts = []
        for idx in indices:
            m = metadatas[idx]
            hover_text = (
                f"<b>{m['company']}</b><br>"
                f"Period: {m['period_label']}<br>"
                f"Section: {m['section']}<br>"
                f"Page: {m['page_number']}<br>"
                f"Type: {m['content_type']}"
            )
            hover_texts.append(hover_text)
        
        # Add scatter trace
        fig.add_trace(go.Scatter3d(
            x=x,
            y=y,
            z=z,
            mode='markers',
            name=company,
            marker=dict(
                size=5,
                color=company_to_color[company],
                opacity=0.8,
                line=dict(width=0.5, color='white')
            ),
            text=hover_texts,
            hovertemplate='%{text}<extra></extra>'
        ))
    
    # Update layout
    fig.update_layout(
        title=dict(
            text=title,
            x=0.5,
            xanchor='center',
            font=dict(size=20, color='#2C3E50')
        ),
        scene=dict(
            xaxis=dict(title='Dimension 1', backgroundcolor='#F8F9FA', gridcolor='#E0E0E0'),
            yaxis=dict(title='Dimension 2', backgroundcolor='#F8F9FA', gridcolor='#E0E0E0'),
            zaxis=dict(title='Dimension 3', backgroundcolor='#F8F9FA', gridcolor='#E0E0E0'),
            bgcolor='#FFFFFF'
        ),
        legend=dict(
            title=dict(text='Companies', font=dict(size=14)),
            font=dict(size=12),
            bgcolor='rgba(255, 255, 255, 0.8)',
            bordercolor='#CCCCCC',
            borderwidth=1
        ),
        margin=dict(l=0, r=0, t=50, b=0),
        hovermode='closest',
        height=700
    )
    
    return fig


def visualize_vectors(
    method: str = 'pca',
    max_samples: Optional[int] = 2000,
    title: Optional[str] = None
) -> go.Figure:
    """
    Main function to create 3D visualization of vector database.
    
    Args:
        method: Dimensionality reduction method ('pca', 'tsne', 'umap')
        max_samples: Maximum number of samples to visualize (None for all)
        title: Custom plot title
    
    Returns:
        Plotly Figure object
    """
    try:
        # Fetch data
        embeddings, metadatas = get_vector_data(max_samples=max_samples)
        
        # Reduce dimensions
        embeddings_3d = reduce_dimensions(embeddings, method=method, n_components=3)
        
        # Create plot
        if title is None:
            title = f"Vector Database 3D Visualization ({method.upper()})"
        
        fig = create_3d_plot(embeddings_3d, metadatas, title=title)
        
        logger.info("3D visualization created successfully")
        return fig
    
    except Exception as e:
        logger.error(f"Failed to create visualization: {e}")
        raise


def get_visualization_stats() -> Dict[str, Any]:
    """
    Get statistics about the vector database for visualization.
    
    Returns:
        Dict with statistics
    """
    try:
        collection = get_or_create_collection()
        total = collection.count()
        
        if total == 0:
            return {
                "total_vectors": 0,
                "companies": [],
                "vectors_by_company": {},
                "embedding_dimension": 0
            }
        
        # Get metadata
        results = collection.get(include=["metadatas", "embeddings"], limit=1)
        embedding_dim = len(results["embeddings"][0]) if len(results["embeddings"]) > 0 else 0
        
        # Get all metadata for company stats
        all_results = collection.get(include=["metadatas"])
        metadatas = all_results["metadatas"]
        
        # Count by company
        vectors_by_company = {}
        for m in metadatas:
            company = m["company"]
            vectors_by_company[company] = vectors_by_company.get(company, 0) + 1
        
        return {
            "total_vectors": total,
            "companies": sorted(vectors_by_company.keys()),
            "vectors_by_company": vectors_by_company,
            "embedding_dimension": embedding_dim
        }
    
    except Exception as e:
        logger.error(f"Failed to get visualization stats: {e}")
        return {
            "total_vectors": 0,
            "companies": [],
            "vectors_by_company": {},
            "embedding_dimension": 0
        }


if __name__ == "__main__":
    # Test visualization
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    print("🎨 Vector Database Visualizer\n")
    
    # Get stats
    stats = get_visualization_stats()
    print(f"Total vectors: {stats['total_vectors']}")
    print(f"Embedding dimension: {stats['embedding_dimension']}")
    print(f"Companies: {len(stats['companies'])}")
    for company, count in stats['vectors_by_company'].items():
        print(f"  - {company}: {count} vectors")
    
    if stats['total_vectors'] == 0:
        print("\n⚠️ No data in vector database. Upload some PDFs first.")
        sys.exit(0)
    
    # Create visualization
    print("\n📊 Creating 3D visualization...")
    method = sys.argv[1] if len(sys.argv) > 1 else 'pca'
    
    fig = visualize_vectors(method=method, max_samples=2000)
    
    # Save to HTML
    output_file = f"vector_visualization_{method}.html"
    fig.write_html(output_file)
    print(f"✓ Visualization saved to: {output_file}")
    print("  Open this file in your browser to view the interactive 3D plot")
