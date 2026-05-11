"""
PDF Parser - extracts text and tables from IRDAI Public Disclosure PDFs.
Uses pdfplumber for accurate table detection and text extraction.
Extracts the IRDAI L-page index to map page labels to section names.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import pdfplumber

from src.config import PROCESSED_OUTPUT_DIR

logger = logging.getLogger(__name__)

# Regex to detect L-page labels like "L-1", "L-12", "L-1 :", "L-5 : Analytical Ratios"
# Updated to handle leading whitespace and serial numbers (e.g., "1 L-1-A-RA Revenue Account")
_LPAGE_LABEL_RE = re.compile(r'\s*(L-\d+(?:-[A-Z]+(?:-[A-Z]+)?)?)\s*[:\-]?\s*(.*)', re.IGNORECASE)

# Regex to detect L-page in page content like "FORM L-4", "Form L-5", "L-6 something"
_PAGE_LPAGE_RE = re.compile(r'(?:FORM|Form)?\s*(L-\d+[A-Z]?(?:-[A-Z]+)?)', re.IGNORECASE)

# Regex to extract company name (looks for patterns ending with Ltd, Limited, Insurance, Company)
# Improved to avoid capturing short prefixes
_COMPANY_NAME_RE = re.compile(r'\b([A-Z][A-Za-z\s&]{10,}(?:Limited|Ltd\.?|Insurance Company Limited|Insurance Company|Company Limited))', re.MULTILINE)


def extract_metadata_from_filename(pdf_path: str) -> Dict[str, str]:
    """
    Extract company, quarter, and FY from filename.
    Expected format: {COMPANY_CODE}_{QUARTER}_{FY}.pdf
    Example: HDFC_Life_Q1_FY25.pdf
    """
    filename = Path(pdf_path).stem

    pattern = r'^(.+)_(Q[1-4])_(FY\d{2})$'
    match = re.match(pattern, filename)

    if not match:
        raise ValueError(
            f"Invalid filename format: {filename}\n"
            f"Expected format: {{COMPANY_CODE}}_{{QUARTER}}_{{FY}}.pdf\n"
            f"Example: HDFC_Life_Q1_FY25.pdf"
        )

    company_code, quarter, fy = match.groups()
    company_display = company_code.replace("_", " ")

    fy_full = f"20{fy[2:4]}"
    fy_start = int(fy_full) - 1
    period_label = f"{quarter} FY{fy_start}-{fy[2:4]}"

    return {
        "company_code": company_code,
        "company": company_display,
        "quarter": quarter,
        "fy": fy,
        "period_label": period_label,
        "source_file": Path(pdf_path).name,
    }


def _update_master_page_definitions():
    """
    Merge all company-specific page definition files into a master mapping.
    Creates two files:
    1. master_page_definitions.json: {L-page: [all terms used by companies]}
    2. master_term_to_page.json: {term: L-page} for reverse lookup
    """
    processed_dir = Path(PROCESSED_OUTPUT_DIR)
    
    # Find all company-specific page definition files
    company_files = list(processed_dir.glob("*_page_definitions.json"))
    
    if not company_files:
        logger.info("No company page definition files found to merge")
        return
    
    # Master mapping: L-page → set of all terms
    master_map: Dict[str, set] = {}
    
    for file_path in company_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                company_defs = json.load(f)
            
            for lpage, term in company_defs.items():
                if lpage not in master_map:
                    master_map[lpage] = set()
                master_map[lpage].add(term)
        except Exception as e:
            logger.warning("Failed to read %s: %s", file_path, e)
    
    # Convert sets to sorted lists for JSON serialization
    master_page_defs = {lpage: sorted(terms) for lpage, terms in master_map.items()}
    
    # Create reverse lookup: term → L-page (lowercase for case-insensitive search)
    term_to_page: Dict[str, str] = {}
    for lpage, terms in master_map.items():
        for term in terms:
            term_lower = term.lower()
            if term_lower not in term_to_page:
                term_to_page[term_lower] = lpage
            # If term already exists and maps to different page, log warning
            elif term_to_page[term_lower] != lpage:
                logger.warning(
                    "Term '%s' maps to multiple L-pages: %s and %s. Using first occurrence.",
                    term, term_to_page[term_lower], lpage
                )
    
    # Save master page definitions
    master_file = processed_dir / "master_page_definitions.json"
    with open(master_file, "w", encoding="utf-8") as f:
        json.dump(master_page_defs, f, indent=2, ensure_ascii=False)
    logger.info("Saved master page definitions with %d L-pages to %s", len(master_page_defs), master_file)
    
    # Save term-to-page lookup
    term_lookup_file = processed_dir / "master_term_to_page.json"
    with open(term_lookup_file, "w", encoding="utf-8") as f:
        json.dump(term_to_page, f, indent=2, ensure_ascii=False)
    logger.info("Saved term-to-page lookup with %d terms to %s", len(term_to_page), term_lookup_file)


def extract_index_page(pdf_path: str) -> Dict[str, str]:
    """
    Scan the first few pages of the PDF for the IRDAI L-page index table.
    Returns a dict mapping L-page labels to section names, e.g.:
        {"L-1": "Revenue Account", "L-2": "Balance Sheet", ...}

    Saves result as data/processed/{company_code}_page_definitions.json.
    Updates master page definitions after saving.
    Falls back to data/processed/page_definitions.json (user master file) if not found.
    """
    metadata = extract_metadata_from_filename(pdf_path)
    company_code = metadata["company_code"]

    index_map: Dict[str, str] = {}

    with pdfplumber.open(pdf_path) as pdf:
        # Scan only first 5 pages — the index is always near the start
        for page in pdf.pages[:5]:
            text = page.extract_text() or ""
            lines = text.splitlines()

            for i, line in enumerate(lines):
                line = line.strip()
                m = _LPAGE_LABEL_RE.search(line)
                if m:
                    label = m.group(1).upper()    # e.g. "L-1"
                    section = m.group(2).strip()
                    
                    # If no description on this line, check next line
                    if not section and i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        # Only use next line if it doesn't look like another L-page entry
                        if next_line and not _LPAGE_LABEL_RE.search(next_line):
                            section = next_line
                    
                    if section and label not in index_map:
                        index_map[label] = section
                        logger.debug("Extracted %s: %s", label, section)

            # Also check tables on this page
            tables = page.extract_tables() or []
            for table in tables:
                for row in table:
                    if not row:
                        continue
                    
                    # Check ALL columns in the row for L-page patterns
                    for col_idx, cell in enumerate(row):
                        if not cell:
                            continue
                        
                        cell_text = str(cell).strip()
                        if not cell_text:
                            continue
                        
                        # Try to match L-page pattern in this cell
                        tm = _LPAGE_LABEL_RE.search(cell_text)
                        if tm:
                            label = tm.group(1).upper()
                            
                            # First, try to get description from the same cell (after L-page)
                            section_from_cell = tm.group(2).strip() if tm.group(2) else ""
                            
                            # If no description in same cell, look in subsequent columns
                            if not section_from_cell:
                                for next_cell in row[col_idx + 1:]:
                                    if next_cell and str(next_cell).strip():
                                        section_from_cell = str(next_cell).strip()
                                        break
                            
                            # Handle cases where description might be split across multiple columns
                            # (e.g., "L-4" in col 0, "Premium" in col 1, "Schedule" in col 2)
                            if section_from_cell and label not in index_map:
                                # Check if we should append text from next column
                                next_col_idx = col_idx + 1
                                if section_from_cell and next_col_idx < len(row):
                                    next_cell = row[next_col_idx]
                                    if next_cell and str(next_cell).strip():
                                        next_text = str(next_cell).strip()
                                        # Only append if it looks like a continuation (not another L-page)
                                        if not _LPAGE_LABEL_RE.search(next_text):
                                            # Check if next cell is short and might be part of description
                                            if len(next_text) < 50 and not next_text.startswith(('L-', 'Form')):
                                                section_from_cell = f"{section_from_cell} {next_text}".strip()
                                
                                index_map[label] = section_from_cell
                                logger.debug("Extracted %s: %s", label, section_from_cell)
                            
                            # Break after finding L-page in this row to avoid duplicates
                            break

    if index_map:
        out_path = Path(PROCESSED_OUTPUT_DIR) / f"{company_code}_page_definitions.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(index_map, f, indent=2, ensure_ascii=False)
        logger.info("Extracted %d L-pages from index", len(index_map))
        logger.info("Saved %d L-page definitions to %s", len(index_map), out_path)
        
        # Update master definitions after saving company-specific file
        _update_master_page_definitions()
        
        # Merge with custom definitions
        try:
            from src.definitions_manager import merge_with_pdf_definitions
            merge_with_pdf_definitions()
        except Exception as e:
            logger.warning("Failed to merge with custom definitions: %s", e)
    else:
        logger.warning("No L-page index found in %s — section labels will use fallback.", pdf_path)

    return index_map


def _load_page_definitions(company_code: str) -> Dict[str, str]:
    """
    Load L-page → section mapping for a company.
    Priority: company-specific file → master fallback → empty dict.
    """
    processed_dir = Path(PROCESSED_OUTPUT_DIR)

    company_file = processed_dir / f"{company_code}_page_definitions.json"
    if company_file.exists():
        with open(company_file, "r", encoding="utf-8") as f:
            return json.load(f)

    master_file = processed_dir / "page_definitions.json"
    if master_file.exists():
        with open(master_file, "r", encoding="utf-8") as f:
            return json.load(f)

    return {}


def get_lpage_from_term(term: str) -> Optional[str]:
    """
    Look up an L-page code from a term (case-insensitive).
    Example: get_lpage_from_term("GWP") → "L-4"
             get_lpage_from_term("premium schedule") → "L-4"
    
    Returns:
        L-page code (e.g., "L-4") or None if not found
    """
    processed_dir = Path(PROCESSED_OUTPUT_DIR)
    term_lookup_file = processed_dir / "master_term_to_page.json"
    
    if not term_lookup_file.exists():
        logger.warning("Master term-to-page lookup file not found. Run _update_master_page_definitions() first.")
        return None
    
    try:
        with open(term_lookup_file, "r", encoding="utf-8") as f:
            term_to_page = json.load(f)
        
        return term_to_page.get(term.lower())
    except Exception as e:
        logger.error("Failed to load term-to-page lookup: %s", e)
        return None


def get_all_terms_for_lpage(lpage: str) -> List[str]:
    """
    Get all terms that map to a specific L-page across all companies.
    Example: get_all_terms_for_lpage("L-4") → ["GWP", "Premium Schedule", "Gross Written Premium"]
    
    Returns:
        List of terms or empty list if L-page not found
    """
    processed_dir = Path(PROCESSED_OUTPUT_DIR)
    master_file = processed_dir / "master_page_definitions.json"
    
    if not master_file.exists():
        logger.warning("Master page definitions file not found. Run _update_master_page_definitions() first.")
        return []
    
    try:
        with open(master_file, "r", encoding="utf-8") as f:
            master_defs = json.load(f)
        
        return master_defs.get(lpage.upper(), [])
    except Exception as e:
        logger.error("Failed to load master page definitions: %s", e)
        return []


def _detect_page_label(first_line: str) -> Optional[str]:
    """Extract the L-page label from the first line of a page, e.g. 'L-5 : Analytical Ratios' → 'L-5'."""
    if not first_line:
        return None
    m = _LPAGE_LABEL_RE.match(first_line.strip())
    return m.group(1).upper() if m else None


def _extract_company_name_from_text(text: str) -> Optional[str]:
    """
    Extract company full name from page text.
    Looks for patterns like "XYZ Bla Bla Ltd", "ABC Insurance Company Limited", etc.
    """
    if not text:
        return None
    
    # Look for company name in first 500 characters (usually at top of page)
    search_text = text[:500]
    matches = _COMPANY_NAME_RE.findall(search_text)
    
    if matches:
        # Return the longest match (most complete company name)
        company_name = max(matches, key=len).strip()
        # Clean up extra spaces
        company_name = ' '.join(company_name.split())
        return company_name
    
    return None


def _extract_lpage_from_text(text: str) -> Optional[str]:
    """
    Extract L-page identifier from page text.
    Handles formats like: "FORM L-4", "Form L-5", "L-6", "L-1-A-RA", etc.
    """
    if not text:
        return None
    
    # Look for L-page in first 200 characters (usually at top of page)
    search_text = text[:200]
    match = _PAGE_LPAGE_RE.search(search_text)
    
    if match:
        return match.group(1).upper()
    
    return None


def extract_table_text(table: List[List[Any]]) -> Optional[Dict[str, Any]]:
    """Convert pdfplumber table to structured format with pipe-separated raw_text."""
    if not table or len(table) < 2:
        return None

    headers = [str(cell).strip() if cell else "" for cell in table[0]]

    rows = []
    for row in table[1:]:
        cleaned_row = [str(cell).strip() if cell else "" for cell in row]
        if any(cleaned_row):
            rows.append(cleaned_row)

    raw_text_lines = [" | ".join(headers)]
    for row in rows:
        raw_text_lines.append(" | ".join(row))
    raw_text = "\n".join(raw_text_lines)

    return {"headers": headers, "rows": rows, "raw_text": raw_text}


def _process_page(page_num: int, page, page_defs: Dict[str, str], index_map: Dict[str, str]) -> Dict[str, Any]:
    """Process a single PDF page (for parallel processing)."""
    raw_text = page.extract_text() or ""
    lines = raw_text.splitlines()
    first_line = lines[0] if lines else ""

    # Extract company name from page content
    company_name = _extract_company_name_from_text(raw_text)
    
    # Extract L-page from page content (not just first line)
    page_label = _extract_lpage_from_text(raw_text) or _detect_page_label(first_line) or ""
    
    # Section will be updated later after index is fully extracted
    if page_num == 1:
        section = "unknown"  # cover page
    else:
        section = "unknown"

    page_data: Dict[str, Any] = {
        "page_number": page_num,
        "page_label":  page_label,
        "company_name": company_name,  # Add extracted company name
        "section":     section,
        "text_blocks": [],
        "tables":      [],
    }

    # OPTIMIZATION 5: Skip table extraction if no tables detected
    # Quick check: if page has table-like structure (multiple "|" characters or tabs)
    has_tables = raw_text.count("|") > 5 or raw_text.count("\t") > 3
    
    if has_tables:
        tables = page.extract_tables() or []
        for table in tables:
            table_data = extract_table_text(table)
            if table_data:
                page_data["tables"].append(table_data)

    # Extract text blocks (split on blank lines)
    if raw_text:
        paragraphs = [p.strip() for p in raw_text.split("\n\n") if p.strip()]
        page_data["text_blocks"] = paragraphs

    return page_data


def parse_pdf(pdf_path: str) -> Dict[str, Any]:
    """
    Parse a PDF file and extract all text and tables.
    Each page dict includes page_label (L-page) and section (from index map).

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Dictionary with parsed content and metadata
    """
    if not Path(pdf_path).exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    metadata = extract_metadata_from_filename(pdf_path)
    company_code = metadata["company_code"]

    pages_data = []
    index_map: Dict[str, str] = {}

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)

        # OPTIMIZATION: Extract index from first 5 pages only (if it exists)
        # Most PDFs have index on page 1 or 2, some don't have it at all
        for page_num, page in enumerate(pdf.pages, start=1):
            # Only check first 5 pages for index
            if page_num <= 5:
                text = page.extract_text() or ""
                lines = text.splitlines()
                
                # Quick check: does this page look like an index?
                has_index_keywords = any(keyword in text.lower() for keyword in ['index', 'schedule', 'contents', 'particulars', 'list of website disclosure', 'form', 'revenue account', 'balance sheet'])
                
                if has_index_keywords:
                    # Extract L-page mappings from text
                    for i, line in enumerate(lines):
                        line = line.strip()
                        m = _LPAGE_LABEL_RE.search(line)
                        if m:
                            label = m.group(1).upper()
                            section = m.group(2).strip()
                            
                            # If no description on this line, check next line
                            if not section and i + 1 < len(lines):
                                next_line = lines[i + 1].strip()
                                # Only use next line if it doesn't look like another L-page entry
                                if next_line and not _LPAGE_LABEL_RE.search(next_line):
                                    section = next_line
                            
                            if section and label not in index_map:
                                index_map[label] = section
                                logger.debug("Extracted %s: %s", label, section)
                    
                    # Also check tables (only if page looks like index)
                    tables = page.extract_tables() or []
                    for table in tables[:3]:  # Check first 3 tables
                        for row in table:
                            if not row:
                                continue
                            
                            # Check ALL columns in the row for L-page patterns
                            for col_idx, cell in enumerate(row):
                                if not cell:
                                    continue
                                
                                cell_text = str(cell).strip()
                                if not cell_text:
                                    continue
                                
                                # Try to match L-page pattern in this cell
                                tm = _LPAGE_LABEL_RE.search(cell_text)
                                if tm:
                                    label = tm.group(1).upper()
                                    
                                    # First, try to get description from the same cell (after L-page)
                                    section_from_cell = tm.group(2).strip() if tm.group(2) else ""
                                    
                                    # If no description in same cell, look in subsequent columns
                                    if not section_from_cell:
                                        for next_cell in row[col_idx + 1:]:
                                            if next_cell and str(next_cell).strip():
                                                section_from_cell = str(next_cell).strip()
                                                break
                                    
                                    # Handle cases where description might be split across multiple columns
                                    if section_from_cell and label not in index_map:
                                        # Check if we should append text from next column
                                        next_col_idx = col_idx + 1
                                        if section_from_cell and next_col_idx < len(row):
                                            next_cell = row[next_col_idx]
                                            if next_cell and str(next_cell).strip():
                                                next_text = str(next_cell).strip()
                                                # Only append if it looks like a continuation (not another L-page)
                                                if not _LPAGE_LABEL_RE.search(next_text):
                                                    # Check if next cell is short and might be part of description
                                                    if len(next_text) < 50 and not next_text.startswith(('L-', 'Form')):
                                                        section_from_cell = f"{section_from_cell} {next_text}".strip()
                                        
                                        index_map[label] = section_from_cell
                                        logger.debug("Extracted %s: %s", label, section_from_cell)
                                    
                                    # Break after finding L-page in this row to avoid duplicates
                                    break
            
            # Process page (all pages)
            page_data = _process_page(page_num, page, {}, index_map)
            pages_data.append(page_data)
    
    # Save index if found
    if index_map:
        out_path = Path(PROCESSED_OUTPUT_DIR) / f"{company_code}_page_definitions.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(index_map, f, indent=2, ensure_ascii=False)
        
        logger.info("Extracted %d L-pages from index", len(index_map))
        
        # Update master definitions
        _update_master_page_definitions()
        
        # Merge with custom definitions
        try:
            from src.definitions_manager import merge_with_pdf_definitions
            merge_with_pdf_definitions()
        except Exception as e:
            logger.warning("Failed to merge with custom definitions: %s", e)
    
    # Load definitions for section mapping
    page_defs = _load_page_definitions(company_code)
    page_definitions_found = bool(page_defs or index_map)
    
    # Update sections in pages_data
    for page_data in pages_data:
        page_label = page_data["page_label"]
        if page_label:
            if page_label in page_defs:
                page_data["section"] = page_defs[page_label]
            elif page_label in index_map:
                page_data["section"] = index_map[page_label]

    result = {
        **metadata,
        "total_pages": total_pages,
        "page_definitions_found": page_definitions_found,
        "pages": pages_data,
    }

    # Save processed JSON
    output_filename = f"{metadata['company_code']}_{metadata['quarter']}_{metadata['fy']}.json"
    output_path = Path(PROCESSED_OUTPUT_DIR) / output_filename
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    return result


if __name__ == "__main__":
    import sys
    from src.config import PDF_INPUT_DIR

    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
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
    print(f"  Page Definitions Found: {result['page_definitions_found']}")
    print(f"  Tables Found: {sum(len(p['tables']) for p in result['pages'])}")
    print(f"  Text Blocks: {sum(len(p['text_blocks']) for p in result['pages'])}")
    sections = set(p['section'] for p in result['pages'] if p['section'] != 'unknown')
    print(f"  Sections Detected: {sorted(sections)}")
    print(f"\n  Saved to: {PROCESSED_OUTPUT_DIR}/{result['company_code']}_{result['quarter']}_{result['fy']}.json")
