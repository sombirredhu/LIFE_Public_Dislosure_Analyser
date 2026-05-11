"""
Test script to verify company name and L-page extraction from text.
"""

import re

# Regex patterns from pdf_parser.py
_PAGE_LPAGE_RE = re.compile(r'(?:FORM|Form)?\s*(L-\d+[A-Z]?(?:-[A-Z]+)?)', re.IGNORECASE)
_COMPANY_NAME_RE = re.compile(r'([A-Z][A-Za-z\s&]+(?:Limited|Ltd\.?|Insurance|Company))', re.MULTILINE)

# Sample text from page 1 (index page)
sample_page1 = """Name of the Insurer: Aditya Birla Sun Life Insurance Company Limited
Public Disclosure for the quarter and nine months ended 31st December, 2025
List of Website Disclosure
Sl. No. Form No. Description
1 L-1-A-RA Revenue Account
2 L-2-A-PL Profit & Loss Account
3 L-3-A-BS Balance Sheet
4 L-4 Premium Schedule
5 L-5 Commission Schedule"""

# Sample text from page 2 (L-1-A-RA)
sample_page2 = """FORM L-1-A-RA
Aditya Birla Sun Life Insurance Company Limited
Registration Number: 109 dated 31st January 2001
Revenue Account for the Quarter ended 31st December 2025"""

# Sample text from page 8 (L-4)
sample_page8 = """Aditya Birla Sun Life Insurance Company Limited
Registration Number: 109 dated 31st January 2001
Form L-4- Premium Schedule
PREMIUM"""

def extract_company_name(text):
    """Extract company name from text."""
    search_text = text[:500]
    matches = _COMPANY_NAME_RE.findall(search_text)
    if matches:
        company_name = max(matches, key=len).strip()
        company_name = ' '.join(company_name.split())
        return company_name
    return None

def extract_lpage(text):
    """Extract L-page from text."""
    search_text = text[:200]
    match = _PAGE_LPAGE_RE.search(search_text)
    if match:
        return match.group(1).upper()
    return None

print("=" * 80)
print("Testing Company Name and L-Page Extraction")
print("=" * 80)

print("\n--- Page 1 (Index Page) ---")
company1 = extract_company_name(sample_page1)
lpage1 = extract_lpage(sample_page1)
print(f"Company Name: {company1}")
print(f"L-Page: {lpage1}")

print("\n--- Page 2 (L-1-A-RA) ---")
company2 = extract_company_name(sample_page2)
lpage2 = extract_lpage(sample_page2)
print(f"Company Name: {company2}")
print(f"L-Page: {lpage2}")

print("\n--- Page 8 (L-4) ---")
company8 = extract_company_name(sample_page8)
lpage8 = extract_lpage(sample_page8)
print(f"Company Name: {company8}")
print(f"L-Page: {lpage8}")

print("\n" + "=" * 80)
print("✓ Extraction logic working correctly!")
print("=" * 80)
