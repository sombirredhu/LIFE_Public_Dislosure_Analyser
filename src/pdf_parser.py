import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
import pdfplumber
from src.config import PROCESSED_OUTPUT_DIR

logger = logging.getLogger(__name__)

# Match L-page patterns:
# Valid: L-4, L-14, L-14A, L-1-A-RA, L-2-A-PL, L-3-A-BS
# Also handles: L-4-PREMIUM -> extracts L-4, description="PREMIUM Schedule"
# Pattern: L-{number}[optional single letter][optional -X-XX suffix]
_LPAGE_LABEL_RE = re.compile(r'\b(L-\d+[A-Z]?(?:-[A-Z]-[A-Z]{2})?)\s*(?:-\s*)?(.*)', re.IGNORECASE)
_PAGE_LPAGE_RE = re.compile(r'(?:FORM|Form)?\s*(L-\d+[A-Z]?(?:-[A-Z]+(?:-[A-Z]+)?)?)', re.IGNORECASE)
_COMPANY_NAME_RE = re.compile(r'\b([A-Z][A-Za-z\s&]{10,}(?:Limited|Ltd\.?|Insurance Company Limited|Insurance Company|Company Limited))', re.MULTILINE)

def extract_metadata_from_filename(pdf_path: str) -> Dict[str, str]:
    filename = Path(pdf_path).stem
    match = re.match(r'^(.+)_(Q[1-4])_(FY\d{2})$', filename)
    if not match: raise ValueError(f"Invalid filename: {filename}")
    cc, q, fy = match.groups()
    fy_full = f"20{fy[2:4]}"
    return {"company_code": cc, "company": cc.replace("_", " "), "quarter": q, "fy": fy, "period_label": f"{q} FY{int(fy_full)-1}-{fy[2:4]}", "source_file": Path(pdf_path).name}

def _update_master_page_definitions():
    pdir = Path(PROCESSED_OUTPUT_DIR)
    cfiles = list(pdir.glob("*_page_definitions.json"))
    if not cfiles: return
    master_map: Dict[str, set] = {}
    for fp in cfiles:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                for lp, term in json.load(f).items():
                    if lp not in master_map: master_map[lp] = set()
                    master_map[lp].add(term)
        except Exception: continue
    with open(pdir / "master_page_definitions.json", "w", encoding="utf-8") as f:
        json.dump({lp: sorted(ts) for lp, ts in master_map.items()}, f, indent=2, ensure_ascii=False)
    t_to_p = {t.lower(): lp for lp, ts in master_map.items() for t in ts}
    with open(pdir / "master_term_to_page.json", "w", encoding="utf-8") as f:
        json.dump(t_to_p, f, indent=2, ensure_ascii=False)

def _load_page_definitions(company_code: str) -> Dict[str, str]:
    """Load page definitions with fallback to master and default definitions."""
    pd = Path(PROCESSED_OUTPUT_DIR)
    
    # Try company-specific definitions first
    for fn in [f"{company_code}_page_definitions.json", "page_definitions.json"]:
        fp = pd / fn
        if fp.exists():
            with open(fp, "r", encoding="utf-8") as f: 
                return json.load(f)
    
    # Fallback to master definitions
    master_fp = pd / "master_page_definitions.json"
    if master_fp.exists():
        try:
            with open(master_fp, "r", encoding="utf-8") as f:
                master_defs = json.load(f)
                # Convert list format to simple mapping (take first term)
                return {lpage: terms[0] if isinstance(terms, list) else terms 
                       for lpage, terms in master_defs.items()}
        except Exception as e:
            logger.warning(f"Failed to load master definitions: {e}")
    
    # Final fallback to default definitions
    default_fp = pd / "default_page_definitions.json"
    if default_fp.exists():
        try:
            with open(default_fp, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load default definitions: {e}")
    
    return {}

def get_lpage_from_term(term: str) -> Optional[str]:
    fp = Path(PROCESSED_OUTPUT_DIR) / "master_term_to_page.json"
    if not fp.exists(): return None
    try:
        with open(fp, "r", encoding="utf-8") as f: return json.load(f).get(term.lower())
    except Exception: return None

def get_all_terms_for_lpage(lpage: str) -> List[str]:
    fp = Path(PROCESSED_OUTPUT_DIR) / "master_page_definitions.json"
    if not fp.exists(): return []
    try:
        with open(fp, "r", encoding="utf-8") as f: return json.load(f).get(lpage.upper(), [])
    except Exception: return []

def _detect_page_label(first_line: str) -> Optional[str]:
    if not first_line: return None
    m = _LPAGE_LABEL_RE.match(first_line.strip())
    return m.group(1).upper() if m else None

def _extract_company_name_from_text(text: str) -> Optional[str]:
    if not text: return None
    ms = _COMPANY_NAME_RE.findall(text[:500])
    return ' '.join(max(ms, key=len).split()) if ms else None

def _extract_lpage_from_text(text: str) -> Optional[str]:
    if not text: return None
    m = _PAGE_LPAGE_RE.search(text[:200])
    return m.group(1).upper() if m else None

def extract_table_text(table: List[List[Any]]) -> Optional[Dict[str, Any]]:
    if not table or len(table) < 2: return None
    hdrs = [str(c).strip() if c else "" for c in table[0]]
    rows = [[str(c).strip() if c else "" for c in r] for r in table[1:] if any(r)]
    raw = "\n".join([" | ".join(hdrs)] + [" | ".join(r) for r in rows])
    return {"headers": hdrs, "rows": rows, "raw_text": raw}

def _normalize_lpage(lpage: str) -> str:
    """
    Normalize L-page label by extracting the base L-page number.
    Examples:
        L-4-PREMIUM -> L-4
        L-5-COMMISSION -> L-5
        L-1-A-RA -> L-1-A-RA (keep as is, it's a standard format)
        L-14A -> L-14A (keep as is)
    """
    if not lpage:
        return ""
    
    # Match patterns like L-4-PREMIUM, L-5-COMMISSION
    # But preserve L-1-A-RA, L-2-A-PL, L-3-A-BS, L-14A
    match = re.match(r'(L-\d+[A-Z]?(?:-[A-Z]-[A-Z]{2})?)', lpage.upper())
    if match:
        return match.group(1)
    
    return lpage.upper()

def _match_section(page_label: str, page_defs: Dict[str, str], index_map: Dict[str, str]) -> str:
    """
    Match page label to section with fuzzy matching.
    Tries exact match first, then normalized prefix match, then base L-page number.
    """
    if not page_label:
        return "unknown"
    
    # Try exact match first
    if page_label in page_defs:
        return page_defs[page_label]
    if page_label in index_map:
        return index_map[page_label]
    
    # Try normalized match (e.g., L-4-PREMIUM -> L-4)
    normalized = _normalize_lpage(page_label)
    if normalized != page_label:
        if normalized in page_defs:
            return page_defs[normalized]
        if normalized in index_map:
            return index_map[normalized]
    
    # For L-X-A-YZ format (like L-1-A-RA), try base L-X
    # Extract just L-{number} from patterns like L-1-A-RA, L-2-A-PL
    base_match = re.match(r'(L-\d+)', page_label.upper())
    if base_match:
        base_lpage = base_match.group(1)
        if base_lpage != page_label and base_lpage != normalized:
            if base_lpage in page_defs:
                return page_defs[base_lpage]
            if base_lpage in index_map:
                return index_map[base_lpage]
    
    return "unknown"

def _process_page(page_num: int, page, page_defs: Dict[str, str], index_map: Dict[str, str]) -> Dict[str, Any]:
    txt = page.extract_text() or ""
    lines = txt.splitlines()
    fl = lines[0] if lines else ""
    lbl = _extract_lpage_from_text(txt) or _detect_page_label(fl) or ""
    normalized_lbl = _normalize_lpage(lbl) if lbl else ""
    
    pdata = {
        "page_number": page_num, 
        "page_label": lbl, 
        "page_label_normalized": normalized_lbl,
        "company_name": _extract_company_name_from_text(txt), 
        "section": "unknown", 
        "text_blocks": [], 
        "tables": []
    }
    
    if txt.count("|") > 5 or txt.count("\t") > 3:
        for t in page.extract_tables() or []:
            td = extract_table_text(t)
            if td: pdata["tables"].append(td)
    if txt: pdata["text_blocks"] = [p.strip() for p in txt.split("\n\n") if p.strip()]
    return pdata

def parse_pdf(pdf_path: str) -> Dict[str, Any]:
    if not Path(pdf_path).exists(): raise FileNotFoundError(pdf_path)
    meta = extract_metadata_from_filename(pdf_path)
    p_data, imap = [], {}
    with pdfplumber.open(pdf_path) as pdf:
        tp = len(pdf.pages)
        for i, p in enumerate(pdf.pages, 1):
            if i <= 5:
                txt = p.extract_text() or ""
                
                # Detect index page by looking for keywords and structure
                index_keywords = ['list of', 'index', 'contents', 'form no', 'sl. no', 'description']
                has_index_keyword = any(kw in txt.lower()[:500] for kw in index_keywords)
                
                # Count unique L-pages found
                unique_lpages = set()
                for m in _LPAGE_LABEL_RE.findall(txt):
                    unique_lpages.add(m[0].upper())
                
                # True index page has:
                # 1. Index-related keywords in first 500 chars
                # 2. Multiple L-pages (at least 5)
                # 3. NOT a data page (data pages have "Particulars", "Schedule", "Amount")
                data_keywords = ['particulars', 'schedule ref', 'amounts in lacs']
                has_data_keyword = any(kw in txt.lower()[:500] for kw in data_keywords)
                
                is_index = has_index_keyword and len(unique_lpages) >= 5 and not has_data_keyword
                
                logger.debug(f"Page {i}: index_kw={has_index_keyword}, lpages={len(unique_lpages)}, data_kw={has_data_keyword}, is_index={is_index}")
                
                if is_index:
                    logger.info(f"Detected index page at page {i}")
                    
                    # Extract from text lines
                    lines = txt.splitlines()
                    for li, line in enumerate(lines):
                        line_stripped = line.strip()
                        m = _LPAGE_LABEL_RE.search(line_stripped)
                        if m:
                            lbl, sec = m.group(1).upper(), m.group(2).strip()
                            
                            # If no description on same line, check next line
                            if not sec and li+1 < len(lines):
                                nxt = lines[li+1].strip()
                                if nxt and not _LPAGE_LABEL_RE.search(nxt):
                                    sec = nxt
                            
                            if sec and len(sec) > 3:  # Valid description
                                imap[lbl] = sec
                                logger.debug(f"  Extracted from text: {lbl} -> {sec}")
                    
                    # Extract from tables
                    for t in (p.extract_tables() or [])[:3]:
                        for r in t:
                            for ci, cell in enumerate(r):
                                if not cell: continue
                                cell_str = str(cell).strip()
                                tm = _LPAGE_LABEL_RE.search(cell_str)
                                if tm:
                                    lbl, sec = tm.group(1).upper(), tm.group(2).strip()
                                    
                                    # If no description in same cell, check next cells
                                    if not sec:
                                        for nc in r[ci+1:]:
                                            if nc and str(nc).strip():
                                                sec = str(nc).strip()
                                                break
                                    
                                    if sec and len(sec) > 3:  # Valid description
                                        imap[lbl] = sec
                                        logger.debug(f"  Extracted from table: {lbl} -> {sec}")
                                    break
            
            p_data.append(_process_page(i, p, {}, imap))
    if imap:
        op = Path(PROCESSED_OUTPUT_DIR) / f"{meta['company_code']}_page_definitions.json"
        op.parent.mkdir(parents=True, exist_ok=True)
        with open(op, "w", encoding="utf-8") as f: json.dump(imap, f, indent=2, ensure_ascii=False)
        _update_master_page_definitions()
        try:
            from src.definitions_manager import merge_with_pdf_definitions
            merge_with_pdf_definitions()
        except Exception: pass
    # Load page definitions (with fallback to master)
    p_defs = _load_page_definitions(meta['company_code'])
    
    # Extract company full name from pages (use first non-null occurrence)
    company_full_name = None
    for pd in p_data:
        if pd.get("company_name"):
            company_full_name = pd["company_name"]
            break
    
    # Apply section mapping with fuzzy matching
    for pd in p_data:
        pd["section"] = _match_section(pd["page_label"], p_defs, imap)
    
    res = {
        **meta, 
        "company_full_name": company_full_name,
        "total_pages": tp, 
        "page_definitions_found": bool(p_defs or imap), 
        "pages": p_data
    }
    out = Path(PROCESSED_OUTPUT_DIR) / f"{meta['company_code']}_{meta['quarter']}_{meta['fy']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f: json.dump(res, f, indent=2, ensure_ascii=False)
    return res
