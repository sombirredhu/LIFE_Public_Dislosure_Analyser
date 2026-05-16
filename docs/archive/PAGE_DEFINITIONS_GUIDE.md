# L-Page Definitions & Master Mapping Guide

## Overview

The system automatically extracts and consolidates L-page definitions (index pages) from all uploaded PDFs. This creates a master mapping that allows you to search for content using any term that any company uses.

## How It Works

### 1. **Automatic Extraction**
When you upload a PDF:
- The system scans the first 5 pages for the IRDAI L-page index
- Extracts mappings like: `L-4 → "Gross Written Premium"` or `L-4 → "Premium Schedule"`
- Saves company-specific definitions to: `data/processed/{COMPANY}_page_definitions.json`

### 2. **Master Consolidation**
After extracting definitions:
- All company-specific mappings are merged into a master file
- Creates two master files:
  - `master_page_definitions.json` - Maps L-pages to all terms used by companies
  - `master_term_to_page.json` - Reverse lookup: term → L-page

### 3. **Smart Search**
When you ask about "GWP" or "Premium Schedule":
- The system looks up which L-page that term refers to
- Searches across all companies for that L-page content
- Works even if different companies use different names for the same L-page

## File Structure

```
data/processed/
├── Aditya_Birla_page_definitions.json          # Company-specific
├── HDFC_Life_page_definitions.json             # Company-specific
├── IciciPrruLife_page_definitions.json         # Company-specific
├── master_page_definitions.json                # Master: L-page → [terms]
└── master_term_to_page.json                    # Master: term → L-page
```

## Example Master Files

### master_page_definitions.json
```json
{
  "L-4": [
    "Gross Written Premium",
    "Premium Schedule",
    "GWP"
  ],
  "L-5": [
    "Analytical Ratios",
    "Key Ratios"
  ]
}
```

### master_term_to_page.json
```json
{
  "gross written premium": "L-4",
  "premium schedule": "L-4",
  "gwp": "L-4",
  "analytical ratios": "L-5",
  "key ratios": "L-5"
}
```

## Usage

### Automatic (Recommended)
Master definitions are automatically updated when you:
- Upload a new PDF through the Streamlit app
- Run the ingestion script: `python scripts/ingest_all.py`

### Manual Rebuild
If you need to manually rebuild the master definitions:
```bash
python scripts/rebuild_master_definitions.py
```

### Programmatic Lookup
```python
from src.pdf_parser import get_lpage_from_term, get_all_terms_for_lpage

# Find L-page from a term
lpage = get_lpage_from_term("GWP")  # Returns "L-4"

# Find all terms for an L-page
terms = get_all_terms_for_lpage("L-4")  # Returns ["GWP", "Premium Schedule", ...]
```

### Test Lookups
```bash
python scripts/test_page_lookup.py
```

## Benefits

1. **Unified Search**: Ask about "GWP" and get results even if some companies call it "Premium Schedule"
2. **Automatic Updates**: Master mapping updates every time you upload a new PDF
3. **Company Flexibility**: Each company can use their own terminology
4. **No Manual Mapping**: System learns from the PDFs themselves

## Important Notes

- **Case-Insensitive**: Searches are case-insensitive ("gwp" = "GWP" = "Gwp")
- **Exact Match**: Terms must match exactly (partial matches don't work)
- **First Occurrence**: If a term maps to multiple L-pages, the first occurrence is used
- **Index Required**: Only works for PDFs that have an index page in the first 5 pages

## Current Status

Run this command to see current mappings:
```bash
python scripts/rebuild_master_definitions.py
```

This will show:
- Number of L-pages mapped
- All terms for each L-page
- Total searchable terms

## Future Enhancements

Potential improvements:
- Fuzzy matching for partial terms
- Manual synonym additions
- Multi-language support
- Confidence scoring for ambiguous terms
