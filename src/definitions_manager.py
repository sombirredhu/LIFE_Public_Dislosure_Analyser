import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from src.config import PROCESSED_OUTPUT_DIR

logger = logging.getLogger(__name__)
CUSTOM_DEFINITIONS_FILE = Path(PROCESSED_OUTPUT_DIR) / "custom_definitions.json"

def _load_custom_definitions() -> Dict[str, Any]:
    if not CUSTOM_DEFINITIONS_FILE.exists(): return {"page_definitions": {}, "calculations": {}, "metadata": {"last_updated": None, "total_page_terms": 0, "total_calculations": 0}}
    try:
        with open(CUSTOM_DEFINITIONS_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except Exception: return {"page_definitions": {}, "calculations": {}, "metadata": {"last_updated": None, "total_page_terms": 0, "total_calculations": 0}}

def _save_custom_definitions(defs: Dict[str, Any]) -> bool:
    try:
        defs["metadata"]["last_updated"] = datetime.now().isoformat()
        defs["metadata"]["total_page_terms"] = sum(len(ts) for ts in defs["page_definitions"].values())
        defs["metadata"]["total_calculations"] = len(defs["calculations"])
        CUSTOM_DEFINITIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CUSTOM_DEFINITIONS_FILE, "w", encoding="utf-8") as f: json.dump(defs, f, indent=2, ensure_ascii=False)
        return True
    except Exception: return False

def merge_with_pdf_definitions():
    cdefs = _load_custom_definitions()
    mf = Path(PROCESSED_OUTPUT_DIR) / "master_page_definitions.json"
    if not mf.exists(): return
    try:
        with open(mf, "r", encoding="utf-8") as f:
            pdf_defs = json.load(f)
            for lp, ts in pdf_defs.items():
                if lp not in cdefs["page_definitions"]: cdefs["page_definitions"][lp] = []
                ex_low = [t.lower() for t in cdefs["page_definitions"][lp]]
                for t in ts:
                    if t.lower() not in ex_low: cdefs["page_definitions"][lp].append(t)
            _save_custom_definitions(cdefs)
    except Exception: pass

def add_page_definition(term: str, lpage: str) -> Tuple[bool, str]:
    term, lpage = term.strip(), lpage.strip().upper()
    if not term: return False, "Empty term"
    if not lpage.startswith("L-"): return False, "Invalid L-page"
    defs = _load_custom_definitions()
    for elp, ts in defs["page_definitions"].items():
        if term.lower() in [t.lower() for t in ts]: return False, f"Already mapped to {elp}"
    if lpage not in defs["page_definitions"]: defs["page_definitions"][lpage] = []
    defs["page_definitions"][lpage].append(term)
    return (_save_custom_definitions(defs), f"Added {term} → {lpage}")

def add_calculation(name: str, formula: str) -> Tuple[bool, str]:
    name, formula = name.strip(), formula.strip()
    if not name or not formula: return False, "Empty name/formula"
    defs = _load_custom_definitions()
    if name in defs["calculations"]: return False, "Calculation exists"
    defs["calculations"][name] = formula
    return (_save_custom_definitions(defs), f"Added calculation {name}")

def delete_page_definition(term: str) -> Tuple[bool, str]:
    defs = _load_custom_definitions()
    for lp, ts in defs["page_definitions"].items():
        for i, t in enumerate(ts):
            if t.lower() == term.lower():
                del ts[i]
                if not ts: del defs["page_definitions"][lp]
                return (_save_custom_definitions(defs), f"Deleted {term}")
    return False, "Not found"

def delete_calculation(name: str) -> Tuple[bool, str]:
    defs = _load_custom_definitions()
    if name.strip() not in defs["calculations"]: return False, "Not found"
    del defs["calculations"][name.strip()]
    return (_save_custom_definitions(defs), f"Deleted {name}")

def get_lpage_for_term(term: str) -> Optional[str]:
    tl = term.strip().lower()
    defs = _load_custom_definitions()
    for lp, ts in defs["page_definitions"].items():
        if tl in [t.lower() for t in ts]: return lp
    return None

def get_calculation_formula(name: str) -> Optional[str]:
    nl = name.strip().lower()
    defs = _load_custom_definitions()
    for cn, f in defs["calculations"].items():
        if cn.lower() == nl: return f
    return None

def get_all_terms_for_lpage(lpage: str) -> List[str]:
    return _load_custom_definitions()["page_definitions"].get(lpage.strip().upper(), [])

def get_all_definitions() -> Dict[str, Any]:
    return _load_custom_definitions()

def search_definitions(query: str) -> Dict[str, Any]:
    ql = query.strip().lower()
    defs = _load_custom_definitions()
    res = {"found": False, "type": None, "lpage": None, "formula": None, "related_terms": []}
    for lp, ts in defs["page_definitions"].items():
        if ql in [t.lower() for t in ts]:
            res.update({"found": True, "type": "page", "lpage": lp, "related_terms": [t for t in ts if t.lower() != ql]})
            break
    for cn, f in defs["calculations"].items():
        if cn.lower() == ql:
            res["type"] = "both" if res["found"] else "calculation"
            res.update({"found": True, "formula": f})
            break
    return res
