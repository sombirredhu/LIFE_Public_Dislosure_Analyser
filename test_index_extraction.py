"""Test index page extraction fix"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.pdf_parser import parse_pdf
import json

print("="*70)
print("TESTING INDEX PAGE EXTRACTION")
print("="*70)

pdf_path = "data/pdfs/Aditya_Birla_Q3_FY26.pdf"
print(f"\nParsing: {pdf_path}")
print("-"*70)

result = parse_pdf(pdf_path)

print(f"\n✓ Total pages: {result['total_pages']}")
print(f"✓ Page definitions found: {result['page_definitions_found']}")

# Check if definitions file was created
defs_path = Path("data/processed/Aditya_Birla_page_definitions.json")
if defs_path.exists():
    with open(defs_path, 'r', encoding='utf-8') as f:
        defs = json.load(f)
    
    print(f"\n✓ Definitions file created: {defs_path}")
    print(f"✓ Total L-pages extracted: {len(defs)}")
    
    print("\nExtracted L-pages:")
    print("-"*70)
    for lpage, description in sorted(defs.items()):
        print(f"  {lpage:15s} -> {description}")
    
    # Check for key L-pages
    key_lpages = ['L-1-A-RA', 'L-2-A-PL', 'L-3-A-BS', 'L-4', 'L-5']
    missing = [lp for lp in key_lpages if lp not in defs]
    
    if missing:
        print(f"\n⚠️  WARNING: Missing key L-pages: {', '.join(missing)}")
    else:
        print(f"\n✅ SUCCESS: All key L-pages extracted!")
else:
    print(f"\n❌ ERROR: Definitions file not created at {defs_path}")

print("\n" + "="*70)
