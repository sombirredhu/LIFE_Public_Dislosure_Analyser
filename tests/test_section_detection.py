"""
Tests for L-page label → section name resolution in pdf_parser.
"""

import pytest
from src.pdf_parser import _detect_page_label, _LPAGE_LABEL_RE


# ── _detect_page_label() ─────────────────────────────────────────────────────

def test_plain_label():
    assert _detect_page_label("L-1") == "L-1"

def test_label_with_colon_and_section():
    assert _detect_page_label("L-5 : Analytical Ratios") == "L-5"

def test_label_with_dash_separator():
    assert _detect_page_label("L-12 - Balance Sheet") == "L-12"

def test_label_uppercase_normalised():
    assert _detect_page_label("l-3 : Revenue Account") == "L-3"

def test_no_label_returns_none():
    assert _detect_page_label("This is a regular line of text.") is None

def test_empty_string_returns_none():
    assert _detect_page_label("") is None

def test_label_with_leading_whitespace():
    assert _detect_page_label("  L-7  ") == "L-7"

def test_two_digit_label():
    assert _detect_page_label("L-14 : Expense of Management") == "L-14"


# ── _LPAGE_LABEL_RE regex ────────────────────────────────────────────────────

def test_regex_captures_section_name():
    m = _LPAGE_LABEL_RE.match("L-5 : Revenue Account")
    assert m is not None
    assert m.group(2).strip() == "Revenue Account"

def test_regex_no_section_gives_empty():
    m = _LPAGE_LABEL_RE.match("L-1")
    assert m is not None
    assert m.group(2).strip() == ""

def test_regex_does_not_match_non_lpage():
    assert _LPAGE_LABEL_RE.match("Table of Contents") is None
    assert _LPAGE_LABEL_RE.match("Page 5") is None
