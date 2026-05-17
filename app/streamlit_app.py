import sys
from pathlib import Path
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.logging_config import setup_logging
setup_logging()

from src.config import APP_TITLE, config_health_report
from src.ui.base import (_check_password, render_css, render_header, render_sidebar, _warm_up_models, _auto_reindex_if_needed)
from src.ui.ask import render_tab_ask_question
from src.ui.upload import render_tab_upload
from src.ui.status import render_tab_index_status
from src.ui.history import render_tab_history
from src.ui.viz import render_tab_vector_visualization
from src.ui.defs import render_tab_definitions

def main():
    st.set_page_config(page_title=APP_TITLE, page_icon="📊", layout="wide", initial_sidebar_state="expanded")
    if not _check_password(): return
    health = config_health_report()
    if health["errors"]:
        st.error("Configuration errors detected:\n- " + "\n- ".join(health["errors"]))
        st.stop()
    if health["warnings"]:
        st.warning("Configuration warnings:\n- " + "\n- ".join(health["warnings"]))
    _warm_up_models()
    _auto_reindex_if_needed()
    render_css()
    render_sidebar()
    render_header()
    tabs = st.tabs(["🔍 Ask Questions", "📜 History", "📂 Upload Reports", "📊 Index Status", "🌐 Vector Viz", "📝 Definitions"])
    with tabs[0]: render_tab_ask_question()
    with tabs[1]: render_tab_history()
    with tabs[2]: render_tab_upload()
    with tabs[3]: render_tab_index_status()
    with tabs[4]: render_tab_vector_visualization()
    with tabs[5]: render_tab_definitions()

if __name__ == "__main__":
    main()
