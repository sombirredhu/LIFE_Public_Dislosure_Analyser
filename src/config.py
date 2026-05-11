"""
Configuration module - loads all settings from .env file.
All other modules import settings from here.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Disable verbose logging from third-party libraries (causes massive slowdown)
logging.getLogger('pdfminer').setLevel(logging.WARNING)
logging.getLogger('pdfplumber').setLevel(logging.WARNING)
logging.getLogger('PIL').setLevel(logging.WARNING)
logging.getLogger('matplotlib').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('chromadb').setLevel(logging.WARNING)
logging.getLogger('sentence_transformers').setLevel(logging.WARNING)
logging.getLogger('transformers').setLevel(logging.WARNING)
logging.getLogger('torch').setLevel(logging.WARNING)

# Load .env file from project root
project_root = Path(__file__).parent.parent
env_path = project_root / ".env"
load_dotenv(env_path)

# ─────────────────────────────────────────
# OPENROUTER API
# ─────────────────────────────────────────
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
LLM_MODEL_FREE = os.getenv("LLM_MODEL_FREE", "openrouter/free")
LLM_MODEL_PAID = os.getenv("LLM_MODEL_PAID", "anthropic/claude-sonnet-4-5")
LLM_MAX_TOKENS_SIMPLE = int(os.getenv("LLM_MAX_TOKENS_SIMPLE", "1024"))
LLM_MAX_TOKENS_COMPLEX = int(os.getenv("LLM_MAX_TOKENS_COMPLEX", "4096"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
LLM_MAX_INPUT_CHARS = int(os.getenv("LLM_MAX_INPUT_CHARS", "120000"))

# ─────────────────────────────────────────
# EMBEDDING MODEL
# ─────────────────────────────────────────
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "384"))

# ─────────────────────────────────────────
# VECTOR DATABASE
# ─────────────────────────────────────────
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./vectordb/chroma_db")
CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "insurance_pd_reports")

# Convert to absolute path
if not os.path.isabs(CHROMA_DB_PATH):
    CHROMA_DB_PATH = str(project_root / CHROMA_DB_PATH)

# ─────────────────────────────────────────
# CHUNKING SETTINGS
# ─────────────────────────────────────────
# Page-wise chunking (new strategy)
PAGE_WISE_CHUNKING = os.getenv("PAGE_WISE_CHUNKING", "True").lower() == "true"
MAX_PAGE_TOKENS = int(os.getenv("MAX_PAGE_TOKENS", "8000"))

# Legacy text-based chunking (fallback)
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1200"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))
MIN_CHUNK_SIZE = int(os.getenv("MIN_CHUNK_SIZE", "100"))

# ─────────────────────────────────────────
# RETRIEVAL SETTINGS
# ─────────────────────────────────────────
TOP_K_SIMPLE = int(os.getenv("TOP_K_SIMPLE", "8"))
TOP_K_COMPLEX = int(os.getenv("TOP_K_COMPLEX", "30"))
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.4"))

# ─────────────────────────────────────────
# PDF PROCESSING
# ─────────────────────────────────────────
PDF_INPUT_DIR = os.getenv("PDF_INPUT_DIR", "./data/pdfs")
PROCESSED_OUTPUT_DIR = os.getenv("PROCESSED_OUTPUT_DIR", "./data/processed")

# Convert to absolute paths
if not os.path.isabs(PDF_INPUT_DIR):
    PDF_INPUT_DIR = str(project_root / PDF_INPUT_DIR)
if not os.path.isabs(PROCESSED_OUTPUT_DIR):
    PROCESSED_OUTPUT_DIR = str(project_root / PROCESSED_OUTPUT_DIR)

# ─────────────────────────────────────────
# STREAMLIT APP
# ─────────────────────────────────────────
APP_TITLE = os.getenv("APP_TITLE", "Insurance PD Report Analyzer")
APP_PORT = int(os.getenv("APP_PORT", "8501"))
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))


def validate_config():
    """Validate that all required settings are present."""
    errors = []

    if not OPENROUTER_API_KEY:
        errors.append("OPENROUTER_API_KEY is not set in .env file")

    if not os.path.exists(PDF_INPUT_DIR):
        os.makedirs(PDF_INPUT_DIR, exist_ok=True)

    if not os.path.exists(PROCESSED_OUTPUT_DIR):
        os.makedirs(PROCESSED_OUTPUT_DIR, exist_ok=True)

    if errors:
        raise ValueError("Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors))

    return True


if __name__ == "__main__":
    print("Configuration loaded successfully!")
    print(f"\nFree Model:  {LLM_MODEL_FREE}")
    print(f"Paid Model:  {LLM_MODEL_PAID}")
    print(f"Embedding Model: {EMBEDDING_MODEL}")
    print(f"ChromaDB Path: {CHROMA_DB_PATH}")
    print(f"PDF Input Dir: {PDF_INPUT_DIR}")
    print(f"Processed Output Dir: {PROCESSED_OUTPUT_DIR}")
    print(f"\nChunk Size: {CHUNK_SIZE}")
    print(f"TOP_K Simple: {TOP_K_SIMPLE}  |  TOP_K Complex: {TOP_K_COMPLEX}")
    print(f"Similarity Threshold: {SIMILARITY_THRESHOLD}")
    print(f"Max Input Chars: {LLM_MAX_INPUT_CHARS}")

    try:
        validate_config()
        print("\n✓ All required settings are present")
    except ValueError as e:
        print(f"\n✗ Configuration validation failed:\n{e}")
