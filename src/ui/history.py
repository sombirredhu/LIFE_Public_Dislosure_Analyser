import streamlit as st
from src.history_store import load_history_entries

def render_tab_history():
    """Tab 6: Query History."""
    st.header("📜 Query History")

    session_items = st.session_state.get("query_history", [])
    file_items = load_history_entries(limit=300)

    # Merge with preference for current session ordering.
    merged = []
    seen = set()
    for item in session_items + file_items:
        key = (item.get("timestamp"), item.get("question"), item.get("result", {}).get("model_used"))
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)

    if not merged:
        st.info("No queries asked in this session yet.")
        return

    for i, item in enumerate(merged):
        q = item.get("question", "Unknown question")
        ts = item.get("timestamp", "Unknown time")
        result = item.get("result", {})
        with st.expander(f"Q: {q} ({ts})"):
            st.markdown("### Answer")
            st.markdown(result.get("answer", "No answer available"))
            
            if result.get("sources"):
                st.markdown("**📚 Sources:**")
                for source in result["sources"]:
                    st.markdown(f"- {source}")
            
            with st.container():
                cols = st.columns(4)
                cols[0].caption(f"**Model:** {result.get('model_used', 'N/A')}")
                cols[1].caption(f"**Confidence:** {result.get('confidence', 'N/A')}")
                cols[2].caption(f"**Chunks:** {result.get('chunks_used', 0)}")
                if item.get("filters"):
                    cols[3].caption(f"**Filters:** {item.get('filters')}")
        
        # Add spacing
        st.markdown("")



