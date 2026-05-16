"""
Integration test for page splitting in chunk_document.
"""

import pytest
from src.chunker import chunk_document


def test_chunk_document_with_oversized_page():
    """Test that chunk_document properly splits oversized pages."""
    # Create a document with one oversized page
    # Create text with sentence boundaries that exceeds 7600 tokens
    sentences = [f"This is sentence number {i} with additional content to make it longer. " for i in range(500)]
    large_text = "".join(sentences)  # ~50000 chars = ~12500 tokens
    
    doc = {
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
                "tables": [],
                "text_blocks": ["Normal page content"]
            },
            {
                "page_number": 2,
                "page_label": "L-2",
                "section": "Claims",
                "tables": [],
                "text_blocks": [large_text]  # Oversized page
            }
        ]
    }
    
    chunks = chunk_document(doc)
    
    # Should have at least 3 chunks (1 normal + 2+ split chunks)
    assert len(chunks) >= 3
    
    # Page 1 should have is_split=False
    page1_chunks = [c for c in chunks if c["metadata"]["page_number"] == 1]
    assert len(page1_chunks) == 1
    assert page1_chunks[0]["metadata"]["is_split"] is False
    
    # Page 2 should have is_split=True and multiple parts
    page2_chunks = [c for c in chunks if c["metadata"]["page_number"] == 2]
    assert len(page2_chunks) >= 2
    
    for chunk in page2_chunks:
        assert chunk["metadata"]["is_split"] is True
        assert chunk["metadata"]["total_parts"] == len(page2_chunks)
        assert 1 <= chunk["metadata"]["part_number"] <= len(page2_chunks)


def test_chunk_document_with_large_table():
    """Test that chunk_document properly splits large tables."""
    # Create a large table
    headers = ["Column1", "Column2", "Column3"]
    rows = [[f"Row{i}_" + "x"*60, f"Data{i}A_" + "y"*60, f"Data{i}B_" + "z"*60] for i in range(200)]
    
    header_text = " | ".join(headers)
    row_texts = [" | ".join(row) for row in rows]
    raw_text = header_text + "\n" + "\n".join(row_texts)
    
    doc = {
        "company": "Test Insurance",
        "company_code": "TEST_INS",
        "quarter": "Q1",
        "fy": "FY25",
        "period_label": "Q1 FY2024-25",
        "source_file": "TEST_INS_Q1_FY25.pdf",
        "total_pages": 1,
        "pages": [
            {
                "page_number": 1,
                "page_label": "L-1",
                "section": "Revenue Account",
                "tables": [
                    {
                        "headers": headers,
                        "rows": rows,
                        "raw_text": raw_text
                    }
                ],
                "text_blocks": []
            }
        ]
    }
    
    chunks = chunk_document(doc)
    
    # Should create multiple chunks
    assert len(chunks) >= 2
    
    # All chunks should have is_split=True
    for chunk in chunks:
        assert chunk["metadata"]["is_split"] is True
        assert chunk["metadata"]["page_number"] == 1
        
        # Each chunk should contain the headers
        assert header_text in chunk["text"]


def test_chunk_document_normal_pages():
    """Test that normal pages are not split."""
    doc = {
        "company": "Test Insurance",
        "company_code": "TEST_INS",
        "quarter": "Q1",
        "fy": "FY25",
        "period_label": "Q1 FY2024-25",
        "source_file": "TEST_INS_Q1_FY25.pdf",
        "total_pages": 3,
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
                "text_blocks": ["This is normal text."]
            },
            {
                "page_number": 2,
                "page_label": "L-2",
                "section": "Claims",
                "tables": [],
                "text_blocks": ["Another normal page."]
            },
            {
                "page_number": 3,
                "page_label": "L-3",
                "section": "Balance Sheet",
                "tables": [],
                "text_blocks": ["Third normal page."]
            }
        ]
    }
    
    chunks = chunk_document(doc)
    
    # Should have exactly 3 chunks (one per page)
    assert len(chunks) == 3
    
    # All chunks should have is_split=False
    for chunk in chunks:
        assert chunk["metadata"]["is_split"] is False
        assert "total_parts" not in chunk["metadata"]
        assert "part_number" not in chunk["metadata"]


def test_chunk_document_rejected_page():
    """Test that pages with unsplittable content are rejected."""
    # Create a table with a single row that exceeds max_tokens
    huge_row = ["x" * 40000]  # ~10000 tokens in a single cell
    
    doc = {
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
                "tables": [],
                "text_blocks": ["Normal page"]
            },
            {
                "page_number": 2,
                "page_label": "L-2",
                "section": "Claims",
                "tables": [
                    {
                        "headers": ["Column1"],
                        "rows": [huge_row],
                        "raw_text": "Column1\n" + huge_row[0]
                    }
                ],
                "text_blocks": []
            }
        ]
    }
    
    chunks = chunk_document(doc)
    
    # Should only have 1 chunk (page 2 rejected)
    assert len(chunks) == 1
    assert chunks[0]["metadata"]["page_number"] == 1
