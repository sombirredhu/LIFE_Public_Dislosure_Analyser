"""
Test vector DB retrieval for all L-pages to ensure RAG accuracy.
Tests if queries return results from all 6 companies.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.retriever import retrieve
from src.pdf_parser import get_lpage_from_term
import json

# Test queries for each L-page we fixed
TEST_QUERIES = [
    "premium",
    "revenue account",
    "balance sheet",
    "receipts and payments",
    "commission",
    "operating expenses",
    "benefits paid",
    "share capital",
    "shareholding pattern",
    "reserves and surplus",
    "borrowings",
    "investment shareholders",
    "investment policyholders",
    "linked liabilities",
    "loans",
    "fixed assets",
    "cash and bank balance"
]

EXPECTED_COMPANIES = [
    "Aditya Birla",
    "Bhartiaxa",
    "Edelweiss",
    "IciciPrruLife",
    "ShriramInsurance",
    "TataAIA"
]

def test_retrieval(query, top_k=10):
    """Test retrieval for a query and return company coverage."""
    print(f"{'='*80}")
    print(f"Query: '{query}'")
    print(f"{'='*80}")
    
    # Get L-page mapping
    lpage = get_lpage_from_term(query.lower())
    if lpage:
        print(f"[OK] Mapped to: {lpage}")
    else:
        print(f"[X] No L-page mapping found")
    
    # Retrieve chunks
    try:
        chunks = retrieve(query, top_k=top_k)
        
        if not chunks:
            print(f"[X] No chunks retrieved")
            return set()
        
        print(f"[OK] Retrieved {len(chunks)} chunks")
        
        # Extract unique companies from results
        companies_found = set()
        for chunk in chunks:
            metadata = chunk.get("metadata", {})
            company = metadata.get("company", "Unknown")
            companies_found.add(company)
        
        print(f"\nCompanies in results ({len(companies_found)}/6):")
        for company in sorted(companies_found):
            print(f"  [OK] {company}")
        
        # Check for missing companies
        missing = set(EXPECTED_COMPANIES) - companies_found
        if missing:
            print(f"\n[WARN] Missing companies ({len(missing)}):")
            for company in sorted(missing):
                print(f"  [X] {company}")
        
        # Show sample chunks
        print(f"\nSample chunks:")
        for i, chunk in enumerate(chunks[:3], 1):
            metadata = chunk.get("metadata", {})
            print(f"\n  [{i}] {metadata.get('company', 'Unknown')} - {metadata.get('period_label', 'Unknown')}")
            print(f"      Page: {metadata.get('page_label', 'Unknown')} - {metadata.get('section', 'Unknown')}")
            print(f"      Chunk ID: {metadata.get('chunk_id', 'Unknown')}")
            text_preview = chunk.get("text", "")[:150].replace("\n", " ")
            print(f"      Text: {text_preview}...")
        
        return companies_found
        
    except Exception as e:
        print(f"[X] Error during retrieval: {e}")
        import traceback
        traceback.print_exc()
        return set()

def main():
    """Run all tests and generate report."""
    print("="*80)
    print("VECTOR DB RETRIEVAL TEST")
    print("Testing if queries return results from all 6 companies")
    print("="*80)
    
    results = {}
    
    for query in TEST_QUERIES:
        companies_found = test_retrieval(query, top_k=20)
        results[query] = {
            "companies_found": len(companies_found),
            "companies": list(companies_found),
            "missing": list(set(EXPECTED_COMPANIES) - companies_found)
        }
    
    # Generate summary report
    print("\n" + "="*80)
    print("SUMMARY REPORT")
    print("="*80)
    
    total_queries = len(TEST_QUERIES)
    full_coverage = sum(1 for r in results.values() if r["companies_found"] == 6)
    partial_coverage = sum(1 for r in results.values() if 0 < r["companies_found"] < 6)
    no_results = sum(1 for r in results.values() if r["companies_found"] == 0)
    
    print(f"\nTotal queries tested: {total_queries}")
    print(f"[OK] Full coverage (6/6 companies): {full_coverage} ({full_coverage/total_queries*100:.1f}%)")
    print(f"[WARN] Partial coverage (1-5 companies): {partial_coverage} ({partial_coverage/total_queries*100:.1f}%)")
    print(f"[X] No results: {no_results} ({no_results/total_queries*100:.1f}%)")
    
    # Queries with issues
    if partial_coverage > 0 or no_results > 0:
        print(f"\n[WARN] Queries with issues:")
        for query, result in results.items():
            if result["companies_found"] < 6:
                print(f"\n  '{query}': {result['companies_found']}/6 companies")
                if result["missing"]:
                    print(f"    Missing: {', '.join(result['missing'])}")
    
    # Save detailed results
    output_file = Path(__file__).parent / "vector_db_test_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n[OK] Detailed results saved to: {output_file}")
    
    # Overall assessment
    print(f"\n{'='*80}")
    if full_coverage == total_queries:
        print("[PASS] All queries return results from all 6 companies")
    elif full_coverage >= total_queries * 0.8:
        print("[PARTIAL] Most queries work, but some need optimization")
    else:
        print("[FAIL] Significant retrieval issues detected")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
