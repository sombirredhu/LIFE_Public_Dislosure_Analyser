"""
Tests for chunker output shape and required metadata fields.
"""

import pytest
from src.chunker import chunk_document, _detect_content_type, _estimate_tokens, _combine_page_content

_REQUIRED_METADATA = {
    "chunk_id", "company", "company_code", "quarter", "fy",
    "period_label", "source_file", "page_number", "page_label",
    "section", "content_type", "char_count", "ingested_at",
}

_SAMPLE_DOC = {
    "company":      "HDFC Life",
    "company_code": "HDFC_Life",
    "quarter":      "Q1",
    "fy":           "FY25",
    "period_label": "Q1 FY2024-25",
    "source_file":  "HDFC_Life_Q1_FY25.pdf",
    "total_pages":  2,
    "pages": [
        {
            "page_number": 1,
            "page_label":  "",
            "section":     "unknown",
            "text_blocks": ["Key Highlights of the quarter results for HDFC Life Insurance Company Limited."],
            "tables":      [],
        },
        {
            "page_number": 2,
            "page_label":  "L-1",
            "section":     "Revenue Account",
            "text_blocks": [
                "The gross written premium for Q1 FY2024-25 was Rs. 8432 crore, "
                "representing a 7% growth over the same period last year."
            ],
            "tables": [
                {
                    "headers":  ["Particulars", "Q1 FY25 (Rs Cr)", "Q1 FY24 (Rs Cr)"],
                    "rows":     [["Gross Written Premium", "8432", "7891"]],
                    "raw_text": "Particulars | Q1 FY25 (Rs Cr) | Q1 FY24 (Rs Cr)\nGross Written Premium | 8432 | 7891",
                }
            ],
        },
    ],
}


def test_chunks_have_exactly_two_top_level_keys():
    chunks = chunk_document(_SAMPLE_DOC)
    for chunk in chunks:
        assert set(chunk.keys()) == {"text", "metadata"}, (
            f"Expected {{text, metadata}} but got {set(chunk.keys())}"
        )


def test_chunk_id_inside_metadata():
    chunks = chunk_document(_SAMPLE_DOC)
    for chunk in chunks:
        assert "chunk_id" in chunk["metadata"]
        assert "chunk_id" not in chunk  # must NOT be top-level


def test_all_required_metadata_fields_present():
    chunks = chunk_document(_SAMPLE_DOC)
    assert len(chunks) > 0
    for chunk in chunks:
        missing = _REQUIRED_METADATA - set(chunk["metadata"].keys())
        assert not missing, f"Missing metadata fields: {missing}"


def test_table_content_type():
    chunks = chunk_document(_SAMPLE_DOC)
    table_chunks = [c for c in chunks if c["metadata"]["content_type"] == "table"]
    assert len(table_chunks) >= 1


def test_summary_content_type_page1():
    chunks = chunk_document(_SAMPLE_DOC)
    page1_chunks = [c for c in chunks if c["metadata"]["page_number"] == 1]
    assert all(c["metadata"]["content_type"] == "summary" for c in page1_chunks), (
        "Page 1 with section='unknown' should be tagged as summary"
    )


def test_page_label_propagated():
    chunks = chunk_document(_SAMPLE_DOC)
    page2_chunks = [c for c in chunks if c["metadata"]["page_number"] == 2]
    assert all(c["metadata"]["page_label"] == "L-1" for c in page2_chunks)


def test_char_count_matches_text_length():
    chunks = chunk_document(_SAMPLE_DOC)
    for chunk in chunks:
        assert chunk["metadata"]["char_count"] == len(chunk["text"])


# --- Unit tests for _detect_content_type ---

def test_detect_table():
    assert _detect_content_type("anything", "Revenue Account", 2, is_table=True) == "table"

def test_detect_summary_by_section():
    assert _detect_content_type("text", "Executive Summary", 2, is_table=False) == "summary"

def test_detect_summary_page1_unknown():
    assert _detect_content_type("some text block", "unknown", 1, is_table=False) == "summary"

def test_detect_summary_by_prefix():
    assert _detect_content_type("Key Highlights of the quarter...", "General", 3, is_table=False) == "summary"

def test_detect_header():
    assert _detect_content_type("Revenue Account", "unknown", 2, is_table=False) == "header"

def test_detect_text():
    long_text = "The gross written premium for Q1 FY2024-25 was Rs. 8432 crore, growing 7%."
    assert _detect_content_type(long_text, "Revenue Account", 2, is_table=False) == "text"


# --- Unit tests for _estimate_tokens ---

def test_estimate_tokens_empty_string():
    """Test token estimation for empty string."""
    assert _estimate_tokens("") == 0


def test_estimate_tokens_known_length():
    """Test token estimation with text of known length."""
    # 100 characters should estimate to 25 tokens (100 / 4)
    text = "a" * 100
    assert _estimate_tokens(text) == 25


def test_estimate_tokens_sample_text():
    """Test token estimation with realistic sample text."""
    # Sample text: 200 characters should estimate to 50 tokens
    text = "The gross written premium for Q1 FY2024-25 was Rs. 8432 crore, representing a 7% growth over the same period last year. This demonstrates strong performance in the insurance sector."
    expected_tokens = len(text) // 4
    assert _estimate_tokens(text) == expected_tokens


def test_estimate_tokens_large_page():
    """Test token estimation for a large page (32000 chars = 8000 tokens)."""
    # 32000 characters should estimate to 8000 tokens (at the MAX_PAGE_TOKENS limit)
    text = "x" * 32000
    assert _estimate_tokens(text) == 8000


def test_estimate_tokens_exceeds_limit():
    """Test token estimation for text exceeding token limit."""
    # 40000 characters should estimate to 10000 tokens (exceeds 8000 limit)
    text = "y" * 40000
    assert _estimate_tokens(text) == 10000


# --- Unit tests for _combine_page_content ---

def test_combine_page_content_tables_only():
    """Test combining page with only tables."""
    page = {
        "page_number": 1,
        "page_label": "L-1",
        "section": "Revenue Account",
        "tables": [
            {
                "headers": ["Particulars", "Amount"],
                "rows": [["Premium Income", "1000"]],
                "raw_text": "Particulars | Amount\nPremium Income | 1000"
            },
            {
                "headers": ["Item", "Value"],
                "rows": [["Claims", "500"]],
                "raw_text": "Item | Value\nClaims | 500"
            }
        ],
        "text_blocks": []
    }
    
    result = _combine_page_content(page)
    
    # Should contain both tables separated by \n\n
    assert "Particulars | Amount\nPremium Income | 1000" in result
    assert "Item | Value\nClaims | 500" in result
    assert "\n\n" in result
    # Should not have trailing/leading whitespace issues
    assert result.strip() == result


def test_combine_page_content_text_only():
    """Test combining page with only text blocks."""
    page = {
        "page_number": 2,
        "page_label": "L-2",
        "section": "Claims",
        "tables": [],
        "text_blocks": [
            "This is the first text block.",
            "This is the second text block.",
            "This is the third text block."
        ]
    }
    
    result = _combine_page_content(page)
    
    # Should contain all text blocks separated by \n\n
    assert "This is the first text block." in result
    assert "This is the second text block." in result
    assert "This is the third text block." in result
    # Count separators (should be 2 for 3 blocks)
    assert result.count("\n\n") == 2


def test_combine_page_content_mixed():
    """Test combining page with both tables and text blocks."""
    page = {
        "page_number": 3,
        "page_label": "L-3",
        "section": "Balance Sheet",
        "tables": [
            {
                "headers": ["Assets", "Amount"],
                "rows": [["Cash", "10000"]],
                "raw_text": "Assets | Amount\nCash | 10000"
            }
        ],
        "text_blocks": [
            "The balance sheet shows strong financial position.",
            "Total assets increased by 15% year over year."
        ]
    }
    
    result = _combine_page_content(page)
    
    # Tables should come first
    assert result.index("Assets | Amount") < result.index("The balance sheet")
    # Should have proper separators
    assert "\n\n" in result
    # All content should be present
    assert "Assets | Amount\nCash | 10000" in result
    assert "The balance sheet shows strong financial position." in result
    assert "Total assets increased by 15% year over year." in result


def test_combine_page_content_empty_arrays():
    """Test combining page with empty tables and text_blocks arrays."""
    page = {
        "page_number": 4,
        "page_label": "L-4",
        "section": "Empty Page",
        "tables": [],
        "text_blocks": []
    }
    
    result = _combine_page_content(page)
    
    # Should return empty string
    assert result == ""


def test_combine_page_content_missing_arrays():
    """Test combining page with missing tables or text_blocks keys."""
    # Missing both keys
    page1 = {
        "page_number": 5,
        "page_label": "L-5",
        "section": "Test"
    }
    
    result1 = _combine_page_content(page1)
    assert result1 == ""
    
    # Missing tables key
    page2 = {
        "page_number": 6,
        "page_label": "L-6",
        "section": "Test",
        "text_blocks": ["Some text"]
    }
    
    result2 = _combine_page_content(page2)
    assert result2 == "Some text"
    
    # Missing text_blocks key
    page3 = {
        "page_number": 7,
        "page_label": "L-7",
        "section": "Test",
        "tables": [
            {
                "headers": ["Col1"],
                "rows": [["Val1"]],
                "raw_text": "Col1\nVal1"
            }
        ]
    }
    
    result3 = _combine_page_content(page3)
    assert result3 == "Col1\nVal1"


def test_combine_page_content_whitespace_handling():
    """Test that whitespace-only text blocks are filtered out."""
    page = {
        "page_number": 8,
        "page_label": "L-8",
        "section": "Test",
        "tables": [],
        "text_blocks": [
            "Valid text block",
            "   ",  # Whitespace only
            "",     # Empty string
            "Another valid block"
        ]
    }
    
    result = _combine_page_content(page)
    
    # Should only contain valid text blocks
    assert "Valid text block" in result
    assert "Another valid block" in result
    # Should have exactly one separator between the two valid blocks
    assert result == "Valid text block\n\nAnother valid block"


def test_combine_page_content_table_without_raw_text():
    """Test handling of table without raw_text field."""
    page = {
        "page_number": 9,
        "page_label": "L-9",
        "section": "Test",
        "tables": [
            {
                "headers": ["Col1"],
                "rows": [["Val1"]]
                # Missing raw_text field
            },
            {
                "headers": ["Col2"],
                "rows": [["Val2"]],
                "raw_text": "Col2\nVal2"
            }
        ],
        "text_blocks": ["Some text"]
    }
    
    result = _combine_page_content(page)
    
    # Should skip table without raw_text and include the valid table and text
    assert "Col2\nVal2" in result
    assert "Some text" in result
    # Should not fail or include empty content from invalid table
    assert result == "Col2\nVal2\n\nSome text"
