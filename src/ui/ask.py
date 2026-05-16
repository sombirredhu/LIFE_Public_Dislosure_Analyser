import streamlit as st
import logging
import json
import time
from datetime import datetime
from typing import Any, Dict, Optional
import re
from src.config import *
from src.rag_pipeline import answer_question
from src.embedder import (
    get_collection_stats, get_indexed_companies,
    get_available_quarters, get_available_fys,
    invalidate_metadata_cache
)
from src.definitions_manager import add_page_definition, add_calculation, search_definitions

logger = logging.getLogger(__name__)

def render_tab_ask_question():
    st.header("💬 Ask a Question")
    invalidate_metadata_cache()
    stats = get_collection_stats()
    if stats['total_chunks'] == 0:
        st.warning("⚠️ No data indexed yet. Please upload PDF files in the 'Upload Reports' tab first.")
        return
    col1, col2, col3 = st.columns(3)
    with col1: st.metric("Indexed Files", stats['unique_files'])
    with col2: st.metric("Total Chunks", stats['total_chunks'])
    with col3: st.metric("Companies", len(stats['chunks_by_company']))
    st.markdown("---")
    with st.expander("💡 Quick Commands for Definitions"):
        st.markdown("**Add Page Definition:** `define GWP as L-4`\n**Add Calculation:** `define Margin % = Margin / ANP`\n**Search:** `what is GWP?`")
    question = st.text_area("Enter your question:", placeholder="Example: Which company had the highest gross written premium in Q1 FY25?", height=100, key="ask_question_input")
    col1, col2, col3 = st.columns(3)
    with col1:
        available_companies = get_indexed_companies()
        company_filter = st.multiselect("Filter by Company (optional)", options=available_companies, default=[])
    with col2:
        available_quarters = get_available_quarters()
        quarter_options = ["All"] + available_quarters if available_quarters else ["All"]
        quarter_filter = st.selectbox("Filter by Quarter (optional)", options=quarter_options, index=0)
    with col3:
        available_fys = get_available_fys()
        fy_options = ["All"] + available_fys if available_fys else ["All"]
        fy_filter = st.selectbox("Filter by FY (optional)", options=fy_options, index=0)
    if st.button("🔍 Get Answer", type="primary", width="stretch"):
        if not question.strip():
            st.error("Please enter a question.")
            return
        now = time.time()
        if "rate_limit" not in st.session_state: st.session_state["rate_limit"] = []
        st.session_state["rate_limit"] = [ts for ts in st.session_state["rate_limit"] if now - ts < 60]
        if len(st.session_state["rate_limit"]) >= 10:
            st.error("⏳ Rate limit exceeded. Please wait a minute before asking more questions.")
            return
        st.session_state["rate_limit"].append(now)
        def_result = _process_definition_command(question)
        if def_result:
            if def_result["success"]: st.success(def_result["message"])
            else: st.error(def_result["message"])
            return
        filters: Dict[str, Any] = {}
        if company_filter: filters["company_code"] = company_filter[0] if len(company_filter) == 1 else {"$in": company_filter}
        if quarter_filter != "All": filters["quarter"] = quarter_filter
        if fy_filter != "All": filters["fy"] = fy_filter
        with st.spinner("🤔 Thinking..."):
            try:
                result = answer_question(question, filters=filters if filters else None, free_model=st.session_state.get("free_model"), paid_model=st.session_state.get("paid_model"))
                st.session_state["last_answer"] = {"question": question, "result": result, "filters": filters, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "model_selected": st.session_state.get("selected_model_label", "")}
                if "query_history" not in st.session_state: st.session_state["query_history"] = []
                st.session_state["query_history"].insert(0, st.session_state["last_answer"].copy())
            except Exception as e:
                logger.exception("[UI] answer_question failed | question=%r | filters=%s", question[:100], filters)
                st.error(f"Error: {str(e)}")
                st.exception(e)
    _render_last_answer()

def _render_last_answer():
    entry = st.session_state.get("last_answer")
    if not entry: return
    result = entry["result"]
    question = entry["question"]
    filters = entry["filters"]
    st.markdown("---")
    st.markdown("### 📝 Answer")
    confidence = result.get('confidence', 'low')
    if confidence == 'high': badge_class, badge_text = 'confidence-high', '✓ High Confidence'
    elif confidence == 'medium': badge_class, badge_text = 'confidence-medium', '⚠ Medium Confidence'
    else: badge_class, badge_text = 'confidence-low', '✗ No Data'
    model_used = result.get('model_used', '')
    is_free = 'free' in model_used.lower()
    col_badge, col_model = st.columns([2, 1])
    with col_badge: st.markdown(f'<span class="{badge_class}">{badge_text}</span>', unsafe_allow_html=True)
    with col_model:
        if is_free: st.success("🟢 Free Model")
        else: st.info("🔵 Paid Model")
    st.caption(f"Model: `{model_used}` · {entry.get('timestamp', '')}")
    st.markdown(result['answer'])
    answer_json = json.dumps(result['answer'])
    copy_html = f"""<div style="margin:10px 0;"><button onclick="copyAns()" style="background:var(--secondary-background-color,#f0f2f6);border:1px solid var(--border-color,#d0d0d0);border-radius:4px; padding:8px 16px; cursor:pointer;font-size:14px; font-weight:500; color:var(--text-color,#262730);display:inline-flex; align-items:center; gap:6px;">📋 Copy Answer</button><span id="ans-fb" style="margin-left:10px;color:#28a745;font-weight:500;display:none;">✓ Copied!</span></div><script>function copyAns(){{navigator.clipboard.writeText({answer_json}).then(function(){{var f=document.getElementById('ans-fb');f.style.display='inline';setTimeout(function(){{f.style.display='none';}},3000);}});}}</script>"""
    st.html(copy_html, height=50)
    with st.expander("📄 View as Plain Text"): st.code(result['answer'], language=None)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    sources_md = "\n".join([f"- {s}" for s in result.get('sources', [])])
    st.download_button(label="📥 Download as Markdown", data=f"# Question: {question}\n\n## Answer\n{result['answer']}\n\n## Sources\n{sources_md}", file_name=f"RAG_Answer_{ts}.md", mime="text/markdown")
    if result.get('sources'):
        st.markdown("---")
        st.markdown("**📚 Sources:**")
        for src in result['sources']: st.markdown(f"- {src}")
    with st.expander("ℹ️ Query Details"):
        st.write(f"**Chunks Used:** {result['chunks_used']}")
        st.write(f"**Confidence:** {result['confidence']}")
        st.write(f"**Model Used:** {result.get('model_used', 'N/A')}")
        if filters: st.write(f"**Filters Applied:** {filters}")

def _process_definition_command(text: str) -> Optional[Dict[str, Any]]:
    page_pattern1 = re.compile(r'(?:define|add definition:?)\s+(.+?)\s+(?:as|=)\s+(l-\d+)', re.IGNORECASE)
    match = page_pattern1.search(text)
    if match:
        success, message = add_page_definition(match.group(1).strip(), match.group(2).strip().upper())
        return {"success": success, "message": message}
    calc_pattern = re.compile(r'(?:define|add calculation:?)\s+(.+?)\s*=\s*(.+)', re.IGNORECASE)
    match = calc_pattern.search(text)
    if match:
        if not match.group(2).strip().upper().startswith('L-'):
            success, message = add_calculation(match.group(1).strip(), match.group(2).strip())
            return {"success": success, "message": message}
    search_pattern = re.compile(r'(?:what is|define)\s+(.+?)[\?]?$', re.IGNORECASE)
    match = search_pattern.search(text)
    if match and len(text.split()) <= 5:
        term = match.group(1).strip()
        result = search_definitions(term)
        if result["found"]:
            msg_parts = [f"**{term}**"]
            if result["type"] in ["page", "both"]:
                msg_parts.append(f"📄 Page: {result['lpage']}")
                if result["related_terms"]: msg_parts.append(f"Related: {', '.join(result['related_terms'])}")
            if result["type"] in ["calculation", "both"]: msg_parts.append(f"🧮 Formula: {result['formula']}")
            return {"success": True, "message": "\n".join(msg_parts)}
        else: return {"success": False, "message": f"No definition found for '{term}'"}
    return None
