import streamlit as st
import pandas as pd
import logging
import json
import time
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config import *
from src.rag_pipeline import answer_question
from src.ingestor import ingest_pdf
from src.definitions_manager import (
    merge_with_pdf_definitions, add_page_definition, 
    add_calculation, get_all_definitions, 
    delete_page_definition, delete_calculation, 
    search_definitions
)

def render_tab_definitions():
    """Tab 4: Manage Definitions."""
    st.header("📚 Manage Definitions")
    
    st.markdown("""
    Define custom terms and calculations to help the system understand your queries better.
    
    **Two types of definitions:**
    - **Page Definitions**: Map terms to L-pages (e.g., GWP → L-4)
    - **Calculations**: Define formulas (e.g., Margin % = Margin / ANP)
    """)
    
    # Merge with PDF definitions button
    col_merge, col_space = st.columns([1, 3])
    with col_merge:
        if st.button("🔄 Sync with PDF Definitions", help="Merge definitions extracted from uploaded PDFs"):
            merge_with_pdf_definitions()
            st.success("✓ Synced with PDF definitions")
            st.rerun()
    
    st.markdown("---")
    
    # Two columns: Add definitions | View/Delete definitions
    col_add, col_view = st.columns([1, 1])
    
    # ===== LEFT COLUMN: Add Definitions =====
    with col_add:
        st.subheader("➕ Add New Definition")
        
        def_type = st.radio(
            "Definition Type",
            options=["Page Definition", "Calculation"],
            horizontal=True,
            key="def_type_radio"
        )
        
        if def_type == "Page Definition":
            st.markdown("**Map a term to an L-page**")
            
            term_input = st.text_input(
                "Term",
                placeholder="e.g., GWP, Premium Schedule",
                key="page_term_input"
            )
            
            lpage_input = st.text_input(
                "L-Page",
                placeholder="e.g., L-4",
                key="lpage_input"
            )
            
            if st.button("➕ Add Page Definition", type="primary", use_container_width=True):
                if term_input and lpage_input:
                    success, message = add_page_definition(term_input, lpage_input)
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
                else:
                    st.warning("Please fill in both fields")
        
        else:  # Calculation
            st.markdown("**Define a calculation formula**")
            
            calc_name = st.text_input(
                "Calculation Name",
                placeholder="e.g., Margin %, ROE",
                key="calc_name_input"
            )
            
            calc_formula = st.text_area(
                "Formula",
                placeholder="e.g., Margin / ANP, Net Profit / Equity",
                height=100,
                key="calc_formula_input"
            )
            
            if st.button("➕ Add Calculation", type="primary", use_container_width=True):
                if calc_name and calc_formula:
                    success, message = add_calculation(calc_name, calc_formula)
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
                else:
                    st.warning("Please fill in both fields")
    
    # ===== RIGHT COLUMN: View/Delete Definitions =====
    with col_view:
        st.subheader("📋 Current Definitions")
        
        all_defs = get_all_definitions()
        
        # Tabs for Page Definitions and Calculations
        tab_page, tab_calc = st.tabs(["📄 Page Definitions", "🧮 Calculations"])
        
        with tab_page:
            if not all_defs["page_definitions"]:
                st.info("No page definitions yet. Add some or sync with PDF definitions.")
            else:
                st.markdown(f"**{all_defs['metadata']['total_page_terms']} terms mapped to {len(all_defs['page_definitions'])} L-pages**")
                
                for lpage in sorted(all_defs["page_definitions"].keys()):
                    terms = all_defs["page_definitions"][lpage]
                    
                    with st.expander(f"**{lpage}** ({len(terms)} terms)"):
                        for term in sorted(terms):
                            col_term, col_del = st.columns([4, 1])
                            with col_term:
                                st.markdown(f"• {term}")
                            with col_del:
                                if st.button("🗑️", key=f"del_page_{lpage}_{term}", help=f"Delete '{term}'"):
                                    success, message = delete_page_definition(term)
                                    if success:
                                        st.success(message)
                                        st.rerun()
                                    else:
                                        st.error(message)
        
        with tab_calc:
            if not all_defs["calculations"]:
                st.info("No calculations defined yet. Add some above.")
            else:
                st.markdown(f"**{len(all_defs['calculations'])} calculations defined**")
                
                for calc_name in sorted(all_defs["calculations"].keys()):
                    formula = all_defs["calculations"][calc_name]
                    
                    col_calc, col_del = st.columns([4, 1])
                    with col_calc:
                        st.markdown(f"**{calc_name}**")
                        st.code(formula, language=None)
                    with col_del:
                        if st.button("🗑️", key=f"del_calc_{calc_name}", help=f"Delete '{calc_name}'"):
                            success, message = delete_calculation(calc_name)
                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)
    
    # ===== BOTTOM: Search Definitions =====
    st.markdown("---")
    st.subheader("🔍 Search Definitions")
    
    search_query = st.text_input(
        "Search for a term or calculation",
        placeholder="e.g., GWP, Margin %, Premium",
        key="search_def_input"
    )
    
    if search_query:
        result = search_definitions(search_query)
        
        if result["found"]:
            st.success(f"✓ Found: **{search_query}**")
            
            if result["type"] in ["page", "both"]:
                st.markdown(f"**📄 Page Definition:** {result['lpage']}")
                if result["related_terms"]:
                    st.markdown(f"**Related terms:** {', '.join(result['related_terms'])}")
            
            if result["type"] in ["calculation", "both"]:
                st.markdown(f"**🧮 Calculation Formula:**")
                st.code(result["formula"], language=None)
        else:
            st.warning(f"No definition found for '{search_query}'")
    
    # Metadata
    if all_defs["metadata"]["last_updated"]:
        st.caption(f"Last updated: {all_defs['metadata']['last_updated']}")



