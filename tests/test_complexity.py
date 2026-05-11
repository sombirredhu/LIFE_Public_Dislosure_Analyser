"""
Tests for classify_complexity() — simple vs complex routing.
"""

import pytest
from src.rag_pipeline import classify_complexity


# ── ALWAYS COMPLEX ──────────────────────────────────────────────────────────

def test_compare_keyword():
    assert classify_complexity("Compare HDFC Life and SBI Life premium") == "complex"

def test_vs_keyword():
    assert classify_complexity("HDFC vs SBI Life premium in Q1") == "complex"

def test_versus_keyword():
    assert classify_complexity("HDFC Life versus LIC in FY25") == "complex"

def test_ranking_keyword():
    assert classify_complexity("What is the ranking of all companies by GWP?") == "complex"

def test_which_company_keyword():
    assert classify_complexity("Which company had the highest claims ratio?") == "complex"

def test_all_companies_keyword():
    assert classify_complexity("Show me all companies premium data") == "complex"

def test_industry_total_keyword():
    assert classify_complexity("What is the industry total GWP for Q1 FY25?") == "complex"

def test_channel_wise_keyword():
    assert classify_complexity("Give me channel-wise breakdown for all insurers") == "complex"


# ── COMPLEX (no single company named) ───────────────────────────────────────

def test_highest_no_company():
    assert classify_complexity("Which insurer had the highest persistency ratio?") == "complex"

def test_lowest_no_company():
    assert classify_complexity("Who had the lowest expense ratio?") == "complex"

def test_trend_no_company():
    assert classify_complexity("Show me the trend in claim settlement ratios") == "complex"

def test_top_no_company():
    assert classify_complexity("Top 5 insurers by new business premium") == "complex"


# ── SIMPLE (single company named, no always-complex keywords) ────────────────

def test_single_company_simple():
    assert classify_complexity("What is HDFC Life's gross written premium in Q1 FY25?") == "simple"

def test_single_company_simple_2():
    assert classify_complexity("How many policies did LIC issue in FY25?") == "simple"

def test_single_company_with_highest_is_simple():
    # "highest" + single company → still simple (asking about one company's highest)
    assert classify_complexity("What was HDFC Life's highest quarterly premium?") == "simple"
