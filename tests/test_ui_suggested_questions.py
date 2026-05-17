from streamlit.testing.v1 import AppTest


def test_suggested_question_click_autofills_text_area():
    at = AppTest.from_string(
        """
import src.ui.ask as ask

ask.invalidate_metadata_cache = lambda: None
ask.get_collection_stats = lambda: {"total_chunks": 1, "unique_files": 1, "chunks_by_company": {"X": 1}}
ask.get_indexed_companies = lambda: ["ICICI"]
ask.get_available_quarters = lambda: ["Q3"]
ask.get_available_fys = lambda: ["FY26"]

ask.render_tab_ask_question()
"""
    )

    at.run(timeout=20)
    assert at.text_area(key="ask_question_input_widget").value == ""

    at.button(key="suggestion_comparison_btn").click().run(timeout=20)
    value = at.text_area(key="ask_question_input_widget").value
    assert value.startswith("List company-wise premium")
