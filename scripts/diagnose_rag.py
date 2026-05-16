"""
RAG System Diagnostic Script

Checks the health and configuration of the RAG pipeline.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import (
    OPENROUTER_API_KEY, PAGE_WISE_CHUNKING, TOP_K_SIMPLE, TOP_K_COMPLEX,
    SIMILARITY_THRESHOLD, EMBEDDING_MODEL, LLM_MODEL_FREE, LLM_MODEL_PAID,
    CHROMA_DB_PATH, PDF_INPUT_DIR
)
from src.embedder import get_collection_stats, get_indexed_companies, get_available_quarters, get_available_fys
from src.retriever import retrieve
import json

def print_header(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")

def print_section(title):
    print(f"\n{title}")
    print("-" * len(title))

def check_config():
    """Check configuration settings."""
    print_header("RAG SYSTEM DIAGNOSTICS")
    
    print_section("1. Configuration")
    print(f"✓ API Key: {'Set' if OPENROUTER_API_KEY else '❌ NOT SET'}")
    print(f"✓ Chunking Strategy: {'Page-wise' if PAGE_WISE_CHUNKING else 'Text-based'}")
    print(f"✓ Embedding Model: {EMBEDDING_MODEL}")
    print(f"✓ LLM Free Model: {LLM_MODEL_FREE}")
    print(f"✓ LLM Paid Model: {LLM_MODEL_PAID}")
    print(f"✓ Top-K Simple: {TOP_K_SIMPLE}")
    print(f"✓ Top-K Complex: {TOP_K_COMPLEX}")
    print(f"✓ Similarity Threshold: {SIMILARITY_THRESHOLD}")
    print(f"✓ ChromaDB Path: {CHROMA_DB_PATH}")
    print(f"✓ PDF Input Dir: {PDF_INPUT_DIR}")

def check_database():
    """Check ChromaDB status."""
    print_section("2. Vector Database Status")
    
    try:
        stats = get_collection_stats()
        print(f"✓ Total Chunks: {stats['total_chunks']}")
        print(f"✓ Unique Files: {stats['unique_files']}")
        print(f"✓ Companies Indexed: {len(stats['chunks_by_company'])}")
        
        if stats['total_chunks'] == 0:
            print("\n❌ WARNING: No data indexed!")
            print("   Run: python scripts/ingest_all.py")
            return False
        
        print("\nChunks by Company:")
        for company, count in sorted(stats['chunks_by_company'].items()):
            print(f"  • {company}: {count} chunks")
        
        print("\nIndexed Files:")
        for file in stats['files']:
            print(f"  • {file}")
        
        return True
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def check_metadata():
    """Check metadata extraction."""
    print_section("3. Metadata Extraction")
    
    try:
        companies = get_indexed_companies()
        quarters = get_available_quarters()
        fys = get_available_fys()
        
        print(f"✓ Companies: {', '.join(companies) if companies else 'None'}")
        print(f"✓ Quarters: {', '.join(quarters) if quarters else 'None'}")
        print(f"✓ Financial Years: {', '.join(fys) if fys else 'None'}")
        
        if not companies:
            print("\n❌ WARNING: No companies found in metadata!")
            return False
        
        return True
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_retrieval():
    """Test retrieval functionality."""
    print_section("4. Retrieval Test")
    
    try:
        test_query = "total premium"
        print(f"Test Query: '{test_query}'")
        print(f"Retrieving top 5 chunks...\n")
        
        chunks = retrieve(test_query, top_k=5)
        
        if not chunks:
            print("❌ WARNING: No chunks retrieved!")
            print("   Possible issues:")
            print("   - Similarity threshold too high")
            print("   - No relevant data indexed")
            print("   - Embedding model mismatch")
            return False
        
        print(f"✓ Retrieved {len(chunks)} chunks\n")
        
        for i, chunk in enumerate(chunks, 1):
            meta = chunk['metadata']
            score = chunk['score']
            text_preview = chunk['text'][:100].replace('\n', ' ')
            
            print(f"{i}. Score: {score:.3f} | {meta['company']} | Page {meta['page_number']}")
            print(f"   Section: {meta.get('section', 'unknown')}")
            print(f"   Preview: {text_preview}...")
            print()
        
        # Check score distribution
        avg_score = sum(c['score'] for c in chunks) / len(chunks)
        max_score = max(c['score'] for c in chunks)
        min_score = min(c['score'] for c in chunks)
        
        print(f"Score Statistics:")
        print(f"  • Max: {max_score:.3f}")
        print(f"  • Avg: {avg_score:.3f}")
        print(f"  • Min: {min_score:.3f}")
        
        if max_score < 0.3:
            print(f"\n⚠️  WARNING: Low similarity scores (max: {max_score:.3f})")
            print("   Consider:")
            print("   - Lowering SIMILARITY_THRESHOLD")
            print("   - Checking query relevance")
            print("   - Verifying embedding model")
        
        return True
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_pdfs():
    """Check available PDF files."""
    print_section("5. Available PDF Files")
    
    try:
        pdf_dir = Path(PDF_INPUT_DIR)
        if not pdf_dir.exists():
            print(f"❌ PDF directory not found: {pdf_dir}")
            return False
        
        pdf_files = list(pdf_dir.glob("*.pdf"))
        
        if not pdf_files:
            print(f"❌ No PDF files found in {pdf_dir}")
            print("   Add PDF files following naming convention:")
            print("   {COMPANY_CODE}_{QUARTER}_{FY}.pdf")
            return False
        
        print(f"✓ Found {len(pdf_files)} PDF files:\n")
        
        from src.embedder import is_already_indexed
        
        for pdf in sorted(pdf_files):
            indexed = is_already_indexed(pdf.name)
            status = "✓ Indexed" if indexed else "⚠️  Not indexed"
            print(f"  {status}: {pdf.name}")
        
        not_indexed = [p for p in pdf_files if not is_already_indexed(p.name)]
        if not_indexed:
            print(f"\n⚠️  {len(not_indexed)} files not indexed")
            print("   Run: python scripts/ingest_all.py")
        
        return True
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def generate_recommendations(results):
    """Generate recommendations based on diagnostic results."""
    print_section("6. Recommendations")
    
    config_ok, db_ok, meta_ok, retrieval_ok, pdfs_ok = results
    
    if not config_ok:
        print("❌ CRITICAL: Configuration issues detected")
        print("   1. Set OPENROUTER_API_KEY in .env file")
        print("   2. Verify all required settings are present")
        return
    
    if not db_ok:
        print("❌ CRITICAL: Database is empty or inaccessible")
        print("   1. Run: python scripts/ingest_all.py")
        print("   2. Check ChromaDB path and permissions")
        return
    
    if not meta_ok:
        print("❌ CRITICAL: Metadata extraction failed")
        print("   1. Re-index PDFs: python scripts/ingest_all.py --force")
        print("   2. Check PDF file naming convention")
        return
    
    if not retrieval_ok:
        print("⚠️  WARNING: Retrieval issues detected")
        print("   1. Check similarity threshold (current: {})".format(SIMILARITY_THRESHOLD))
        print("   2. Verify embedding model compatibility")
        print("   3. Test with different queries")
        return
    
    if not pdfs_ok:
        print("⚠️  WARNING: PDF file issues detected")
        print("   1. Add missing PDF files to data/pdfs/")
        print("   2. Follow naming convention: {COMPANY_CODE}_{QUARTER}_{FY}.pdf")
        print("   3. Run ingestion: python scripts/ingest_all.py")
        return
    
    # All checks passed
    print("✅ All systems operational!")
    print("\nOptimization suggestions:")
    
    stats = get_collection_stats()
    if stats['total_chunks'] < 500:
        print("  • Index more companies for better cross-company analysis")
    
    if SIMILARITY_THRESHOLD < 0.25:
        print(f"  • Consider increasing SIMILARITY_THRESHOLD to 0.35 for better relevance")
    
    if not PAGE_WISE_CHUNKING:
        print("  • Enable PAGE_WISE_CHUNKING for better semantic coherence")
    
    print("\nNext steps:")
    print("  1. Test RAG with: python scripts/test_query.py --q 'your question'")
    print("  2. Launch UI with: streamlit run app/streamlit_app.py")
    print("  3. Monitor answer quality and adjust settings as needed")

def main():
    """Run all diagnostic checks."""
    results = []
    
    # Run checks
    config_ok = True  # Config check doesn't return bool
    check_config()
    results.append(config_ok)
    
    db_ok = check_database()
    results.append(db_ok)
    
    meta_ok = check_metadata()
    results.append(meta_ok)
    
    retrieval_ok = test_retrieval()
    results.append(retrieval_ok)
    
    pdfs_ok = check_pdfs()
    results.append(pdfs_ok)
    
    # Generate recommendations
    generate_recommendations(results)
    
    print(f"\n{'='*70}")
    print("  DIAGNOSTIC COMPLETE")
    print(f"{'='*70}\n")
    
    # Exit code
    if all(results):
        print("✅ Status: HEALTHY")
        return 0
    else:
        print("⚠️  Status: NEEDS ATTENTION")
        return 1

if __name__ == "__main__":
    sys.exit(main())
