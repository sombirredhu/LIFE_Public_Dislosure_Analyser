import streamlit as st
import logging
import json
import time
from datetime import datetime
from typing import Any, Dict, Optional

from src.config import *
from src.rag_pipeline import answer_question
from src.embedder import (
    get_collection_stats, get_indexed_companies, 
    get_available_quarters, get_available_fys
)
from src.definitions_manager import add_page_definition, add_calculation, search_definitions

logger = logging.getLogger(__name__)

def render_tab_ask_question():
    """Tab 1: Ask a Question."""
    st.header("💬 Ask a Question")
    
    # Check if data exists
    stats = get_collection_stats()
    if stats['total_chunks'] == 0:
        st.warning("⚠️ No data indexed yet. Please upload PDF files in the 'Upload Reports' tab first.")
        return
    
    # Show quick stats
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Indexed Files", stats['unique_files'])
    with col2:
        st.metric("Total Chunks", stats['total_chunks'])
    with col3:
        st.metric("Companies", len(stats['chunks_by_company']))
    
    st.markdown("---")
    
    # Quick help for definition commands
    with st.expander("💡 Quick Commands for Definitions"):
        st.markdown("""
        You can manage definitions directly from chat:
        
        **Add Page Definition:**
        - `define GWP as L-4`
        - `add definition: Premium Schedule = L-5`
        
        **Add Calculation:**
        - `define Margin % = Margin / ANP`
        - `add calculation: ROE = Net Profit / Equity`
        
        **Search Definition:**
        - `what is GWP?`
        - `define GWP` (without adding anything)
        
        Or use the **Definitions** tab for full management interface.
        """)
    
    # Question input
    question = st.text_area(
        "Enter your question:",
        placeholder="Example: Which company had the highest gross written premium in Q1 FY25?",
        height=100
    )
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        available_companies = get_indexed_companies()
        company_filter = st.multiselect(
            "Filter by Company (optional)",
            options=available_companies,
            default=[]
        )
    
    with col2:
        available_quarters = get_available_quarters()
        quarter_options = ["All"] + available_quarters if available_quarters else ["All"]
        quarter_filter = st.selectbox(
            "Filter by Quarter (optional)",
            options=quarter_options,
            index=0
        )
    
    with col3:
        available_fys = get_available_fys()
        fy_options = ["All"] + available_fys if available_fys else ["All"]
        fy_filter = st.selectbox(
            "Filter by FY (optional)",
            options=fy_options,
            index=0
        )
    
    # Submit button
    if st.button("🔍 Get Answer", type="primary", use_container_width=True):
        if not question.strip():
            st.error("Please enter a question.")
            return
            
        # Rate limiting: Max 10 queries per minute per session
        now = time.time()
        if "rate_limit" not in st.session_state:
            st.session_state["rate_limit"] = []
            
        # Clean old timestamps
        st.session_state["rate_limit"] = [ts for ts in st.session_state["rate_limit"] if now - ts < 60]
        
        if len(st.session_state["rate_limit"]) >= 10:
            st.error("⏳ Rate limit exceeded. Please wait a minute before asking more questions.")
            return
            
        st.session_state["rate_limit"].append(now)
        
        # Check if this is a definition command
        def_result = _process_definition_command(question)
        if def_result:
            if def_result["success"]:
                st.success(def_result["message"])
            else:
                st.error(def_result["message"])
            return
        
        # Build filters
        filters = {}
        if company_filter:
            if len(company_filter) == 1:
                filters["company_code"] = company_filter[0]
            else:
                filters["company_code"] = {"$in": company_filter}
        
        if quarter_filter != "All":
            filters["quarter"] = quarter_filter
        
        if fy_filter != "All":
            filters["fy"] = fy_filter
        
        # Get answer
        with st.spinner("🤔 Thinking..."):
            try:
                result = answer_question(
                    question,
                    filters=filters if filters else None,
                    free_model=st.session_state.get("free_model"),
                    paid_model=st.session_state.get("paid_model"),
                )
                
                # Display answer
                st.markdown("### 📝 Answer")
                
                # Confidence badge
                confidence = result['confidence']
                if confidence == 'high':
                    badge_class = 'confidence-high'
                    badge_text = '✓ High Confidence'
                elif confidence == 'medium':
                    badge_class = 'confidence-medium'
                    badge_text = '⚠ Medium Confidence'
                else:
                    badge_class = 'confidence-low'
                    badge_text = '✗ No Data'

                model_used = result.get('model_used', '')
                model_tier = 'paid' if 'free' not in model_used.lower() else 'free'

                col_badge, col_model = st.columns([2, 1])
                with col_badge:
                    st.markdown(f'<span class="{badge_class}">{badge_text}</span>', unsafe_allow_html=True)
                with col_model:
                    # Visual Model Badge - Enhanced with colored badge
                    if model_tier == 'free':
                        st.success("🟢 Free Model")
                    else:
                        st.info("🔵 Paid Model")
                
                st.caption(f"Model: `{model_used}`")
                st.markdown("")
                
                # Answer text
                st.markdown(result['answer'])
                
                # Enhanced Copy Button with JavaScript clipboard API
                st.markdown("")  # Add spacing
                
                # Escape answer text for JavaScript
                answer_json = json.dumps(result['answer'])
                
                # Create copy button with inline JavaScript
                copy_button_html = f"""
                <div style="margin: 10px 0;">
                    <button onclick="copyToClipboard()" style="
                        background-color: var(--secondary-background-color, #f0f2f6);
                        border: 1px solid var(--border-color, #d0d0d0);
                        border-radius: 4px;
                        padding: 8px 16px;
                        cursor: pointer;
                        font-size: 14px;
                        font-weight: 500;
                        color: var(--text-color, #262730);
                        display: inline-flex;
                        align-items: center;
                        gap: 6px;
                    ">
                        📋 Copy Answer
                    </button>
                    <span id="copy-feedback" style="
                        margin-left: 10px;
                        color: #28a745;
                        font-weight: 500;
                        display: none;
                    ">✓ Copied to clipboard!</span>
                </div>
                <script>
                    function copyToClipboard() {{
                        const text = {answer_json};
                        navigator.clipboard.writeText(text).then(function() {{
                            const feedback = document.getElementById('copy-feedback');
                            feedback.style.display = 'inline';
                            setTimeout(function() {{
                                feedback.style.display = 'none';
                            }}, 3000);
                        }}, function(err) {{
                            alert('Failed to copy. Please use the text box below to copy manually.');
                        }});
                    }}
                </script>
                """
                st.components.v1.html(copy_button_html, height=50)
                
                # Fallback: Provide code block for manual copy
                with st.expander("📄 View as Plain Text (Manual Copy)"):
                    st.code(result['answer'], language=None)
                
                # Export Download Button
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                st.download_button(
                    label="📥 Download Answer as Markdown",
                    data=f"# Question: {question}\n\n## Answer\n{result['answer']}\n\n## Sources\n" + "\n".join([f"- {s}" for s in result.get('sources', [])]),
                    file_name=f"RAG_Answer_{timestamp}.md",
                    mime="text/markdown",
                )
                
                # Sources
                if result['sources']:
                    st.markdown("---")
                    st.markdown("**📚 Sources:**")
                    for source in result['sources']:
                        st.markdown(f"- {source}")

                # Metadata
                with st.expander("ℹ️ Query Details"):
                    st.write(f"**Chunks Used:** {result['chunks_used']}")
                    st.write(f"**Confidence:** {result['confidence']}")
                    st.write(f"**Model Used:** {result.get('model_used', 'N/A')}")
                    if filters:
                        st.write(f"**Filters Applied:** {filters}")
                
                # Save to history
                if "query_history" not in st.session_state:
                    st.session_state["query_history"] = []
                st.session_state["query_history"].insert(0, {
                    "question": question,
                    "result": result,
                    "filters": filters,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
            
            except Exception as e:
                logger.exception("[UI] answer_question failed | question=%r | filters=%s", question[:100], filters)
                st.error(f"Error: {str(e)}")
                st.exception(e)



def _process_definition_command(text: str) -> Optional[Dict[str, Any]]:
    """
    Process definition commands from chat.
    
    Supported patterns:
    - "define GWP as L-4"
    - "add definition: Premium Schedule = L-5"
    - "define Margin % = Margin / ANP"
    - "what is GWP?"
    
    Returns:
        Dict with success and message, or None if not a definition command
    """
    import re
    
    text_lower = text.lower().strip()
    
    # Pattern 1: "define X as L-Y" or "add definition: X = L-Y"
    page_pattern1 = re.compile(r'(?:define|add definition:?)\s+(.+?)\s+(?:as|=)\s+(l-\d+)', re.IGNORECASE)
    match = page_pattern1.search(text)
    if match:
        term = match.group(1).strip()
        lpage = match.group(2).strip().upper()
        success, message = add_page_definition(term, lpage)
        return {"success": success, "message": message}
    
    # Pattern 2: "define X = formula" (calculation)
    calc_pattern = re.compile(r'(?:define|add calculation:?)\s+(.+?)\s*=\s*(.+)', re.IGNORECASE)
    match = calc_pattern.search(text)
    if match:
        # Check if it's not an L-page definition
        if not match.group(2).strip().upper().startswith('L-'):
            calc_name = match.group(1).strip()
            formula = match.group(2).strip()
            success, message = add_calculation(calc_name, formula)
            return {"success": success, "message": message}
    
    # Pattern 3: "what is X?" or "define X" (search)
    search_pattern = re.compile(r'(?:what is|define)\s+(.+?)[\?]?$', re.IGNORECASE)
    match = search_pattern.search(text)
    if match and len(text.split()) <= 5:  # Only for short queries
        term = match.group(1).strip()
        result = search_definitions(term)
        
        if result["found"]:
            msg_parts = [f"**{term}**"]
            if result["type"] in ["page", "both"]:
                msg_parts.append(f"📄 Page: {result['lpage']}")
                if result["related_terms"]:
                    msg_parts.append(f"Related: {', '.join(result['related_terms'])}")
            if result["type"] in ["calculation", "both"]:
                msg_parts.append(f"🧮 Formula: {result['formula']}")
            
            return {"success": True, "message": "\n".join(msg_parts)}
        else:
            return {"success": False, "message": f"No definition found for '{term}'"}
    
    return None



