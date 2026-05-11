"""
Tests specifically for _chunk_page_wise() function to verify task 2.4 requirements.
"""

import pytest
from datetime import datetime
from src.chunker import _chunk_page_wise, chunk_document
from src.config import PAGE_WISE_CHUNKING


def test_chunk_page_wise_basic_functionality():
    """
    Test that _chunk_page_wise() creates one chunk per page with correct structure.
    Validates Requirements: 1.1, 1.4, 1.5, 1.6, 1.7, 1.8
    """
    parsed_doc = {
        "company": "Test Insurance",
        "company_code": "TEST_INS",
        "quarter": "Q1",
        "fy": "FY25",
        "period_label": "Q1 FY2024-25",
        "source_file": "TEST_INS_Q1_FY25.pdf",
        "total_pages": 2,
        "pages": [
            {
                "page_number": 1,
                "page_label": "L-1",
                "section": "Revenue Account",
                "tables": [
                    {
                        "headers": ["Particulars", "Amount"],
                        "rows": [["Premium Income", "1000"]],
                        "raw_text": "Particulars | Amount\nPremium Income | 1000"
                    }
                ],
                "text_blocks": ["This is a test document."]
            },
            {
                "page_number": 2,
                "page_label": "L-2",
                "section": "Claims",
                "tables": [],
                "text_blocks": ["Claims information for the quarter."]
            }
        ]
    }
    
    base_metadata = {
        "company": parsed_doc["company"],
        "company_code": parsed_doc["company_code"],
        "quarter": parsed_doc["quarter"],
        "fy": parsed_doc["fy"],
        "period_label": parsed_doc["period_label"],
        "source_file": parsed_doc["source_file"],
    }
    
    chunks = _chunk_page_wise(parsed_doc, base_metadata)
    
    # Should create 2 chunks (one per page)
    assert len(chunks) == 2
    
    # Verify first chunk
    chunk1 = chunks[0]
    assert "text" in chunk1
    assert "metadata" in chunk1
    
    # Verify chunk_id format: {company_code}_{quarter}_{fy}_page{page_number}
    assert chunk1["metadata"]["chunk_id"] == "TEST_INS_Q1_FY25_page1"
    
    # Verify content_type is "page"
    assert chunk1["metadata"]["content_type"] == "page"
    
    # Verify metadata fields are populated
    assert chunk1["metadata"]["company"] == "Test Insurance"
    assert chunk1["metadata"]["company_code"] == "TEST_INS"
    assert chunk1["metadata"]["quarter"] == "Q1"
    assert chunk1["metadata"]["fy"] == "FY25"
    assert chunk1["metadata"]["period_label"] == "Q1 FY2024-25"
    assert chunk1["metadata"]["source_file"] == "TEST_INS_Q1_FY25.pdf"
    assert chunk1["metadata"]["page_number"] == 1
    assert chunk1["metadata"]["page_label"] == "L-1"
    assert chunk1["metadata"]["section"] == "Revenue Account"
    
    # Verify char_count is set
    assert chunk1["metadata"]["char_count"] == len(chunk1["text"])
    
    # Verify ingested_at timestamp is set
    assert "ingested_at" in chunk1["metadata"]
    # Verify it's a valid ISO 8601 timestamp
    datetime.fromisoformat(chunk1["metadata"]["ingested_at"])
    
    # Verify second chunk
    chunk2 = chunks[1]
    assert chunk2["metadata"]["chunk_id"] == "TEST_INS_Q1_FY25_page2"
    assert chunk2["metadata"]["page_number"] == 2
    assert chunk2["metadata"]["page_label"] == "L-2"
    assert chunk2["metadata"]["section"] == "Claims"


def test_chunk_page_wise_combines_content():
    """
    Test that _chunk_page_wise() calls _combine_page_content() and combines tables and text.
    Validates Requirement: 1.1
    """
    parsed_doc = {
        "company": "Test Insurance",
        "company_code": "TEST_INS",
        "quarter": "Q1",
        "fy": "FY25",
        "period_label": "Q1 FY2024-25",
        "source_file": "TEST_INS_Q1_FY25.pdf",
        "pages": [
            {
                "page_number": 1,
                "page_label": "L-1",
                "section": "Test",
                "tables": [
                    {
                        "headers": ["Col1", "Col2"],
                        "rows": [["Val1", "Val2"]],
                        "raw_text": "Col1 | Col2\nVal1 | Val2"
                    }
                ],
                "text_blocks": ["Text block 1", "Text block 2"]
            }
        ]
    }
    
    base_metadata = {
        "company": parsed_doc["company"],
        "company_code": parsed_doc["company_code"],
        "quarter": parsed_doc["quarter"],
        "fy": parsed_doc["fy"],
        "period_label": parsed_doc["period_label"],
        "source_file": parsed_doc["source_file"],
    }
    
    chunks = _chunk_page_wise(parsed_doc, base_metadata)
    
    assert len(chunks) == 1
    
    # Verify that the chunk text contains both table and text blocks
    chunk_text = chunks[0]["text"]
    assert "Col1 | Col2\nVal1 | Val2" in chunk_text
    assert "Text block 1" in chunk_text
    assert "Text block 2" in chunk_text
    
    # Verify tables come before text blocks (separated by \n\n)
    table_pos = chunk_text.index("Col1 | Col2")
    text_pos = chunk_text.index("Text block 1")
    assert table_pos < text_pos


def test_chunk_page_wise_skips_empty_pages():
    """
    Test that _chunk_page_wise() skips pages with no tables and no text_blocks.
    Validates Requirement: 1.2
    """
    parsed_doc = {
        "company": "Test Insurance",
        "company_code": "TEST_INS",
        "quarter": "Q1",
        "fy": "FY25",
        "period_label": "Q1 FY2024-25",
        "source_file": "TEST_INS_Q1_FY25.pdf",
        "pages": [
            {
                "page_number": 1,
                "page_label": "L-1",
                "section": "Test",
                "tables": [],
                "text_blocks": []
            },
            {
                "page_number": 2,
                "page_label": "L-2",
                "section": "Test",
                "tables": [],
                "text_blocks": ["Valid content"]
            },
            {
                "page_number": 3,
                "page_label": "L-3",
                "section": "Test",
                "tables": [],
                "text_blocks": ["   "]  # Whitespace only
            }
        ]
    }
    
    base_metadata = {
        "company": parsed_doc["company"],
        "company_code": parsed_doc["company_code"],
        "quarter": parsed_doc["quarter"],
        "fy": parsed_doc["fy"],
        "period_label": parsed_doc["period_label"],
        "source_file": parsed_doc["source_file"],
    }
    
    chunks = _chunk_page_wise(parsed_doc, base_metadata)
    
    # Should only create 1 chunk (page 2 with valid content)
    # Pages 1 and 3 should be skipped
    assert len(chunks) == 1
    assert chunks[0]["metadata"]["page_number"] == 2


def test_chunk_page_wise_handles_missing_arrays():
    """
    Test that _chunk_page_wise() handles missing tables or text_blocks arrays.
    Validates Requirement: 1.3
    """
    parsed_doc = {
        "company": "Test Insurance",
        "company_code": "TEST_INS",
        "quarter": "Q1",
        "fy": "FY25",
        "period_label": "Q1 FY2024-25",
        "source_file": "TEST_INS_Q1_FY25.pdf",
        "pages": [
            {
                "page_number": 1,
                "page_label": "L-1",
                "section": "Test",
                # Missing tables key
                "text_blocks": ["Text content"]
            },
            {
                "page_number": 2,
                "page_label": "L-2",
                "section": "Test",
                "tables": [
                    {
                        "headers": ["Col1"],
                        "rows": [["Val1"]],
                        "raw_text": "Col1\nVal1"
                    }
                ]
                # Missing text_blocks key
            }
        ]
    }
    
    base_metadata = {
        "company": parsed_doc["company"],
        "company_code": parsed_doc["company_code"],
        "quarter": parsed_doc["quarter"],
        "fy": parsed_doc["fy"],
        "period_label": parsed_doc["period_label"],
        "source_file": parsed_doc["source_file"],
    }
    
    chunks = _chunk_page_wise(parsed_doc, base_metadata)
    
    # Should create 2 chunks without errors
    assert len(chunks) == 2
    
    # Page 1 should have only text
    assert "Text content" in chunks[0]["text"]
    
    # Page 2 should have only table
    assert "Col1\nVal1" in chunks[1]["text"]


def test_chunk_page_wise_metadata_statistics():
    """
    Test that _chunk_page_wise() adds table_count, text_block_count, and is_split metadata.
    Validates Requirements: 1.4 (metadata enrichment)
    """
    parsed_doc = {
        "company": "Test Insurance",
        "company_code": "TEST_INS",
        "quarter": "Q1",
        "fy": "FY25",
        "period_label": "Q1 FY2024-25",
        "source_file": "TEST_INS_Q1_FY25.pdf",
        "pages": [
            {
                "page_number": 1,
                "page_label": "L-1",
                "section": "Test",
                "tables": [
                    {"headers": ["C1"], "rows": [["V1"]], "raw_text": "C1\nV1"},
                    {"headers": ["C2"], "rows": [["V2"]], "raw_text": "C2\nV2"}
                ],
                "text_blocks": ["Text 1", "Text 2", "Text 3"]
            }
        ]
    }
    
    base_metadata = {
        "company": parsed_doc["company"],
        "company_code": parsed_doc["company_code"],
        "quarter": parsed_doc["quarter"],
        "fy": parsed_doc["fy"],
        "period_label": parsed_doc["period_label"],
        "source_file": parsed_doc["source_file"],
    }
    
    chunks = _chunk_page_wise(parsed_doc, base_metadata)
    
    assert len(chunks) == 1
    
    # Verify metadata statistics
    metadata = chunks[0]["metadata"]
    assert metadata["table_count"] == 2
    assert metadata["text_block_count"] == 3
    assert metadata["is_split"] == False


def test_chunk_page_wise_returns_list():
    """
    Test that _chunk_page_wise() returns a list of chunks.
    Validates Requirement: Return list of chunks
    """
    parsed_doc = {
        "company": "Test Insurance",
        "company_code": "TEST_INS",
        "quarter": "Q1",
        "fy": "FY25",
        "period_label": "Q1 FY2024-25",
        "source_file": "TEST_INS_Q1_FY25.pdf",
        "pages": []
    }
    
    base_metadata = {
        "company": parsed_doc["company"],
        "company_code": parsed_doc["company_code"],
        "quarter": parsed_doc["quarter"],
        "fy": parsed_doc["fy"],
        "period_label": parsed_doc["period_label"],
        "source_file": parsed_doc["source_file"],
    }
    
    chunks = _chunk_page_wise(parsed_doc, base_metadata)
    
    # Should return a list (even if empty)
    assert isinstance(chunks, list)


def test_chunk_document_uses_page_wise_chunking():
    """
    Test that chunk_document() uses page-wise chunking when PAGE_WISE_CHUNKING is True.
    """
    if not PAGE_WISE_CHUNKING:
        pytest.skip("PAGE_WISE_CHUNKING is disabled")
    
    parsed_doc = {
        "company": "Test Insurance",
        "company_code": "TEST_INS",
        "quarter": "Q1",
        "fy": "FY25",
        "period_label": "Q1 FY2024-25",
        "source_file": "TEST_INS_Q1_FY25.pdf",
        "pages": [
            {
                "page_number": 1,
                "page_label": "L-1",
                "section": "Test",
                "tables": [{"headers": ["C1"], "rows": [["V1"]], "raw_text": "C1\nV1"}],
                "text_blocks": ["Text content"]
            }
        ]
    }
    
    chunks = chunk_document(parsed_doc)
    
    # Should create page-wise chunks
    assert len(chunks) == 1
    assert chunks[0]["metadata"]["content_type"] == "page"
    assert chunks[0]["metadata"]["chunk_id"] == "TEST_INS_Q1_FY25_page1"


def test_chunk_page_wise_multiple_pages():
    """
    Test that _chunk_page_wise() correctly processes multiple pages.
    """
    parsed_doc = {
        "company": "Test Insurance",
        "company_code": "TEST_INS",
        "quarter": "Q1",
        "fy": "FY25",
        "period_label": "Q1 FY2024-25",
        "source_file": "TEST_INS_Q1_FY25.pdf",
        "pages": [
            {
                "page_number": i,
                "page_label": f"L-{i}",
                "section": f"Section {i}",
                "tables": [],
                "text_blocks": [f"Content for page {i}"]
            }
            for i in range(1, 6)  # 5 pages
        ]
    }
    
    base_metadata = {
        "company": parsed_doc["company"],
        "company_code": parsed_doc["company_code"],
        "quarter": parsed_doc["quarter"],
        "fy": parsed_doc["fy"],
        "period_label": parsed_doc["period_label"],
        "source_file": parsed_doc["source_file"],
    }
    
    chunks = _chunk_page_wise(parsed_doc, base_metadata)
    
    # Should create 5 chunks
    assert len(chunks) == 5
    
    # Verify each chunk has correct page_number
    for i, chunk in enumerate(chunks, start=1):
        assert chunk["metadata"]["page_number"] == i
        assert chunk["metadata"]["chunk_id"] == f"TEST_INS_Q1_FY25_page{i}"
        assert f"Content for page {i}" in chunk["text"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
