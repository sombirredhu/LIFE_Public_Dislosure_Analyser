"""
Test script to verify page-wise chunking with existing processed JSON files.
"""

import sys
import json
from pathlib import Path
from collections import Counter

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.chunker import chunk_document
from src.config import PROCESSED_OUTPUT_DIR, PAGE_WISE_CHUNKING, MAX_PAGE_TOKENS


def main():
    """Test page-wise chunking on existing JSON files."""
    print("=" * 80)
    print("PAGE-WISE CHUNKING TEST")
    print("=" * 80)
    print(f"PAGE_WISE_CHUNKING: {PAGE_WISE_CHUNKING}")
    print(f"MAX_PAGE_TOKENS: {MAX_PAGE_TOKENS}")
    print()
    
    # Find all processed JSON files (exclude page_definitions files)
    processed_dir = Path(PROCESSED_OUTPUT_DIR)
    json_files = [
        f for f in processed_dir.glob("*.json")
        if not f.name.endswith("_page_definitions.json")
        and not f.name.startswith("master_")
        and not f.name.endswith("_term_to_page.json")
        and not f.name == "custom_definitions.json"
    ]
    
    if not json_files:
        print(f"✗ No processed JSON files found in {PROCESSED_OUTPUT_DIR}")
        return
    
    print(f"Found {len(json_files)} processed JSON files:")
    for f in json_files:
        print(f"  - {f.name}")
    print()
    
    # Process each file
    total_chunks = 0
    total_pages = 0
    split_pages = 0
    companies_processed = []
    
    for json_file in json_files:
        print(f"\nProcessing: {json_file.name}")
        print("-" * 80)
        
        # Load parsed document
        with open(json_file, "r", encoding="utf-8") as f:
            parsed_doc = json.load(f)
        
        # Chunk document
        chunks = chunk_document(parsed_doc)
        
        # Analyze chunks
        company = parsed_doc["company"]
        pages = len(parsed_doc["pages"])
        chunk_count = len(chunks)
        
        # Count split pages
        split_count = sum(1 for c in chunks if c["metadata"].get("is_split", False))
        
        # Count content types
        content_types = Counter(c["metadata"]["content_type"] for c in chunks)
        
        # Check for company_full_name
        chunks_with_full_name = sum(1 for c in chunks if "company_full_name" in c["metadata"])
        
        # Check for page_label
        chunks_with_page_label = sum(1 for c in chunks if c["metadata"].get("page_label"))
        
        print(f"  Company: {company}")
        print(f"  Total Pages: {pages}")
        print(f"  Total Chunks: {chunk_count}")
        print(f"  Chunks with Split Pages: {split_count}")
        print(f"  Chunks with Company Full Name: {chunks_with_full_name}")
        print(f"  Chunks with Page Label: {chunks_with_page_label}")
        print(f"  Content Types: {dict(content_types)}")
        
        # Show sample chunk metadata
        if chunks:
            sample = chunks[0]["metadata"]
            print(f"\n  Sample Chunk Metadata:")
            print(f"    chunk_id: {sample['chunk_id']}")
            print(f"    page_number: {sample['page_number']}")
            print(f"    page_label: {sample.get('page_label', 'N/A')}")
            print(f"    company_full_name: {sample.get('company_full_name', 'N/A')}")
            print(f"    content_type: {sample['content_type']}")
            print(f"    is_split: {sample.get('is_split', False)}")
            print(f"    table_count: {sample.get('table_count', 0)}")
            print(f"    text_block_count: {sample.get('text_block_count', 0)}")
            print(f"    char_count: {sample['char_count']}")
        
        total_chunks += chunk_count
        total_pages += pages
        split_pages += split_count
        companies_processed.append(company)
    
    # Print summary
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Companies Processed: {len(companies_processed)}")
    print(f"  {', '.join(companies_processed)}")
    print(f"Total Pages: {total_pages}")
    print(f"Total Chunks: {total_chunks}")
    print(f"Split Pages: {split_pages}")
    print(f"Avg Chunks per Page: {total_chunks / total_pages:.2f}")
    print(f"Chunk Reduction: {((total_pages - total_chunks) / total_pages * 100):.1f}%")
    print()
    
    if PAGE_WISE_CHUNKING:
        print("✓ Page-wise chunking is ENABLED")
        print("✓ Each page is processed as a single semantic unit")
        print("✓ Company names and L-pages extracted from page content")
    else:
        print("⚠ Page-wise chunking is DISABLED (using legacy text-based chunking)")
    
    print()


if __name__ == "__main__":
    main()
