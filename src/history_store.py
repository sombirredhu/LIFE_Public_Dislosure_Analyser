import json
from pathlib import Path
from typing import Any, Dict, List


_HISTORY_FILE = Path(__file__).resolve().parent.parent / "logs" / "query_history.jsonl"


def append_history_entry(entry: Dict[str, Any]) -> None:
    _HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load_history_entries(limit: int = 200) -> List[Dict[str, Any]]:
    if not _HISTORY_FILE.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with open(_HISTORY_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return list(reversed(rows[-limit:]))

