import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
import pdfplumber
from src.config import PROCESSED_OUTPUT_DIR

logger = logging.getLogger(__name__)

_LPAGE_LABEL_RE = re.compile(r'\s*(L-\d+[A-Z]?(?:-[A-Z]+(?:-[A-Z]+)?)?)\s*[:\-]?\s*(.*)', re.IGNORECASE)
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
    pd = Path(PROCESSED_OUTPUT_DIR)
    for fn in [f"{company_code}_page_definitions.json", "page_definitions.json"]:
        fp = pd / fn
        if fp.exists():
            with open(fp, "r", encoding="utf-8") as f: return json.load(f)
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

def _process_page(page_num: int, page, page_defs: Dict[str, str], index_map: Dict[str, str]) -> Dict[str, Any]:
    txt = page.extract_text() or ""
    lines = txt.splitlines()
    fl = lines[0] if lines else ""
    lbl = _extract_lpage_from_text(txt) or _detect_page_label(fl) or ""
    pdata = {"page_number": page_num, "page_label": lbl, "company_name": _extract_company_name_from_text(txt), "section": "unknown", "text_blocks": [], "tables": []}
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
                # A true index page will list multiple distinct L-pages. 
                # Data pages will only reference their own L-page (e.g., L-4).
                unique_lpages = {m[0].upper() for m in _LPAGE_LABEL_RE.findall(txt)}
                is_index = len(unique_lpages) >= 3
                
                if is_index:
                    for li, line in enumerate(txt.splitlines()):
                        m = _LPAGE_LABEL_RE.search(line.strip())
                        if m:
                            lbl, sec = m.group(1).upper(), m.group(2).strip()
                            if not sec and li+1 < len(txt.splitlines()):
                                nxt = txt.splitlines()[li+1].strip()
                                if nxt and not _LPAGE_LABEL_RE.search(nxt): sec = nxt
                            if sec: imap[lbl] = sec
                    for t in (p.extract_tables() or [])[:3]:
                        for r in t:
                            for ci, cell in enumerate(r):
                                if not cell: continue
                                tm = _LPAGE_LABEL_RE.search(str(cell).strip())
                                if tm:
                                    lbl, sec = tm.group(1).upper(), tm.group(2).strip()
                                    if not sec:
                                        for nc in r[ci+1:]:
                                            if nc and str(nc).strip(): sec = str(nc).strip(); break
                                    if sec: imap[lbl] = sec
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
    p_defs = _load_page_definitions(meta['company_code'])
    for pd in p_data:
        l = pd["page_label"]
        if l in p_defs: pd["section"] = p_defs[l]
        elif l in imap: pd["section"] = imap[l]
    res = {**meta, "total_pages": tp, "page_definitions_found": bool(p_defs or imap), "pages": p_data}
    out = Path(PROCESSED_OUTPUT_DIR) / f"{meta['company_code']}_{meta['quarter']}_{meta['fy']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f: json.dump(res, f, indent=2, ensure_ascii=False)
    return res
