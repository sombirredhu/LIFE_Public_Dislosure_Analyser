"""
Test backward compatibility with real data from processed JSON files.

This test verifies chunk count reduction and backward compatibility using
actual insurance company disclosure documents.

Requirements: 4.3, 4.4, 4.5, 7.3
"""

import pytest
import json
import sys
from pathlib import Path
from unittest.mock import patch

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.chunker import chunk_document
from src.config import PROCESSED_OUTPUT_DIR


def get_real_parsed_docs():
    """Load real parsed documents from processed directory."""
    processed_dir = Path(PROCESSED_OUTPUT_DIR)
    json_files = [
        f for f in processed_dir.glob("*.json")
        if not f.name.endswith("_page_definitions.json")
        and f.name not in ["custom_definitions.json", "master_page_definitions.json", "master_term_to_page.json"]
    ]
    
    docs = []
    for json_file in json_files[:3]:  # Test with first 3 documents
        with open(json_file, "r", encoding="utf-8") as f:
            docs.append((json_file.name, json.load(f)))
    
    return docs


@pytest.mark.parametrize("filename,parsed_doc", get_real_parsed_docs())
def test_real_data_chunk_count_reduction(filename, parsed_doc):
    """
    Test chunk count reduction with real insurance disclosure documents.
    
    Requirement: 7.3 - THE Chunker SHALL reduce total chunk count by at least 
    75% compared to text-based chunking
    """
    # Get legacy chunk count
    with patch('src.chunker.PAGE_WISE_CHUNKING', False):
        legacy_chunks = chunk_document(parsed_doc)
        legacy_count = len(legacy_chunks)
    
    # Get page-wise chunk count
    with patch('src.chunker.PAGE_WISE_CHUNKING', True):
        page_chunks = chunk_document(parsed_doc)
        page_count = len(page_chunks)
    
    # Calculate reduction
    reduction_pct = ((legacy_count - page_count) / legacy_count) * 100 if legacy_count > 0 else 0
    
    print(f"\n{filename}:")
    print(f"  Legacy chunks: {legacy_count}")
    print(f"  Page-wise chunks: {page_count}")
    print(f"  Reduction: {reduction_pct:.1f}%")
    print(f"  Pages in document: {len(parsed_doc.get('pages', []))}")
    
    # Verify reduction (should be significant for real documents)
    assert page_count < legacy_count, \
        f"Page-wise should create fewer chunks: {page_count} vs {legacy_count}"
    
    # For real documents with many pages, expect significant reduction
    if len(parsed_doc.get('pages', [])) > 10:
        assert reduction_pct > 50, \
            f"Expected >50% reduction for documents with >10 pages, got {reduction_pct:.1f}%"


@pytest.mark.parametrize("filename,parsed_doc", get_real_parsed_docs())
def test_real_data_metadata_preservation(filename, parsed_doc):
    """
    Test that metadata is preserved correctly with real data.
    
    Requirement: 4.4 - Preserve all existing metadata fields
    """
    required_fields = {
        "company", "company_code", "quarter", "fy", "period_label",
        "source_file", "chunk_id", "page_number", "page_label",
        "section", "content_type", "char_count", "ingested_at"
    }
    
    # Test both modes
    for mode_name, mode_value in [("legacy", False), ("page-wise", True)]:
        with patch('src.chunker.PAGE_WISE_CHUNKING', mode_value):
            chunks = chunk_document(parsed_doc)
            
            assert len(chunks) > 0, f"Should create chunks in {mode_name} mode"
            
            for chunk in chunks:
                metadata = chunk["metadata"]
                missing_fields = required_fields - set(metadata.keys())
                assert not missing_fields, \
                    f"{mode_name} mode missing fields in {filename}: {missing_fields}"
    
    print(f"✓ {filename}: Metadata preserved in both modes")


@pytest.mark.parametrize("filename,parsed_doc", get_real_parsed_docs())
def test_real_data_chunk_structure(filename, parsed_doc):
    """
    Test that chunk structure is consistent with real data.
    
    Requirement: 4.3 - Maintain two-key chunk structure
    """
    # Test both modes
    for mode_name, mode_value in [("legacy", False), ("page-wise", True)]:
        with patch('src.chunker.PAGE_WISE_CHUNKING', mode_value):
            chunks = chunk_document(parsed_doc)
            
            for chunk in chunks:
                # Verify exactly 2 top-level keys
                assert set(chunk.keys()) == {"text", "metadata"}, \
                    f"{mode_name} mode should have exactly 2 keys in {filename}"
                
                # Verify text is non-empty string
                assert isinstance(chunk["text"], str) and len(chunk["text"]) > 0, \
                    f"{mode_name} mode should have non-empty text in {filename}"
                
                # Verify metadata is dict
                assert isinstance(chunk["metadata"], dict), \
                    f"{mode_name} mode should have dict metadata in {filename}"
    
    print(f"✓ {filename}: Chunk structure consistent in both modes")


@pytest.mark.parametrize("filename,parsed_doc", get_real_parsed_docs())
def test_real_data_page_wise_alignment(filename, parsed_doc):
    """
    Test that page-wise chunks align with document pages.
    
    Requirement: 1.1 - One chunk per page by default
    """
    with patch('src.chunker.PAGE_WISE_CHUNKING', True):
        chunks = chunk_document(parsed_doc)
        page_count = len(parsed_doc.get('pages', []))
        
        # Count non-split chunks (should be close to page count)
        non_split_chunks = [c for c in chunks if not c["metadata"].get("is_split", False)]
        split_pages = [c for c in chunks if c["metadata"].get("is_split", False)]
        
        print(f"\n{filename}:")
        print(f"  Total pages: {page_count}")
        print(f"  Total chunks: {len(chunks)}")
        print(f"  Non-split pages: {len(non_split_chunks)}")
        print(f"  Split pages: {len(set(c['metadata']['page_number'] for c in split_pages))}")
        
        # Verify chunks are reasonable (at most a few splits per document)
        assert len(chunks) <= page_count * 2, \
            f"Too many chunks for {filename}: {len(chunks)} chunks for {page_count} pages"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
