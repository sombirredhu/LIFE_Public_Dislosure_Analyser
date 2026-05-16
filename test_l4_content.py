"""Check L-4 page content for all companies"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.retriever import retrieve
from src.embedder import get_indexed_companies

print("="*70)
print("CHECKING L-4 PAGE CONTENT FOR ALL COMPANIES")
print("="*70)

companies = get_indexed_companies()
print(f"\nTotal companies: {len(companies)}")
print(f"Companies: {companies}\n")

# Retrieve L-4 pages for each company
for company_code in companies:
    print(f"\n{'='*70}")
    print(f"COMPANY: {company_code}")
    print(f"{'='*70}")
    
    # Try to get L-4 page
    chunks = retrieve("L-4 premium schedule", filters={"company_code": company_code}, top_k=3)
    
    if not chunks:
        print("❌ No L-4 page found!")
        continue
    
    for i, chunk in enumerate(chunks, 1):
        meta = chunk['metadata']
        print(f"\nChunk {i}:")
        print(f"  Page: {meta['page_number']}")
        print(f"  Label: {meta.get('page_label', 'NO LABEL')}")
        print(f"  Section: {meta.get('section', 'NO SECTION')}")
        print(f"  Score: {chunk['score']:.3f}")
        print(f"  Content preview (first 500 chars):")
        print(f"  {chunk['text'][:500]}")
        
        # Check if content has premium numbers
        text = chunk['text'].lower()
        has_numbers = any(word in text for word in ['crore', 'cr', 'lacs', 'lakhs', 'premium'])
        has_table = '|' in chunk['text'] or 'premium' in text
        print(f"\n  Has premium keywords: {has_numbers}")
        print(f"  Has table structure: {has_table}")

print("\n" + "="*70)
