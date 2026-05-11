"""
Rebuild master page definitions from all existing company-specific definition files.
Run this script after uploading PDFs to consolidate all L-page mappings.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pdf_parser import _update_master_page_definitions
from src.config import PROCESSED_OUTPUT_DIR
import json


def main():
    """Rebuild master page definitions and display results."""
    print("🔄 Rebuilding master page definitions...")
    print(f"📁 Scanning: {PROCESSED_OUTPUT_DIR}\n")
    
    # Update master definitions
    _update_master_page_definitions()
    
    # Display results
    processed_dir = Path(PROCESSED_OUTPUT_DIR)
    
    master_file = processed_dir / "master_page_definitions.json"
    term_lookup_file = processed_dir / "master_term_to_page.json"
    
    if master_file.exists():
        with open(master_file, "r", encoding="utf-8") as f:
            master_defs = json.load(f)
        
        print("✅ Master Page Definitions Created:")
        print(f"   📄 {master_file}")
        print(f"   📊 {len(master_defs)} L-pages mapped\n")
        
        print("📋 L-Page Mappings:")
        for lpage in sorted(master_defs.keys()):
            terms = master_defs[lpage]
            print(f"   {lpage}: {', '.join(terms)}")
    
    if term_lookup_file.exists():
        with open(term_lookup_file, "r", encoding="utf-8") as f:
            term_to_page = json.load(f)
        
        print(f"\n✅ Term-to-Page Lookup Created:")
        print(f"   📄 {term_lookup_file}")
        print(f"   🔍 {len(term_to_page)} searchable terms\n")
        
        print("🔍 Sample Term Lookups:")
        sample_terms = list(term_to_page.items())[:10]
        for term, lpage in sample_terms:
            print(f"   '{term}' → {lpage}")
        
        if len(term_to_page) > 10:
            print(f"   ... and {len(term_to_page) - 10} more terms")
    
    print("\n✨ Done! You can now search by any term to find the corresponding L-page.")


if __name__ == "__main__":
    main()
