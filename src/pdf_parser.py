"""
PDF Parser - extracts text and tables from IRDAI Public Disclosure PDFs.
Uses pdfplumber for accurate table detection and text extraction.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Any
import pdfplumber

from src.config import PROCESSED_OUTPUT_DIR


def extract_metadata_from_filename(pdf_path: str) -> Dict[str, str]:
    """
    Extract company, quarter, and FY from filename.
    Expected format: {COMPANY_CODE}_{QUARTER}_{FY}.pdf
    Example: HDFC_Life_Q1_FY25.pdf
    """
    filename = Path(pdf_path).stem  # Remove .pdf extension
    
    # Pattern: COMPANY_CODE_QUARTER_FY
    # Handle company codes with underscores (e.g., HDFC_Life, Tata_AIA)
    pattern = r'^(.+)_(Q[1-4])_(FY\d{2})$'
    match = re.match(pattern, filename)
    
    if not match:
        raise ValueError(
            f"Invalid filename format: {filename}\n"
            f"Expected format: {{COMPANY_CODE}}_{{QUARTER}}_{{FY}}.pdf\n"
            f"Example: HDFC_Life_Q1_FY25.pdf"
        )
    
    company_code, quarter, fy = match.groups()
    
    # Convert company code to display name
    company_display = company_code.replace("_", " ")
    
    # Create period label (e.g., "Q1 FY2024-25")
    fy_full = f"20{fy[2:4]}"  # FY25 -> 2025
    fy_start = int(fy_full) - 1
    period_label = f"{quarter} FY{fy_start}-{fy[2:4]}"
    
    return {
        "company_code": company_code,
        "company": company_display,
        "quarter": quarter,
        "fy": fy,
        "period_label": period_label,
        "source_file": Path(pdf_path).name
    }


def extract_table_text(table: List[List[Any]]) -> Dict[str, Any]:
    """
    Convert pdfplumber table to structured format.
    Returns headers, rows, and raw text representation.
    """
    if not table or len(table) < 2:
        return None
    
    # First row is usually headers
    headers = [str(cell).strip() if cell else "" for cell in table[0]]
    
    # Remaining rows are data
    rows = []
    for row in table[1:]:
        cleaned_row = [str(cell).strip() if cell else "" for cell in row]
        # Skip empty rows
        if any(cleaned_row):
            rows.append(cleaned_row)
    
    # Create pipe-separated text representation
    raw_text_lines = [" | ".join(headers)]
    for row in rows:
        raw_text_lines.append(" | ".join(row))
    raw_text = "\n".join(raw_text_lines)
    
    return {
        "headers": headers,
        "rows": rows,
        "raw_text": raw_text
    }


def parse_pdf(pdf_path: str) -> Dict[str, Any]:
    """
    Parse a PDF file and extract all text and tables.
    
    Args:
        pdf_path: Path to the PDF file
    
    Returns:
        Dictionary with parsed content and metadata
    """
    if not Path(pdf_path).exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    # Extract metadata from filename
    metadata = extract_metadata_from_filename(pdf_path)
    
    pages_data = []
    
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        
        for page_num, page in enumerate(pdf.pages, start=1):
            page_data = {
                "page_number": page_num,
                "text_blocks": [],
                "tables": []
            }
            
            # Extract tables first
            tables = page.extract_tables()
            if tables:
                for table in tables:
                    table_data = extract_table_text(table)
                    if table_data:
                        page_data["tables"].append(table_data)
            
            # Extract text (excluding table areas to avoid duplication)
            text = page.extract_text()
            if text:
                # Split into paragraphs (separated by blank lines)
                paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
                page_data["text_blocks"] = paragraphs
            
            pages_data.append(page_data)
    
    result = {
        **metadata,
        "total_pages": total_pages,
        "pages": pages_data
    }
    
    # Save to processed directory
    output_filename = f"{metadata['company_code']}_{metadata['quarter']}_{metadata['fy']}.json"
    output_path = Path(PROCESSED_OUTPUT_DIR) / output_filename
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    return result


if __name__ == "__main__":
    # Test with a sample PDF (if exists)
    import sys
    from src.config import PDF_INPUT_DIR
    
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        # Try to find any PDF in the input directory
        pdf_files = list(Path(PDF_INPUT_DIR).glob("*.pdf"))
        if pdf_files:
            pdf_path = str(pdf_files[0])
        else:
            print(f"No PDF files found in {PDF_INPUT_DIR}")
            print("Usage: python src/pdf_parser.py <path_to_pdf>")
            sys.exit(1)
    
    print(f"Parsing: {pdf_path}")
    result = parse_pdf(pdf_path)
    
    print(f"\n✓ Parsed successfully!")
    print(f"  Company: {result['company']}")
    print(f"  Period: {result['period_label']}")
    print(f"  Total Pages: {result['total_pages']}")
    print(f"  Tables Found: {sum(len(p['tables']) for p in result['pages'])}")
    print(f"  Text Blocks: {sum(len(p['text_blocks']) for p in result['pages'])}")
    print(f"\n  Saved to: {PROCESSED_OUTPUT_DIR}/{result['company_code']}_{result['quarter']}_{result['fy']}.json")
