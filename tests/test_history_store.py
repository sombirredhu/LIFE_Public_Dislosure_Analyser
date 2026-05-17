from pathlib import Path

from src import history_store


def test_append_and_load_history_entries(tmp_path, monkeypatch):
    history_file = tmp_path / "query_history.jsonl"
    monkeypatch.setattr(history_store, "_HISTORY_FILE", history_file)

    history_store.append_history_entry({"question": "Q1", "timestamp": "2026-01-01 10:00:00", "result": {"answer": "A1"}})
    history_store.append_history_entry({"question": "Q2", "timestamp": "2026-01-01 10:01:00", "result": {"answer": "A2"}})

    rows = history_store.load_history_entries(limit=10)
    assert len(rows) == 2
    assert rows[0]["question"] == "Q2"
    assert rows[1]["question"] == "Q1"


def test_load_history_skips_invalid_lines(tmp_path, monkeypatch):
    history_file = tmp_path / "query_history.jsonl"
    monkeypatch.setattr(history_store, "_HISTORY_FILE", history_file)
    history_file.parent.mkdir(parents=True, exist_ok=True)
    history_file.write_text('{"ok": 1}\nnot-json\n{"ok": 2}\n', encoding="utf-8")

    rows = history_store.load_history_entries(limit=10)
    assert len(rows) == 2
    assert rows[0]["ok"] == 2
    assert rows[1]["ok"] == 1

