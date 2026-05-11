"""
Test script for vector visualization.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.vector_visualizer import get_visualization_stats, visualize_vectors


def main():
    print("🎨 Testing Vector Visualization\n")
    
    # Get stats
    print("📊 Getting visualization stats...")
    stats = get_visualization_stats()
    
    print(f"   Total vectors: {stats['total_vectors']}")
    print(f"   Embedding dimension: {stats['embedding_dimension']}")
    print(f"   Companies: {len(stats['companies'])}")
    
    if stats['total_vectors'] == 0:
        print("\n⚠️ No data in vector database. Upload some PDFs first.")
        return
    
    print("\n   Vectors by company:")
    for company, count in stats['vectors_by_company'].items():
        percentage = (count / stats['total_vectors']) * 100
        print(f"      {company}: {count} ({percentage:.1f}%)")
    
    # Test visualization creation
    print("\n🎨 Creating 3D visualization (PCA)...")
    try:
        fig = visualize_vectors(method='pca', max_samples=500)
        print("   ✓ Visualization created successfully")
        
        # Save to HTML
        output_file = "test_vector_visualization.html"
        fig.write_html(output_file)
        print(f"   ✓ Saved to: {output_file}")
        print("   Open this file in your browser to view the interactive 3D plot")
        
        print("\n✅ All tests passed!")
    except Exception as e:
        print(f"\n❌ Failed to create visualization: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
