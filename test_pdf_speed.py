"""
Test PDF parsing speed to verify optimizations.
"""

import time
from pathlib import Path
from src.config import PDF_INPUT_DIR

# Find a test PDF
pdf_files = list(Path(PDF_INPUT_DIR).glob("*.pdf"))

if not pdf_files:
    print("No PDF files found in", PDF_INPUT_DIR)
    print("Please add a PDF file to test.")
else:
    test_pdf = pdf_files[0]
    print(f"Testing with: {test_pdf.name}")
    print(f"File size: {test_pdf.stat().st_size / 1024:.1f} KB")
    print()
    
    # Test parsing speed
    print("Starting PDF parsing test...")
    start = time.time()
    
    from src.pdf_parser import parse_pdf
    result = parse_pdf(str(test_pdf))
    
    elapsed = time.time() - start
    
    print(f"\n✓ Parsing completed in {elapsed:.2f} seconds")
    print(f"  Pages: {result['total_pages']}")
    print(f"  Company: {result['company']}")
    print(f"  Tables found: {sum(len(p['tables']) for p in result['pages'])}")
    print(f"  Text blocks: {sum(len(p['text_blocks']) for p in result['pages'])}")
    print(f"\n  Speed: {result['total_pages'] / elapsed:.1f} pages/second")
    
    if elapsed < 10:
        print("\n✓ FAST - Parsing is working well!")
    elif elapsed < 30:
        print("\n⚠ MODERATE - Could be faster")
    else:
        print("\n✗ SLOW - Still has performance issues")
