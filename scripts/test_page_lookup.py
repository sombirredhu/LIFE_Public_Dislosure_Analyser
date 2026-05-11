"""
Test script to demonstrate L-page lookup functionality.
Shows how to search for L-pages by term.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pdf_parser import get_lpage_from_term, get_all_terms_for_lpage


def main():
    """Test L-page lookup functionality."""
    print("🔍 L-Page Lookup Test\n")
    
    # Test 1: Search by term
    print("=" * 60)
    print("Test 1: Search L-page by term")
    print("=" * 60)
    
    test_terms = [
        "GWP",
        "Premium Schedule",
        "Investments - Assets Held to Cover Linked Liabilities Schedule",
        "investments",  # partial match won't work - needs exact term
        "Revenue Account",
    ]
    
    for term in test_terms:
        lpage = get_lpage_from_term(term)
        if lpage:
            print(f"✅ '{term}' → {lpage}")
        else:
            print(f"❌ '{term}' → Not found")
    
    # Test 2: Get all terms for an L-page
    print("\n" + "=" * 60)
    print("Test 2: Get all terms for an L-page")
    print("=" * 60)
    
    test_lpages = ["L-1", "L-4", "L-14"]
    
    for lpage in test_lpages:
        terms = get_all_terms_for_lpage(lpage)
        if terms:
            print(f"✅ {lpage} → {', '.join(terms)}")
        else:
            print(f"❌ {lpage} → No terms found")
    
    print("\n" + "=" * 60)
    print("💡 Tip: Upload more PDFs with index pages to build a richer mapping!")
    print("=" * 60)


if __name__ == "__main__":
    main()
