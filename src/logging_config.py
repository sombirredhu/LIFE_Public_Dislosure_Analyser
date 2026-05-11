"""
Centralized logging configuration.

Call setup_logging() once at application startup.
Produces three outputs:
  - Console       : INFO+  (keep terminal readable)
  - logs/app.log  : DEBUG+ (rolling 5 MB × 3 files — full trace)
  - logs/errors.log: ERROR+ (rolling 2 MB × 5 files — quick error scan)

Log format:
  2026-05-10 21:18:00 | INFO     | src.retriever:72 | Retrieved 5 chunks
"""

import logging
import logging.handlers
from pathlib import Path

_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"

_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: int = logging.DEBUG) -> None:
    """
    Configure root logger. Safe to call multiple times — no-op after first call.

    Args:
        level: Minimum level captured by file handlers (default DEBUG).
    """
    root = logging.getLogger()
    if root.handlers:
        return  # already configured — skip

    root.setLevel(level)
    fmt = logging.Formatter(_FORMAT, datefmt=_DATE_FMT)

    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    # ── Console: INFO and above ───────────────────────────────────────────────
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)
    root.addHandler(console)

    # ── logs/app.log: DEBUG and above, rolling 5 MB × 3 ─────────────────────
    app_fh = logging.handlers.RotatingFileHandler(
        _LOG_DIR / "app.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    app_fh.setLevel(logging.DEBUG)
    app_fh.setFormatter(fmt)
    root.addHandler(app_fh)

    # ── logs/errors.log: ERROR and above, rolling 2 MB × 5 ──────────────────
    err_fh = logging.handlers.RotatingFileHandler(
        _LOG_DIR / "errors.log",
        maxBytes=2 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    err_fh.setLevel(logging.ERROR)
    err_fh.setFormatter(fmt)
    root.addHandler(err_fh)

    # ── Silence noisy third-party libraries ──────────────────────────────────
    for lib in (
        "httpx", "httpcore", "urllib3",
        "chromadb", "chromadb.telemetry",
        "sentence_transformers", "transformers",
        "openai._base_client", "openai.http_client",
        # Streamlit's file watcher scans all transformers submodules and hits
        # ModuleNotFoundError for optional extras (e.g. torchvision for zoedepth).
        # This is harmless — suppress the noise.
        "streamlit.watcher.local_sources_watcher",
    ):
        logging.getLogger(lib).setLevel(logging.ERROR)

    logging.getLogger(__name__).info(
        "Logging initialised — app.log + errors.log in %s", _LOG_DIR
    )
