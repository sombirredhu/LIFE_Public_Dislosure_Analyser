import streamlit as st

def render_tab_history():
    """Tab 6: Query History."""
    st.header("📜 Query History")
    
    if "query_history" not in st.session_state or not st.session_state["query_history"]:
        st.info("No queries asked in this session yet.")
        return
        
    for i, item in enumerate(st.session_state["query_history"]):
        with st.expander(f"Q: {item['question']} ({item['timestamp']})"):
            st.markdown("### Answer")
            st.markdown(item["result"]["answer"])
            
            if item["result"].get("sources"):
                st.markdown("**📚 Sources:**")
                for source in item["result"]["sources"]:
                    st.markdown(f"- {source}")
            
            with st.container():
                cols = st.columns(4)
                cols[0].caption(f"**Model:** {item['result'].get('model_used', 'N/A')}")
                cols[1].caption(f"**Confidence:** {item['result'].get('confidence', 'N/A')}")
                cols[2].caption(f"**Chunks:** {item['result'].get('chunks_used', 0)}")
                if item["filters"]:
                    cols[3].caption(f"**Filters:** {item['filters']}")
        
        # Add spacing
        st.markdown("")



