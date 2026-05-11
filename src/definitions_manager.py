"""
Definitions Manager - Manages custom term definitions and synonyms.
Supports two types of definitions:
1. Page Definitions: Terms that map to L-pages (e.g., GWP = L-4)
2. Calculation Definitions: Formulas (e.g., Margin % = Margin / ANP)
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

from src.config import PROCESSED_OUTPUT_DIR

logger = logging.getLogger(__name__)

CUSTOM_DEFINITIONS_FILE = Path(PROCESSED_OUTPUT_DIR) / "custom_definitions.json"


def _load_custom_definitions() -> Dict[str, Any]:
    """
    Load custom definitions from JSON file.
    
    Returns:
        Dict with structure:
        {
            "page_definitions": {
                "L-4": ["GWP", "Gross Written Premium", "Premium Schedule"],
                "L-5": ["Analytical Ratios", "Key Ratios"]
            },
            "calculations": {
                "Margin %": "Margin / ANP",
                "ROE": "Net Profit / Equity"
            },
            "metadata": {
                "last_updated": "2024-01-15T10:30:00",
                "total_page_terms": 5,
                "total_calculations": 2
            }
        }
    """
    if not CUSTOM_DEFINITIONS_FILE.exists():
        return {
            "page_definitions": {},
            "calculations": {},
            "metadata": {
                "last_updated": None,
                "total_page_terms": 0,
                "total_calculations": 0
            }
        }
    
    try:
        with open(CUSTOM_DEFINITIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error("Failed to load custom definitions: %s", e)
        return {
            "page_definitions": {},
            "calculations": {},
            "metadata": {
                "last_updated": None,
                "total_page_terms": 0,
                "total_calculations": 0
            }
        }


def _save_custom_definitions(definitions: Dict[str, Any]) -> bool:
    """Save custom definitions to JSON file."""
    try:
        # Update metadata
        definitions["metadata"]["last_updated"] = datetime.now().isoformat()
        definitions["metadata"]["total_page_terms"] = sum(
            len(terms) for terms in definitions["page_definitions"].values()
        )
        definitions["metadata"]["total_calculations"] = len(definitions["calculations"])
        
        CUSTOM_DEFINITIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CUSTOM_DEFINITIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(definitions, f, indent=2, ensure_ascii=False)
        
        logger.info("Saved custom definitions: %d page terms, %d calculations",
                   definitions["metadata"]["total_page_terms"],
                   definitions["metadata"]["total_calculations"])
        return True
    except Exception as e:
        logger.error("Failed to save custom definitions: %s", e)
        return False


def merge_with_pdf_definitions():
    """
    Merge PDF-extracted definitions with custom definitions.
    PDF definitions are added to page_definitions if not already present.
    """
    custom_defs = _load_custom_definitions()
    
    # Load master page definitions from PDFs
    master_file = Path(PROCESSED_OUTPUT_DIR) / "master_page_definitions.json"
    if not master_file.exists():
        logger.info("No master page definitions found to merge")
        return
    
    try:
        with open(master_file, "r", encoding="utf-8") as f:
            pdf_defs = json.load(f)
        
        # Merge PDF definitions into custom definitions
        for lpage, terms in pdf_defs.items():
            if lpage not in custom_defs["page_definitions"]:
                custom_defs["page_definitions"][lpage] = []
            
            # Add terms that don't already exist (case-insensitive check)
            existing_lower = [t.lower() for t in custom_defs["page_definitions"][lpage]]
            for term in terms:
                if term.lower() not in existing_lower:
                    custom_defs["page_definitions"][lpage].append(term)
        
        _save_custom_definitions(custom_defs)
        logger.info("Merged PDF definitions with custom definitions")
    except Exception as e:
        logger.error("Failed to merge PDF definitions: %s", e)


def add_page_definition(term: str, lpage: str) -> Tuple[bool, str]:
    """
    Add a term to a specific L-page.
    
    Args:
        term: The term to add (e.g., "GWP", "Gross Written Premium")
        lpage: The L-page code (e.g., "L-4")
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    term = term.strip()
    lpage = lpage.strip().upper()
    
    if not term:
        return False, "Term cannot be empty"
    
    if not lpage.startswith("L-"):
        return False, "L-page must start with 'L-' (e.g., L-4)"
    
    definitions = _load_custom_definitions()
    
    # Check if term already exists for a different L-page
    for existing_lpage, terms in definitions["page_definitions"].items():
        if term.lower() in [t.lower() for t in terms]:
            if existing_lpage != lpage:
                return False, f"Term '{term}' already mapped to {existing_lpage}"
            else:
                return False, f"Term '{term}' already exists for {lpage}"
    
    # Add term to L-page
    if lpage not in definitions["page_definitions"]:
        definitions["page_definitions"][lpage] = []
    
    definitions["page_definitions"][lpage].append(term)
    
    if _save_custom_definitions(definitions):
        return True, f"Added '{term}' → {lpage}"
    else:
        return False, "Failed to save definition"


def add_calculation(name: str, formula: str) -> Tuple[bool, str]:
    """
    Add a calculation definition.
    
    Args:
        name: Calculation name (e.g., "Margin %", "ROE")
        formula: Formula (e.g., "Margin / ANP", "Net Profit / Equity")
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    name = name.strip()
    formula = formula.strip()
    
    if not name:
        return False, "Calculation name cannot be empty"
    
    if not formula:
        return False, "Formula cannot be empty"
    
    definitions = _load_custom_definitions()
    
    # Check if calculation already exists
    if name in definitions["calculations"]:
        return False, f"Calculation '{name}' already exists with formula: {definitions['calculations'][name]}"
    
    definitions["calculations"][name] = formula
    
    if _save_custom_definitions(definitions):
        return True, f"Added calculation: {name} = {formula}"
    else:
        return False, "Failed to save calculation"


def delete_page_definition(term: str) -> Tuple[bool, str]:
    """
    Delete a term from page definitions.
    
    Args:
        term: The term to delete
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    term = term.strip()
    definitions = _load_custom_definitions()
    
    # Find and remove term
    for lpage, terms in definitions["page_definitions"].items():
        for i, t in enumerate(terms):
            if t.lower() == term.lower():
                del definitions["page_definitions"][lpage][i]
                
                # Remove L-page if no terms left
                if not definitions["page_definitions"][lpage]:
                    del definitions["page_definitions"][lpage]
                
                if _save_custom_definitions(definitions):
                    return True, f"Deleted '{term}' from {lpage}"
                else:
                    return False, "Failed to save changes"
    
    return False, f"Term '{term}' not found"


def delete_calculation(name: str) -> Tuple[bool, str]:
    """
    Delete a calculation definition.
    
    Args:
        name: Calculation name to delete
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    name = name.strip()
    definitions = _load_custom_definitions()
    
    if name not in definitions["calculations"]:
        return False, f"Calculation '{name}' not found"
    
    del definitions["calculations"][name]
    
    if _save_custom_definitions(definitions):
        return True, f"Deleted calculation '{name}'"
    else:
        return False, "Failed to save changes"


def get_lpage_for_term(term: str) -> Optional[str]:
    """
    Find which L-page a term refers to (case-insensitive).
    
    Args:
        term: The term to search for
    
    Returns:
        L-page code (e.g., "L-4") or None if not found
    """
    term_lower = term.strip().lower()
    definitions = _load_custom_definitions()
    
    for lpage, terms in definitions["page_definitions"].items():
        if term_lower in [t.lower() for t in terms]:
            return lpage
    
    return None


def get_calculation_formula(name: str) -> Optional[str]:
    """
    Get the formula for a calculation (case-insensitive).
    
    Args:
        name: Calculation name
    
    Returns:
        Formula string or None if not found
    """
    name_lower = name.strip().lower()
    definitions = _load_custom_definitions()
    
    for calc_name, formula in definitions["calculations"].items():
        if calc_name.lower() == name_lower:
            return formula
    
    return None


def get_all_terms_for_lpage(lpage: str) -> List[str]:
    """
    Get all terms that map to a specific L-page.
    
    Args:
        lpage: L-page code (e.g., "L-4")
    
    Returns:
        List of terms
    """
    lpage = lpage.strip().upper()
    definitions = _load_custom_definitions()
    
    return definitions["page_definitions"].get(lpage, [])


def get_all_definitions() -> Dict[str, Any]:
    """
    Get all definitions (page definitions and calculations).
    
    Returns:
        Complete definitions dictionary
    """
    return _load_custom_definitions()


def search_definitions(query: str) -> Dict[str, Any]:
    """
    Search for a term in both page definitions and calculations.
    
    Args:
        query: Search term
    
    Returns:
        Dict with search results:
        {
            "found": bool,
            "type": "page" | "calculation" | "both" | None,
            "lpage": str or None,
            "formula": str or None,
            "related_terms": List[str]
        }
    """
    query_lower = query.strip().lower()
    definitions = _load_custom_definitions()
    
    result = {
        "found": False,
        "type": None,
        "lpage": None,
        "formula": None,
        "related_terms": []
    }
    
    # Search in page definitions
    for lpage, terms in definitions["page_definitions"].items():
        if query_lower in [t.lower() for t in terms]:
            result["found"] = True
            result["type"] = "page"
            result["lpage"] = lpage
            result["related_terms"] = [t for t in terms if t.lower() != query_lower]
            break
    
    # Search in calculations
    for calc_name, formula in definitions["calculations"].items():
        if calc_name.lower() == query_lower:
            if result["found"]:
                result["type"] = "both"
            else:
                result["found"] = True
                result["type"] = "calculation"
            result["formula"] = formula
            break
    
    return result


if __name__ == "__main__":
    # Test the definitions manager
    print("🔧 Definitions Manager Test\n")
    
    # Merge with PDF definitions
    print("Merging with PDF definitions...")
    merge_with_pdf_definitions()
    
    # Add some test definitions
    print("\nAdding test definitions...")
    success, msg = add_page_definition("GWP", "L-4")
    print(f"  {msg}")
    
    success, msg = add_page_definition("Gross Written Premium", "L-4")
    print(f"  {msg}")
    
    success, msg = add_calculation("Margin %", "Margin / ANP")
    print(f"  {msg}")
    
    # Search for a term
    print("\nSearching for 'GWP'...")
    result = search_definitions("GWP")
    print(f"  Found: {result['found']}")
    print(f"  Type: {result['type']}")
    print(f"  L-page: {result['lpage']}")
    print(f"  Related terms: {result['related_terms']}")
    
    # Get all definitions
    print("\nAll definitions:")
    all_defs = get_all_definitions()
    print(f"  Page definitions: {len(all_defs['page_definitions'])} L-pages")
    print(f"  Calculations: {len(all_defs['calculations'])} formulas")
    print(f"  Last updated: {all_defs['metadata']['last_updated']}")
