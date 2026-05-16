"""
Streamlit Web UI for Insurance PD Report Analyzer.
Main entry point — routes to modular UI components in src/ui/
"""

import sys
from pathlib import Path
import streamlit as st

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.logging_config import setup_logging
setup_logging()

from src.config import APP_TITLE
from src.ui.base import (
    _check_password, render_css, render_header, 
    render_sidebar, _warm_up_models, _auto_reindex_if_needed
)
from src.ui.ask import render_tab_ask_question
from src.ui.upload import render_tab_upload
from src.ui.status import render_tab_index_status
from src.ui.history import render_tab_history
from src.ui.viz import render_tab_vector_visualization
from src.ui.defs import render_tab_definitions

def main():
    # Page config
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Auth gate
    if not _check_password():
        return

    # Warm up models
    _warm_up_models()
    
    # Auto-reindex on startup if needed
    _auto_reindex_if_needed()

    # Styling
    render_css()

    # Sidebar
    render_sidebar()

    # Header
    render_header()

    # Tabs
    tab_ask, tab_history, tab_upload, tab_status, tab_viz, tab_defs = st.tabs([
        "🔍 Ask Questions", 
        "📜 History",
        "📂 Upload Reports", 
        "📊 Index Status",
        "🌐 Vector Viz",
        "📝 Definitions"
    ])

    with tab_ask:
        render_tab_ask_question()
    
    with tab_history:
        render_tab_history()

    with tab_upload:
        render_tab_upload()

    with tab_status:
        render_tab_index_status()

    with tab_viz:
        render_tab_vector_visualization()

    with tab_defs:
        render_tab_definitions()

if __name__ == "__main__":
    main()
