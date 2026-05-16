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
    Reduce high-dimensional embeddings to 2D or 3D for visualization.

    Args:
        embeddings: Array of shape (n_samples, n_features)
        method:     'pca' or 'tsne'
        n_components: 2 for 2D plot, 3 for 3D plot

    Returns:
        Reduced embeddings of shape (n_samples, n_components)
    """
    n_samples = embeddings.shape[0]
    logger.info(
        "Reducing %d embeddings from %dD to %dD using %s",
        n_samples, embeddings.shape[1], n_components, method.upper()
    )

    if method.lower() == 'pca':
        n_comp = min(n_components, n_samples, embeddings.shape[1])
        reducer = PCA(n_components=n_comp, random_state=42)
        reduced = reducer.fit_transform(embeddings)
        variance_explained = sum(reducer.explained_variance_ratio_) * 100
        logger.info("PCA variance explained: %.2f%%", variance_explained)
        # Pad with zeros if PCA returned fewer dims than requested
        if reduced.shape[1] < n_components:
            pad = np.zeros((reduced.shape[0], n_components - reduced.shape[1]))
            reduced = np.hstack([reduced, pad])

    elif method.lower() == 'tsne':
        # t-SNE in 3D is extremely slow and often crashes; cap at 2D
        safe_components = min(n_components, 2)
        if n_components == 3:
            logger.warning(
                "t-SNE 3D is unreliable — falling back to 2D. Use PCA for 3D."
            )
        perplexity = min(30, max(5, n_samples // 5))
        reducer = TSNE(
            n_components=safe_components,
            random_state=42,
            perplexity=perplexity,
            n_iter=1000,
            learning_rate='auto',
            init='pca',
        )
        reduced = reducer.fit_transform(embeddings)
        # Pad with zeros so caller always gets n_components dims
        if reduced.shape[1] < n_components:
            pad = np.zeros((reduced.shape[0], n_components - reduced.shape[1]))
            reduced = np.hstack([reduced, pad])
        logger.info("t-SNE reduction completed (actual dims: %d)", reduced.shape[1])

    else:
        raise ValueError(f"Unknown method: {method}. Use 'pca' or 'tsne'")

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
    
    logger.info("Fetching %d vectors from ChromaDB", n_samples)
    
    # Get data from collection
    results = collection.get(
        limit=n_samples,
        include=["embeddings", "metadatas"]
    )
    
    embeddings = np.array(results["embeddings"])
    metadatas = results["metadatas"]
    
    logger.info("Fetched %d embeddings of dimension %d", embeddings.shape[0], embeddings.shape[1])
    
    return embeddings, metadatas


def create_2d_plot(
    embeddings_2d: np.ndarray,
    metadatas: List[Dict[str, Any]],
    title: str = "Vector Database 2D Visualization"
) -> go.Figure:
    """Create interactive 2D scatter plot with Plotly."""
    company_to_color = {}
    companies = sorted(set(m["company"] for m in metadatas))
    for i, company in enumerate(companies):
        company_to_color[company] = COMPANY_COLORS[i % len(COMPANY_COLORS)]

    fig = go.Figure()
    for company in companies:
        indices = [i for i, m in enumerate(metadatas) if m["company"] == company]
        x = embeddings_2d[indices, 0]
        y = embeddings_2d[indices, 1]
        hover_texts = [
            f"<b>{metadatas[idx]['company']}</b><br>"
            f"Period: {metadatas[idx]['period_label']}<br>"
            f"Section: {metadatas[idx]['section']}<br>"
            f"Page: {metadatas[idx]['page_number']}<br>"
            f"Type: {metadatas[idx]['content_type']}"
            for idx in indices
        ]
        fig.add_trace(go.Scatter(
            x=x, y=y,
            mode='markers',
            name=company,
            marker=dict(size=7, color=company_to_color[company], opacity=0.8,
                        line=dict(width=0.5, color='white')),
            text=hover_texts,
            hovertemplate='%{text}<extra></extra>'
        ))

    fig.update_layout(
        title=dict(text=title, x=0.5, xanchor='center', font=dict(size=20)),
        xaxis=dict(title='Dimension 1', showgrid=True, gridcolor='#E0E0E0'),
        yaxis=dict(title='Dimension 2', showgrid=True, gridcolor='#E0E0E0'),
        legend=dict(title=dict(text='Companies'), font=dict(size=12),
                    bgcolor='rgba(255,255,255,0.8)', bordercolor='#CCC', borderwidth=1),
        margin=dict(l=40, r=20, t=60, b=40),
        hovermode='closest',
        height=600
    )
    return fig



def create_3d_plot(
    embeddings_3d: np.ndarray,
    metadatas: List[Dict[str, Any]],
    title: str = "Vector Database 3D Visualization"
) -> go.Figure:
    """Create interactive 3D scatter plot with Plotly."""
    company_to_color = {}
    companies = sorted(set(m["company"] for m in metadatas))
    for i, company in enumerate(companies):
        company_to_color[company] = COMPANY_COLORS[i % len(COMPANY_COLORS)]

    logger.info("Creating 3D plot for %d companies", len(companies))
    fig = go.Figure()
    for company in companies:
        indices = [i for i, m in enumerate(metadatas) if m["company"] == company]
        x = embeddings_3d[indices, 0]
        y = embeddings_3d[indices, 1]
        z = embeddings_3d[indices, 2]
        hover_texts = [
            f"<b>{metadatas[idx]['company']}</b><br>"
            f"Period: {metadatas[idx]['period_label']}<br>"
            f"Section: {metadatas[idx]['section']}<br>"
            f"Page: {metadatas[idx]['page_number']}<br>"
            f"Type: {metadatas[idx]['content_type']}"
            for idx in indices
        ]
        fig.add_trace(go.Scatter3d(
            x=x, y=y, z=z,
            mode='markers',
            name=company,
            marker=dict(size=5, color=company_to_color[company], opacity=0.8,
                        line=dict(width=0.5, color='white')),
            text=hover_texts,
            hovertemplate='%{text}<extra></extra>'
        ))

    fig.update_layout(
        title=dict(text=title, x=0.5, xanchor='center', font=dict(size=20, color='#2C3E50')),
        scene=dict(
            xaxis=dict(title='Dim 1', backgroundcolor='#F8F9FA', gridcolor='#E0E0E0'),
            yaxis=dict(title='Dim 2', backgroundcolor='#F8F9FA', gridcolor='#E0E0E0'),
            zaxis=dict(title='Dim 3', backgroundcolor='#F8F9FA', gridcolor='#E0E0E0'),
            bgcolor='#FFFFFF'
        ),
        legend=dict(title=dict(text='Companies'), font=dict(size=12),
                    bgcolor='rgba(255,255,255,0.8)', bordercolor='#CCC', borderwidth=1),
        margin=dict(l=0, r=0, t=50, b=0),
        hovermode='closest',
        height=700
    )
    return fig


def visualize_vectors(
    method: str = 'pca',
    max_samples: Optional[int] = 2000,
    title: Optional[str] = None,
    n_dims: int = 3,
) -> go.Figure:
    """
    Main function to create 2D or 3D visualization of vector database.

    Args:
        method:      'pca' or 'tsne'
        max_samples: Maximum number of samples to visualize
        title:       Custom plot title
        n_dims:      2 for 2D scatter, 3 for 3D scatter
                     Note: t-SNE always reduces to 2D for reliability.
    """
    try:
        embeddings, metadatas = get_vector_data(max_samples=max_samples)

        # t-SNE is always 2D for reliability
        actual_dims = 2 if method.lower() == 'tsne' else n_dims
        reduced = reduce_dimensions(embeddings, method=method, n_components=actual_dims)

        if title is None:
            dim_label = f"{actual_dims}D"
            title = f"Vector Database {dim_label} Visualization ({method.upper()})"

        if actual_dims == 2:
            fig = create_2d_plot(reduced, metadatas, title=title)
        else:
            fig = create_3d_plot(reduced, metadatas, title=title)

        logger.info("Visualization created successfully (%dD, method=%s)", actual_dims, method)
        return fig

    except Exception as e:
        logger.error("Failed to create visualization: %s", e)
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
        logger.error("Failed to get visualization stats: %s", e)
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
