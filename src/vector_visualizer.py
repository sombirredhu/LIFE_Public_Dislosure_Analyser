import logging
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
import plotly.graph_objects as go
from sklearn.decomposition import PCA
from src.embedder import get_or_create_collection

logger = logging.getLogger(__name__)

COMPANY_COLORS = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E2', '#F8B739', '#52B788', '#E63946', '#457B9D', '#F4A261', '#2A9D8F', '#E76F51']

def reduce_dimensions(embeddings: np.ndarray, n_components: int = 3) -> np.ndarray:
    n_samples = embeddings.shape[0]
    n_comp = min(n_components, n_samples, embeddings.shape[1])
    reducer = PCA(n_components=n_comp, random_state=42)
    reduced = reducer.fit_transform(embeddings)
    if reduced.shape[1] < n_components:
        reduced = np.hstack([reduced, np.zeros((reduced.shape[0], n_components - reduced.shape[1]))])
    return reduced

def get_vector_data(max_samples: Optional[int] = None) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
    collection = get_or_create_collection()
    total = collection.count()
    if total == 0: raise ValueError("No data in vector database")
    n_samples = min(max_samples, total) if max_samples else total
    results = collection.get(limit=n_samples, include=["embeddings", "metadatas"])
    return np.array(results["embeddings"]), results["metadatas"]

def create_2d_plot(embeddings_2d: np.ndarray, metadatas: List[Dict[str, Any]], title: str = "Vector Database 2D Visualization") -> go.Figure:
    companies = sorted(set(m["company"] for m in metadatas))
    fig = go.Figure()
    for i, company in enumerate(companies):
        indices = [idx for idx, m in enumerate(metadatas) if m["company"] == company]
        hover = [f"<b>{m['company']}</b><br>Period: {m['period_label']}<br>Section: {m['section']}<br>Page: {m['page_number']}" for m in [metadatas[idx] for idx in indices]]
        fig.add_trace(go.Scatter(x=embeddings_2d[indices, 0], y=embeddings_2d[indices, 1], mode='markers', name=company, marker=dict(size=7, color=COMPANY_COLORS[i % len(COMPANY_COLORS)], opacity=0.8), text=hover, hovertemplate='%{text}<extra></extra>'))
    fig.update_layout(title=dict(text=title, x=0.5), xaxis=dict(title='Dim 1'), yaxis=dict(title='Dim 2'), height=600)
    return fig

def create_3d_plot(embeddings_3d: np.ndarray, metadatas: List[Dict[str, Any]], title: str = "Vector Database 3D Visualization") -> go.Figure:
    companies = sorted(set(m["company"] for m in metadatas))
    fig = go.Figure()
    for i, company in enumerate(companies):
        indices = [idx for idx, m in enumerate(metadatas) if m["company"] == company]
        hover = [f"<b>{m['company']}</b><br>Period: {m['period_label']}<br>Section: {m['section']}<br>Page: {m['page_number']}" for m in [metadatas[idx] for idx in indices]]
        fig.add_trace(go.Scatter3d(x=embeddings_3d[indices, 0], y=embeddings_3d[indices, 1], z=embeddings_3d[indices, 2], mode='markers', name=company, marker=dict(size=5, color=COMPANY_COLORS[i % len(COMPANY_COLORS)], opacity=0.8), text=hover, hovertemplate='%{text}<extra></extra>'))
    fig.update_layout(title=dict(text=title, x=0.5), scene=dict(xaxis=dict(title='Dim 1'), yaxis=dict(title='Dim 2'), zaxis=dict(title='Dim 3')), margin=dict(l=0, r=0, t=50, b=0), height=700)
    return fig

def visualize_vectors(max_samples: Optional[int] = 2000, title: Optional[str] = None, n_dims: int = 3) -> go.Figure:
    embeddings, metadatas = get_vector_data(max_samples=max_samples)
    reduced = reduce_dimensions(embeddings, n_components=n_dims)
    title = title or f"Vector Database {n_dims}D Visualization (PCA)"
    return create_2d_plot(reduced, metadatas, title=title) if n_dims == 2 else create_3d_plot(reduced, metadatas, title=title)

def get_visualization_stats() -> Dict[str, Any]:
    try:
        collection = get_or_create_collection()
        total = collection.count()
        if total == 0: return {"total_vectors": 0, "companies": [], "vectors_by_company": {}, "embedding_dimension": 0}
        res = collection.get(include=["metadatas", "embeddings"], limit=1)
        dim = len(res["embeddings"][0]) if res["embeddings"] else 0
        metas = collection.get(include=["metadatas"])["metadatas"]
        vc = {}
        for m in metas: vc[m["company"]] = vc.get(m["company"], 0) + 1
        return {"total_vectors": total, "companies": sorted(vc.keys()), "vectors_by_company": vc, "embedding_dimension": dim}
    except Exception: return {"total_vectors": 0, "companies": [], "vectors_by_company": {}, "embedding_dimension": 0}
