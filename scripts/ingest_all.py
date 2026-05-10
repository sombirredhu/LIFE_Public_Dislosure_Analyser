"""
Batch ingestion script - ingest all PDFs from data/pdfs/ directory.
Run this after adding new PDF files to index them.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestor import ingest_directory
from src.config import PDF_INPUT_DIR
from src.embedder import get_collection_stats


def main():
    """Main ingestion script."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Ingest all PDF files from data/pdfs/ directory"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-indexing of already indexed files"
    )
    parser.add_argument(
        "--dir",
        type=str,
        default=PDF_INPUT_DIR,
        help=f"Directory containing PDF files (default: {PDF_INPUT_DIR})"
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("INSURANCE PD REPORT INGESTION")
    print("=" * 80)
    print(f"Source Directory: {args.dir}")
    print(f"Force Re-index: {args.force}")
    print()
    
    # Show current collection stats
    print("Current ChromaDB Collection Stats:")
    stats = get_collection_stats()
    print(f"  Total Chunks: {stats['total_chunks']}")
    print(f"  Unique Files: {stats['unique_files']}")
    
    if stats['chunks_by_company']:
        print(f"  Indexed Companies:")
        for company, count in sorted(stats['chunks_by_company'].items()):
            print(f"    {company}: {count} chunks")
    
    print()
    
    # Ingest all PDFs
    result = ingest_directory(args.dir, force_reindex=args.force)
    
    # Print summary
    print()
    print("=" * 80)
    print("INGESTION COMPLETE")
    print("=" * 80)
    print(f"Total Files Found: {result['total_files']}")
    print(f"Successfully Ingested: {result['success_count']}")
    print(f"Skipped (Already Indexed): {result['skipped_count']}")
    print(f"Errors: {result['error_count']}")
    
    if result['error_count'] > 0:
        print("\nFiles with errors:")
        for r in result['results']:
            if r['status'] == 'error':
                print(f"  ✗ {r['source_file']}: {r['message']}")
    
    # Show updated stats
    print("\nUpdated ChromaDB Collection Stats:")
    stats = get_collection_stats()
    print(f"  Total Chunks: {stats['total_chunks']}")
    print(f"  Unique Files: {stats['unique_files']}")
    
    if stats['chunks_by_company']:
        print(f"  Indexed Companies:")
        for company, count in sorted(stats['chunks_by_company'].items()):
            print(f"    {company}: {count} chunks")
    
    print()
    
    if result['success_count'] > 0:
        print("✓ Ingestion successful! You can now:")
        print("  1. Test queries: python scripts/test_query.py --q \"your question\"")
        print("  2. Launch UI: streamlit run app/streamlit_app.py")
    elif result['skipped_count'] > 0:
        print("⊘ All files were already indexed. Use --force to re-index.")
    else:
        print("✗ No files were successfully ingested.")


if __name__ == "__main__":
    main()
