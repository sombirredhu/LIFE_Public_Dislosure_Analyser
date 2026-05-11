# Vector Database 3D Visualization Guide

## Overview

The 3D Vector Visualization feature allows you to see your document embeddings in 3D space. Each company is displayed in a unique color, making it easy to understand how documents are distributed semantically.

---

## Features

### 🎨 Color-Coded Companies
- Each company gets a unique, distinct color
- Easy to identify which documents belong to which company
- 15 predefined colors that cycle if you have more companies

### 📊 Interactive 3D Plot
- **Rotate**: Click and drag to rotate the view
- **Zoom**: Scroll or pinch to zoom in/out
- **Pan**: Right-click and drag to pan
- **Hover**: See detailed information about each point
- **Legend**: Click company names to show/hide them

### 🔬 Dimensionality Reduction Methods

**PCA (Principal Component Analysis)**:
- ✅ Fast and deterministic
- ✅ Preserves global structure
- ✅ Good for quick overview
- ✅ Shows variance explained percentage
- 📊 Best for: Initial exploration

**t-SNE (t-Distributed Stochastic Neighbor Embedding)**:
- ✅ Better visual separation
- ✅ Preserves local structure
- ⚠️ Slower with large datasets
- ⚠️ Non-deterministic (results vary slightly)
- 📊 Best for: Finding clusters and patterns

---

## How to Use

### From Streamlit App

1. **Open the app**:
   ```bash
   streamlit run app/streamlit_app.py
   ```

2. **Go to "3D Visualization" tab**

3. **Configure settings**:
   - Choose reduction method (PCA or t-SNE)
   - Set max samples (fewer = faster)

4. **Click "Generate 3D Visualization"**

5. **Interact with the plot**:
   - Rotate, zoom, pan
   - Hover over points for details
   - Click legend to filter companies

6. **Download** (optional):
   - Click "Download as HTML"
   - Share or view offline

### From Command Line

```bash
# Using PCA (fast)
python src/vector_visualizer.py pca

# Using t-SNE (better separation)
python src/vector_visualizer.py tsne

# Output: vector_visualization_pca.html or vector_visualization_tsne.html
```

---

## Understanding the Visualization

### What Each Point Represents
- Each point = one chunk of text from your documents
- Position = semantic meaning in 3D space
- Color = company that owns the document
- Proximity = semantic similarity

### Interpreting Patterns

**Clusters**:
- Groups of points close together
- Indicate similar content or topics
- May represent specific sections (e.g., all "Premium Schedule" pages)

**Company Separation**:
- Companies with unique content will be more separated
- Companies with similar reporting will overlap
- Complete overlap = very similar content

**Outliers**:
- Isolated points far from others
- May indicate unique or unusual content
- Could be errors or special sections

**Dimensions**:
- Dimension 1, 2, 3 = Principal components or t-SNE dimensions
- Higher variance = more important dimension
- No direct interpretation (abstract semantic features)

---

## Examples

### Example 1: Well-Separated Companies
```
Company A (Red) -------- Company B (Blue)
        |                      |
    Cluster 1              Cluster 2
```
**Interpretation**: Companies have distinct content or reporting styles

### Example 2: Overlapping Companies
```
    Company A (Red)
         \/
    Overlap Area
         /\
    Company B (Blue)
```
**Interpretation**: Companies have similar content (e.g., standard IRDAI formats)

### Example 3: Multiple Clusters per Company
```
Company A:
  Cluster 1 (Premium data)
  Cluster 2 (Claims data)
  Cluster 3 (Ratios)
```
**Interpretation**: Different sections of reports form distinct clusters

---

## Technical Details

### Dimensionality Reduction

**Original Space**: 384 dimensions (sentence-transformers embedding)
**Reduced Space**: 3 dimensions (for visualization)

**PCA Process**:
1. Center the data (subtract mean)
2. Compute covariance matrix
3. Find principal components (eigenvectors)
4. Project data onto top 3 components
5. Variance explained: typically 20-40%

**t-SNE Process**:
1. Compute pairwise similarities in high-dimensional space
2. Initialize random 3D positions
3. Iteratively adjust positions to preserve local structure
4. Perplexity parameter: auto-adjusted based on dataset size

### Performance

| Dataset Size | PCA Time | t-SNE Time | Recommended |
|--------------|----------|------------|-------------|
| 100 vectors  | < 1s     | ~2s        | Either      |
| 500 vectors  | < 1s     | ~5s        | Either      |
| 1000 vectors | ~1s      | ~15s       | PCA first   |
| 2000 vectors | ~2s      | ~45s       | PCA first   |
| 5000+ vectors| ~5s      | 2-5 min    | PCA only    |

### Memory Usage

- Embeddings: ~1.5 KB per vector (384 dimensions × 4 bytes)
- 1000 vectors: ~1.5 MB
- 5000 vectors: ~7.5 MB
- Visualization: ~500 KB HTML file

---

## Color Palette

The system uses 15 distinct colors:

1. 🔴 Red (#FF6B6B)
2. 🔵 Teal (#4ECDC4)
3. 🔵 Blue (#45B7D1)
4. 🟠 Light Salmon (#FFA07A)
5. 🟢 Mint (#98D8C8)
6. 🟡 Yellow (#F7DC6F)
7. 🟣 Purple (#BB8FCE)
8. 🔵 Sky Blue (#85C1E2)
9. 🟠 Orange (#F8B739)
10. 🟢 Green (#52B788)
11. 🔴 Dark Red (#E63946)
12. 🔵 Steel Blue (#457B9D)
13. 🟠 Sandy Brown (#F4A261)
14. 🟢 Teal Green (#2A9D8F)
15. 🟠 Burnt Orange (#E76F51)

If you have more than 15 companies, colors will cycle.

---

## Use Cases

### 1. Quality Assurance
**Goal**: Verify data consistency
**How**: Check if similar sections cluster together
**Example**: All "Premium Schedule" pages should be close

### 2. Outlier Detection
**Goal**: Find unusual or erroneous data
**How**: Look for isolated points far from clusters
**Example**: Misclassified pages or data errors

### 3. Company Comparison
**Goal**: Compare reporting styles
**How**: See how companies separate or overlap
**Example**: Identify companies with unique reporting

### 4. Content Analysis
**Goal**: Understand document structure
**How**: Identify distinct clusters within companies
**Example**: See how different sections are distributed

### 5. Data Coverage
**Goal**: Verify all companies are represented
**How**: Check that all colors appear in the plot
**Example**: Ensure no company is missing

---

## Tips & Best Practices

### For Best Results

1. **Start with PCA**:
   - Quick overview
   - Deterministic results
   - Good for large datasets

2. **Use t-SNE for Deep Dive**:
   - Better cluster separation
   - More intuitive groupings
   - Best with < 2000 samples

3. **Adjust Sample Size**:
   - More samples = more complete picture
   - Fewer samples = faster rendering
   - 500-1000 is a good balance

4. **Interact with the Plot**:
   - Rotate to see from different angles
   - Zoom in on interesting clusters
   - Use legend to focus on specific companies

5. **Compare Methods**:
   - Generate both PCA and t-SNE
   - Look for consistent patterns
   - Different views reveal different insights

### Troubleshooting

**Problem**: Plot is too crowded
**Solution**: Reduce max samples or zoom in

**Problem**: t-SNE is too slow
**Solution**: Use PCA or reduce samples

**Problem**: Can't see patterns
**Solution**: Try different reduction method or rotate view

**Problem**: Colors are hard to distinguish
**Solution**: Use legend to hide some companies

**Problem**: Points overlap too much
**Solution**: Try t-SNE for better separation

---

## API Reference

### Python Functions

```python
from src.vector_visualizer import (
    visualize_vectors,
    get_visualization_stats,
    reduce_dimensions,
    create_3d_plot
)

# Get statistics
stats = get_visualization_stats()
# Returns: {
#   "total_vectors": int,
#   "companies": List[str],
#   "vectors_by_company": Dict[str, int],
#   "embedding_dimension": int
# }

# Create visualization
fig = visualize_vectors(
    method='pca',           # 'pca', 'tsne', or 'umap'
    max_samples=2000,       # Max vectors to visualize
    title="Custom Title"    # Optional custom title
)

# Save to HTML
fig.write_html("visualization.html")

# Reduce dimensions manually
embeddings_3d = reduce_dimensions(
    embeddings,             # numpy array (n_samples, n_features)
    method='pca',          # 'pca', 'tsne', or 'umap'
    n_components=3         # Number of dimensions
)
```

---

## Advanced Features

### UMAP Support (Optional)

If you install UMAP, you can use it as an alternative:

```bash
pip install umap-learn
```

Then use:
```python
fig = visualize_vectors(method='umap')
```

**UMAP Benefits**:
- Faster than t-SNE
- Better preserves global structure than t-SNE
- More consistent results

---

## Limitations

1. **Dimensionality Loss**: 3D can't capture all 384 dimensions
   - Information is lost in reduction
   - Some relationships may not be visible

2. **Interpretation**: Axes have no direct meaning
   - Dimensions are abstract combinations
   - Focus on relative positions, not absolute values

3. **Scalability**: Large datasets are slow
   - t-SNE: O(n²) complexity
   - Recommend < 5000 samples for t-SNE

4. **Non-determinism**: t-SNE results vary
   - Different runs give slightly different layouts
   - Overall patterns should be consistent

---

## Future Enhancements

Potential improvements:
- 2D visualization option
- Animation over time (as data grows)
- Custom color schemes
- Filter by quarter/FY
- Highlight specific sections
- Export to various formats
- Cluster analysis overlay
- Similarity search from plot

---

## References

- **PCA**: [Scikit-learn PCA Documentation](https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.PCA.html)
- **t-SNE**: [Scikit-learn t-SNE Documentation](https://scikit-learn.org/stable/modules/generated/sklearn.manifold.TSNE.html)
- **Plotly**: [Plotly 3D Scatter Documentation](https://plotly.com/python/3d-scatter-plots/)

---

**Last Updated**: 2026-05-10  
**Version**: 1.0  
**Status**: Production Ready ✅
