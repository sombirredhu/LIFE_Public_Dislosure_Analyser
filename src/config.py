import os
import logging
from pathlib import Path
from dotenv import load_dotenv

for lib in ['pdfminer', 'pdfplumber', 'PIL', 'matplotlib', 'urllib3', 'chromadb']:
    logging.getLogger(lib).setLevel(logging.WARNING)

project_root = Path(__file__).parent.parent
load_dotenv(project_root / ".env")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
LLM_MODEL_FREE = os.getenv("LLM_MODEL_FREE", "openrouter/free")
LLM_MODEL_PAID = os.getenv("LLM_MODEL_PAID", "anthropic/claude-sonnet-4-5")
LLM_MAX_TOKENS_SIMPLE = int(os.getenv("LLM_MAX_TOKENS_SIMPLE", "1024"))
LLM_MAX_TOKENS_COMPLEX = int(os.getenv("LLM_MAX_TOKENS_COMPLEX", "4096"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
LLM_MAX_INPUT_CHARS = int(os.getenv("LLM_MAX_INPUT_CHARS", "120000"))

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "openai/text-embedding-3-small")
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "1536"))
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "64"))

CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./vectordb/chroma_db")
CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "insurance_pd_reports")
if not os.path.isabs(CHROMA_DB_PATH): CHROMA_DB_PATH = str(project_root / CHROMA_DB_PATH)

PAGE_WISE_CHUNKING = os.getenv("PAGE_WISE_CHUNKING", "True").lower() == "true"
MAX_PAGE_TOKENS = int(os.getenv("MAX_PAGE_TOKENS", "8000"))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1200"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))
MIN_CHUNK_SIZE = int(os.getenv("MIN_CHUNK_SIZE", "100"))

TOP_K_SIMPLE = int(os.getenv("TOP_K_SIMPLE", "12"))
TOP_K_COMPLEX = int(os.getenv("TOP_K_COMPLEX", "40"))
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.20"))

PDF_INPUT_DIR = os.getenv("PDF_INPUT_DIR", "./data/pdfs")
PROCESSED_OUTPUT_DIR = os.getenv("PROCESSED_OUTPUT_DIR", "./data/processed")
if not os.path.isabs(PDF_INPUT_DIR): PDF_INPUT_DIR = str(project_root / PDF_INPUT_DIR)
if not os.path.isabs(PROCESSED_OUTPUT_DIR): PROCESSED_OUTPUT_DIR = str(project_root / PROCESSED_OUTPUT_DIR)

APP_TITLE = os.getenv("APP_TITLE", "Insurance PD Report Analyzer")
APP_PORT = int(os.getenv("APP_PORT", "8501"))
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))

def validate_config():
    if not OPENROUTER_API_KEY: raise ValueError("OPENROUTER_API_KEY is not set")
    os.makedirs(PDF_INPUT_DIR, exist_ok=True)
    os.makedirs(PROCESSED_OUTPUT_DIR, exist_ok=True)
    return True
