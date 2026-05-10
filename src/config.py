"""
Configuration module - loads all settings from .env file.
All other modules import settings from here.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
project_root = Path(__file__).parent.parent
env_path = project_root / ".env"
load_dotenv(env_path)

# ─────────────────────────────────────────
# CLAUDE API
# ─────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
CLAUDE_MAX_TOKENS = int(os.getenv("CLAUDE_MAX_TOKENS", "2048"))
CLAUDE_TEMPERATURE = float(os.getenv("CLAUDE_TEMPERATURE", "0.2"))

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
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))
MIN_CHUNK_SIZE = int(os.getenv("MIN_CHUNK_SIZE", "100"))

# ─────────────────────────────────────────
# RETRIEVAL SETTINGS
# ─────────────────────────────────────────
TOP_K_RESULTS = int(os.getenv("TOP_K_RESULTS", "8"))
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.3"))

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
# COMPANY METADATA
# ─────────────────────────────────────────
COMPANY_CODES = os.getenv("COMPANY_CODES", "LIC,HDFC_Life,SBI_Life,ICICI_Pru,Max_Life,Bajaj_Life,Kotak_Life,Tata_AIA")
COMPANY_CODES = [code.strip() for code in COMPANY_CODES.split(",")]

# ─────────────────────────────────────────
# STREAMLIT APP
# ─────────────────────────────────────────
APP_TITLE = os.getenv("APP_TITLE", "Insurance PD Report Analyzer")
APP_PORT = int(os.getenv("APP_PORT", "8501"))
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))


def validate_config():
    """Validate that all required settings are present."""
    errors = []
    
    if not ANTHROPIC_API_KEY:
        errors.append("ANTHROPIC_API_KEY is not set in .env file")
    
    if not os.path.exists(PDF_INPUT_DIR):
        os.makedirs(PDF_INPUT_DIR, exist_ok=True)
    
    if not os.path.exists(PROCESSED_OUTPUT_DIR):
        os.makedirs(PROCESSED_OUTPUT_DIR, exist_ok=True)
    
    if errors:
        raise ValueError(f"Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors))
    
    return True


if __name__ == "__main__":
    # Test configuration loading
    print("Configuration loaded successfully!")
    print(f"\nClaude Model: {CLAUDE_MODEL}")
    print(f"Embedding Model: {EMBEDDING_MODEL}")
    print(f"ChromaDB Path: {CHROMA_DB_PATH}")
    print(f"PDF Input Dir: {PDF_INPUT_DIR}")
    print(f"Processed Output Dir: {PROCESSED_OUTPUT_DIR}")
    print(f"Company Codes: {', '.join(COMPANY_CODES)}")
    print(f"\nChunk Size: {CHUNK_SIZE}")
    print(f"Top K Results: {TOP_K_RESULTS}")
    print(f"Similarity Threshold: {SIMILARITY_THRESHOLD}")
    
    try:
        validate_config()
        print("\n✓ All required settings are present")
    except ValueError as e:
        print(f"\n✗ Configuration validation failed:\n{e}")
