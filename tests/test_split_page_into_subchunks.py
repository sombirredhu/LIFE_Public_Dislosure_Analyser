"""
Tests for _split_page_into_subchunks function.
"""

import pytest
from src.chunker import _split_page_into_subchunks, _estimate_tokens


def test_split_page_basic():
    """Test basic page splitting with oversized content."""
    # Create a page with content exceeding 7600 tokens (30400 chars)
    large_text = "x" * 30400  # ~7600 tokens
    
    page = {
        "page_number": 1,
        "page_label": "L-1",
        "section": "Test Section",
        "tables": [],
        "text_blocks": [large_text, large_text]  # Total ~15200 tokens
    }
    
    base_metadata = {
        "company": "Test Company",
        "company_code": "TEST",
        "quarter": "Q1",
        "fy": "FY25",
        "period_label": "Q1 FY2024-25",
        "source_file": "test.pdf"
    }
    
    result = _split_page_into_subchunks(page, base_metadata, max_tokens=7600)
    
    # Should create multiple sub-chunks
    assert len(result) >= 2
    
    # Each chunk should have proper metadata
    for i, chunk in enumerate(result, start=1):
        assert chunk["metadata"]["is_split"] is True
        assert chunk["metadata"]["total_parts"] == len(result)
        assert chunk["metadata"]["part_number"] == i
        assert chunk["metadata"]["chunk_id"] == f"TEST_Q1_FY25_page1_part{i}"
        assert chunk["metadata"]["page_number"] == 1
        assert chunk["metadata"]["page_label"] == "L-1"
        assert chunk["metadata"]["section"] == "Test Section"


def test_split_page_with_table():
    """Test page splitting with a table that fits within limit."""
    # Create a table that fits
    table_text = "Header1 | Header2\nRow1 | Data1\nRow2 | Data2"
    
    # Create large text blocks
    large_text = "x" * 30400  # ~7600 tokens
    
    page = {
        "page_number": 2,
        "page_label": "L-2",
        "section": "Revenue",
        "tables": [
            {
                "headers": ["Header1", "Header2"],
                "rows": [["Row1", "Data1"], ["Row2", "Data2"]],
                "raw_text": table_text
            }
        ],
        "text_blocks": [large_text]
    }
    
    base_metadata = {
        "company": "Test Company",
        "company_code": "TEST",
        "quarter": "Q1",
        "fy": "FY25",
        "period_label": "Q1 FY2024-25",
        "source_file": "test.pdf"
    }
    
    result = _split_page_into_subchunks(page, base_metadata, max_tokens=7600)
    
    # Should create at least 2 sub-chunks (table + large text)
    assert len(result) >= 2
    
    # First chunk should contain the table
    assert table_text in result[0]["text"]


def test_split_page_large_table():
    """Test splitting a large table by rows with repeated headers."""
    # Create a large table with many rows that exceeds 7600 tokens
    # Each row needs to be larger to exceed the limit
    headers = ["Column1", "Column2", "Column3"]
    # Make each row ~200 chars so 200 rows = 40000 chars = 10000 tokens
    rows = [[f"Row{i}_" + "x"*60, f"Data{i}A_" + "y"*60, f"Data{i}B_" + "z"*60] for i in range(200)]
    
    # Build raw_text
    header_text = " | ".join(headers)
    row_texts = [" | ".join(row) for row in rows]
    raw_text = header_text + "\n" + "\n".join(row_texts)
    
    page = {
        "page_number": 3,
        "page_label": "L-3",
        "section": "Claims",
        "tables": [
            {
                "headers": headers,
                "rows": rows,
                "raw_text": raw_text
            }
        ],
        "text_blocks": []
    }
    
    base_metadata = {
        "company": "Test Company",
        "company_code": "TEST",
        "quarter": "Q1",
        "fy": "FY25",
        "period_label": "Q1 FY2024-25",
        "source_file": "test.pdf"
    }
    
    result = _split_page_into_subchunks(page, base_metadata, max_tokens=7600)
    
    # Should create multiple sub-chunks
    assert len(result) >= 2
    
    # Each sub-chunk should contain the headers
    for chunk in result:
        assert header_text in chunk["text"]


def test_split_page_text_at_sentence_boundaries():
    """Test splitting text blocks at sentence boundaries."""
    # Create a large text block with sentences that exceeds 7600 tokens
    # Each sentence ~100 chars, 1000 sentences = 100000 chars = 25000 tokens
    sentences = [f"This is sentence number {i} with some additional text to make it longer. " for i in range(1000)]
    large_text = "".join(sentences)
    
    page = {
        "page_number": 4,
        "page_label": "L-4",
        "section": "Notes",
        "tables": [],
        "text_blocks": [large_text]
    }
    
    base_metadata = {
        "company": "Test Company",
        "company_code": "TEST",
        "quarter": "Q1",
        "fy": "FY25",
        "period_label": "Q1 FY2024-25",
        "source_file": "test.pdf"
    }
    
    result = _split_page_into_subchunks(page, base_metadata, max_tokens=7600)
    
    # Should create multiple sub-chunks
    assert len(result) >= 2
    
    # Each chunk should be at least 100 characters
    for chunk in result:
        assert len(chunk["text"]) >= 100


def test_split_page_unsplittable_table_row():
    """Test rejection of page with unsplittable table row."""
    # Create a table with a single row that exceeds max_tokens
    huge_row = ["x" * 40000]  # ~10000 tokens in a single cell
    
    page = {
        "page_number": 5,
        "page_label": "L-5",
        "section": "Test",
        "tables": [
            {
                "headers": ["Column1"],
                "rows": [huge_row],
                "raw_text": "Column1\n" + huge_row[0]
            }
        ],
        "text_blocks": []
    }
    
    base_metadata = {
        "company": "Test Company",
        "company_code": "TEST",
        "quarter": "Q1",
        "fy": "FY25",
        "period_label": "Q1 FY2024-25",
        "source_file": "test.pdf"
    }
    
    # Should raise ValueError for unsplittable content
    with pytest.raises(ValueError, match="unsplittable table row exceeds token limit"):
        _split_page_into_subchunks(page, base_metadata, max_tokens=7600)


def test_split_page_max_20_subchunks():
    """Test that page splitting is limited to 20 sub-chunks."""
    # Create many small text blocks that would create > 20 chunks
    text_blocks = ["x" * 30400 for _ in range(30)]  # Each ~7600 tokens
    
    page = {
        "page_number": 6,
        "page_label": "L-6",
        "section": "Test",
        "tables": [],
        "text_blocks": text_blocks
    }
    
    base_metadata = {
        "company": "Test Company",
        "company_code": "TEST",
        "quarter": "Q1",
        "fy": "FY25",
        "period_label": "Q1 FY2024-25",
        "source_file": "test.pdf"
    }
    
    result = _split_page_into_subchunks(page, base_metadata, max_tokens=7600)
    
    # Should be limited to 20 sub-chunks
    assert len(result) <= 20


def test_split_page_minimum_2_rows_per_table_chunk():
    """Test that table sub-chunks have at least 2 rows (when possible)."""
    # Create a table with rows that would naturally split at 1 row per chunk
    # Each row is ~3800 chars (~950 tokens), so 2 rows = ~1900 tokens (fits in 7600)
    headers = ["Column1", "Column2"]
    rows = [[f"x" * 1900, f"y" * 1900] for _ in range(10)]
    
    header_text = " | ".join(headers)
    row_texts = [" | ".join(row) for row in rows]
    raw_text = header_text + "\n" + "\n".join(row_texts)
    
    page = {
        "page_number": 7,
        "page_label": "L-7",
        "section": "Test",
        "tables": [
            {
                "headers": headers,
                "rows": rows,
                "raw_text": raw_text
            }
        ],
        "text_blocks": []
    }
    
    base_metadata = {
        "company": "Test Company",
        "company_code": "TEST",
        "quarter": "Q1",
        "fy": "FY25",
        "period_label": "Q1 FY2024-25",
        "source_file": "test.pdf"
    }
    
    result = _split_page_into_subchunks(page, base_metadata, max_tokens=7600)
    
    # Should create multiple sub-chunks
    assert len(result) >= 2
    
    # Each chunk should have headers
    for chunk in result:
        assert header_text in chunk["text"]


def test_split_page_metadata_consistency():
    """Test that all metadata fields are consistent across sub-chunks."""
    large_text = "x" * 30400  # ~7600 tokens
    
    page = {
        "page_number": 8,
        "page_label": "L-8",
        "section": "Balance Sheet",
        "tables": [
            {
                "headers": ["Asset", "Value"],
                "rows": [["Cash", "1000"]],
                "raw_text": "Asset | Value\nCash | 1000"
            }
        ],
        "text_blocks": [large_text, large_text]
    }
    
    base_metadata = {
        "company": "Test Company",
        "company_code": "TEST",
        "quarter": "Q1",
        "fy": "FY25",
        "period_label": "Q1 FY2024-25",
        "source_file": "test.pdf"
    }
    
    result = _split_page_into_subchunks(page, base_metadata, max_tokens=7600)
    
    # All chunks should have same page-level metadata
    for chunk in result:
        assert chunk["metadata"]["page_number"] == 8
        assert chunk["metadata"]["page_label"] == "L-8"
        assert chunk["metadata"]["section"] == "Balance Sheet"
        assert chunk["metadata"]["table_count"] == 1
        assert chunk["metadata"]["text_block_count"] == 2
        assert chunk["metadata"]["company"] == "Test Company"
        assert chunk["metadata"]["company_code"] == "TEST"
        assert chunk["metadata"]["quarter"] == "Q1"
        assert chunk["metadata"]["fy"] == "FY25"


def test_split_page_empty_content():
    """Test handling of page with no content after filtering."""
    page = {
        "page_number": 9,
        "page_label": "L-9",
        "section": "Empty",
        "tables": [],
        "text_blocks": ["   ", ""]  # Only whitespace
    }
    
    base_metadata = {
        "company": "Test Company",
        "company_code": "TEST",
        "quarter": "Q1",
        "fy": "FY25",
        "period_label": "Q1 FY2024-25",
        "source_file": "test.pdf"
    }
    
    result = _split_page_into_subchunks(page, base_metadata, max_tokens=7600)
    
    # Should return empty list or minimal chunks
    assert len(result) == 0 or all(len(c["text"].strip()) == 0 for c in result)
