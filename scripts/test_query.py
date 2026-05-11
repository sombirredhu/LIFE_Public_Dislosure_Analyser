"""
Test query script - ask questions from command line.
Use this to test the RAG pipeline before launching the UI.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.rag_pipeline import answer_question
from src.embedder import get_collection_stats


def main():
    """Main test query script."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Ask questions about insurance PD reports"
    )
    parser.add_argument(
        "--q", "--question",
        type=str,
        required=True,
        dest="question",
        help="Question to ask"
    )
    parser.add_argument(
        "--company",
        type=str,
        help="Filter to specific company code (e.g., HDFC_Life)"
    )
    parser.add_argument(
        "--quarter",
        type=str,
        help="Filter to specific quarter (e.g., Q1)"
    )
    parser.add_argument(
        "--fy",
        type=str,
        help="Filter to specific financial year (e.g., FY25)"
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=None,
        help="Number of chunks to retrieve (default: from config)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show retrieved chunks for debugging"
    )
    
    args = parser.parse_args()
    
    # Check if database has data
    stats = get_collection_stats()
    if stats['total_chunks'] == 0:
        print("✗ No data in ChromaDB. Please run ingestion first:")
        print("  python scripts/ingest_all.py")
        sys.exit(1)
    
    print("=" * 80)
    print("INSURANCE PD REPORT QUERY")
    print("=" * 80)
    print(f"Question: {args.question}")
    
    # Build filters
    filters = {}
    if args.company:
        filters["company_code"] = args.company
        print(f"Filter: Company = {args.company}")
    if args.quarter:
        filters["quarter"] = args.quarter
        print(f"Filter: Quarter = {args.quarter}")
    if args.fy:
        filters["fy"] = args.fy
        print(f"Filter: FY = {args.fy}")
    
    print()
    print("Retrieving relevant information and generating answer...")
    print()
    
    try:
        # Get answer
        result = answer_question(
            args.question,
            filters=filters if filters else None,
            top_k=args.top_k
        )
        
        # Print answer
        print("=" * 80)
        print("ANSWER")
        print("=" * 80)
        print(result["answer"])
        print()
        
        # Print metadata
        print("=" * 80)
        print("METADATA")
        print("=" * 80)
        print(f"Confidence:  {result['confidence']}")
        print(f"Chunks Used: {result['chunks_used']}")
        print(f"Model Used:  {result.get('model_used', 'N/A')}")
        print(f"Sources:     {', '.join(result['sources']) if result['sources'] else 'None'}")
    
    except ValueError as e:
        print(f"✗ Configuration error: {e}")
        print("\nPlease ensure:")
        print("1. .env file exists with OPENROUTER_API_KEY")
        print("2. PDF files have been ingested: python scripts/ingest_all.py")
        sys.exit(1)
    
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
