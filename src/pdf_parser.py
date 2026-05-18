import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import pdfplumber
from src.config import PROCESSED_OUTPUT_DIR

logger = logging.getLogger(__name__)

# Match L-page patterns:
# Valid: L-4, L-14, L-14A, L-1-A-RA, L-2-A-PL, L-3-A-BS
# Also handles: L-4-PREMIUM -> extracts L-4, description="PREMIUM Schedule"
# Pattern: L-{number}[optional single letter][optional -X-XX suffix]
_LPAGE_LABEL_RE = re.compile(r'^\s*(?:\d+\s+)?(L-?\d+[A-Z]?(?:-[A-Z]+(?:-[A-Z]+)?)?)\s*(?:[:\-]\s*)?(.*)$', re.IGNORECASE)
_PAGE_LPAGE_RE = re.compile(r'(?:FORM|Form)?\s*(L-\s*\d+[A-Z]?(?:-[A-Z]+(?:-[A-Z]+)?)?)', re.IGNORECASE)
_COMPANY_NAME_RE = re.compile(r'\b([A-Z][A-Za-z\s&]{10,}(?:Limited|Ltd\.?|Insurance Company Limited|Insurance Company|Company Limited))', re.MULTILINE)
_LPAGE_TOKEN_RE = re.compile(r'\bL-?\d+[A-Z]?(?:-[A-Z]+(?:-[A-Z]+)?)?\b', re.IGNORECASE)
_INDEX_HINT_WORDS = ("list of", "index", "contents", "form no", "sl. no", "description", "particulars", "page no")
_INDEX_DATA_WORDS = ("amounts in lacs", "schedule ref")

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
    def _is_clean_term(t: str) -> bool:
        if "\n" in t or len(t) > 60 or len(t.strip()) < 3:
            return False
        import re as _re
        return len(_re.findall(r"[a-zA-Z]{2,}", t)) >= 2

    raw_t_to_p = {t.lower(): lp for lp, ts in master_map.items() for t in ts}
    t_to_p = {k: v for k, v in raw_t_to_p.items() if _is_clean_term(k)}
    # Merge user-curated abbreviations so they survive every rebuild.
    user_path = pdir / "user_term_to_page.json"
    if user_path.exists():
        try:
            with open(user_path, "r", encoding="utf-8") as f:
                user_data = json.load(f)
            t_to_p.update({k: v for k, v in user_data.items() if not k.startswith("_")})
        except Exception:
            pass
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

def _canonicalize_lpage(raw: str) -> Optional[str]:
    if not raw:
        return None
    token = re.sub(r"\s+", "", raw.strip().upper())
    token = re.sub(r"^L(?=\d)", "L-", token)
    if not re.match(r"^L-\d+[A-Z]?(?:-[A-Z]+(?:-[A-Z]+)?)?$", token):
        return None
    return token

def _clean_index_section(text: str) -> str:
    sec = re.sub(r"^[\s:\-\.]+", "", text or "").strip()
    sec = re.sub(r"^(?:and|&)\s+", "", sec, flags=re.IGNORECASE)
    sec = re.sub(r"\s+\d+\s*$", "", sec)  # trailing page number
    if re.fullmatch(r"\d+", sec):
        return ""
    sec = re.sub(r"\s{2,}", " ", sec).strip()
    if sec in {"&", "AND", "/"}:
        return ""
    return sec

def _section_from_token_suffix(token: str) -> str:
    if not token:
        return ""
    base = _normalize_lpage(token)
    if not base or len(token) <= len(base):
        return ""
    suffix = token[len(base):].lstrip("-")
    if not suffix:
        return ""
    # Ignore structural suffixes like A-RA / A-PL / A-BS.
    if re.fullmatch(r"[A-Z]-[A-Z]{2}", suffix):
        return ""
    words = suffix.replace("-", " ").title().strip()
    if not words:
        return ""
    if words.lower() == "premium":
        return "Premium Schedule"
    return words

def _extract_lpage_pairs_from_line(line: str) -> List[Tuple[str, str]]:
    if not line:
        return []
    matches = list(_LPAGE_TOKEN_RE.finditer(line))
    if not matches:
        return []
    pairs: List[Tuple[str, str]] = []
    for i, m in enumerate(matches):
        tok = _canonicalize_lpage(m.group(0))
        if not tok:
            continue
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(line)
        sec = _clean_index_section(line[start:end])
        suffix_sec = _section_from_token_suffix(tok)

        # If token carries inline suffix (e.g., L-4-PREMIUM), use it as fallback description.
        if not sec and suffix_sec:
            sec = suffix_sec
        elif suffix_sec and re.match(r"^(?:and|&)\b", line[start:end].strip(), re.IGNORECASE):
            # Cases like: "L-10 & L11-Reserves and Surplus & Borrowings"
            sec = f"{suffix_sec} {sec}".strip()
        pairs.append((tok, sec))

    # If a combined row maps multiple L-pages with one shared description,
    # copy the first non-empty description to empty peers.
    non_empty = next((sec for _, sec in pairs if sec), "")
    if non_empty and len(pairs) > 1:
        pairs = [(lp, sec or non_empty) for lp, sec in pairs]
    return pairs

def _is_index_like_page(text: str, tables: List[List[List[Any]]]) -> bool:
    if not text and not tables:
        return False
    txt = (text or "").lower()[:1500]
    has_hint = any(k in txt for k in _INDEX_HINT_WORDS)
    has_data = any(k in txt for k in _INDEX_DATA_WORDS)

    lpages = set()
    for m in _LPAGE_TOKEN_RE.findall(text or ""):
        lp = _canonicalize_lpage(m)
        if lp:
            lpages.add(_normalize_lpage(lp))
    lpage_count = len(lpages)

    table_hint = False
    for t in tables[:3]:
        for row in t[:3]:
            row_text = " ".join(str(c).strip().lower() for c in row if c)
            if "particular" in row_text and ("form" in row_text or "page" in row_text):
                table_hint = True
                break
        if table_hint:
            break

    if lpage_count >= 8:
        return True
    if has_hint and lpage_count >= 4 and not has_data:
        return True
    if table_hint and lpage_count >= 3:
        return True
    return False

def _extract_index_map_from_pdf(pdf) -> Dict[str, str]:
    index_map: Dict[str, str] = {}
    page_limit = min(len(pdf.pages), 8)
    for i, page in enumerate(pdf.pages[:page_limit], 1):
        txt = page.extract_text() or ""
        tables = page.extract_tables() or []
        is_index = _is_index_like_page(txt, tables)
        logger.debug("[INDEX] Page %s index-like=%s", i, is_index)
        if not is_index:
            continue

        # Parse text lines
        for line in txt.splitlines():
            for lp, sec in _extract_lpage_pairs_from_line(line):
                lp_norm = _normalize_lpage(lp)
                if sec and len(sec) >= 3:
                    prev = index_map.get(lp_norm, "")
                    if not prev or len(sec) > len(prev):
                        index_map[lp_norm] = sec

        # Parse table rows
        for t in tables[:5]:
            for row in t:
                row_text = " ".join(str(c).strip() for c in row if c).strip()
                if not row_text:
                    continue
                for lp, sec in _extract_lpage_pairs_from_line(row_text):
                    lp_norm = _normalize_lpage(lp)
                    if sec and len(sec) >= 3:
                        prev = index_map.get(lp_norm, "")
                        if not prev or len(sec) > len(prev):
                            index_map[lp_norm] = sec
    return index_map

def extract_index_page(pdf_path: str) -> Dict[str, str]:
    if not Path(pdf_path).exists():
        raise FileNotFoundError(pdf_path)
    with pdfplumber.open(pdf_path) as pdf:
        return _extract_index_map_from_pdf(pdf)

def _detect_page_label(first_line: str) -> Optional[str]:
    if not first_line: return None
    m = _LPAGE_LABEL_RE.match(first_line.strip())
    if not m:
        return None
    token = _canonicalize_lpage(m.group(1))
    return token.upper() if token else None

def _extract_company_name_from_text(text: str) -> Optional[str]:
    if not text: return None
    ms = _COMPANY_NAME_RE.findall(text[:500])
    return ' '.join(max(ms, key=len).split()) if ms else None

def _extract_lpage_from_text(text: str) -> Optional[str]:
    if not text: return None
    m = _PAGE_LPAGE_RE.search(text[:200])
    if not m: return None
    # Normalize internal spaces: "L- 12" -> "L-12"
    return re.sub(r'\s+', '', m.group(1).upper())

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
        L-1-A-RA -> L-1
        L-14A -> L-14A (keep as is)
    """
    if not lpage:
        return ""

    token = re.sub(r"\s+", "", lpage.strip().upper())
    token = re.sub(r"^L(?=\d)", "L-", token)

    # Keep optional direct alpha suffix (e.g., L-14A), drop any hyphen suffixes.
    base = re.match(r"^(L-\d+[A-Z]?)", token)
    if base:
        return base.group(1)
    return token

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
    
    raw_tables = page.extract_tables() or []
    is_index = _is_index_like_page(txt, raw_tables)

    pdata = {
        "page_number": page_num,
        "page_label": lbl,
        "page_label_normalized": normalized_lbl,
        "company_name": _extract_company_name_from_text(txt),
        "section": "unknown",
        "is_index_page": is_index,
        "text_blocks": [],
        "tables": []
    }

    if txt.count("|") > 5 or txt.count("\t") > 3:
        for t in raw_tables:
            td = extract_table_text(t)
            if td: pdata["tables"].append(td)
    if txt: pdata["text_blocks"] = [p.strip() for p in txt.split("\n\n") if p.strip()]
    return pdata

def parse_pdf(pdf_path: str) -> Dict[str, Any]:
    if not Path(pdf_path).exists(): raise FileNotFoundError(pdf_path)
    meta = extract_metadata_from_filename(pdf_path)
    p_data = []
    with pdfplumber.open(pdf_path) as pdf:
        tp = len(pdf.pages)
        imap = _extract_index_map_from_pdf(pdf)
        for i, p in enumerate(pdf.pages, 1):
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
