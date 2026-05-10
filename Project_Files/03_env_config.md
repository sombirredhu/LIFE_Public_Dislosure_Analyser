# 3. .env Configuration File

Every setting lives here. No API keys or paths hardcoded anywhere in the code. Copy `.env.example` to `.env`, fill in your values, and the system is ready.

```env
# ─────────────────────────────────────────
# OPENROUTER API
# ─────────────────────────────────────────
OPENROUTER_API_KEY=sk-or-xxxxxxxxxxxxxxxxxxxxxxxx
# OpenRouter base URL — do not change
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# ——— FREE MODEL (used by default for most queries) ———
# Used for: single-company lookups, single-metric questions, simple factual Q&A
# Free on OpenRouter (rate-limited) — no cost for routine queries
LLM_MODEL_FREE=anthropic/claude-3-haiku:free

# ——— PAID MODEL (used only when complexity warrants it) ———
# Used for: multi-company comparisons, multi-quarter trends, ambiguous queries,
#           channel-wise aggregations across all companies
# Only triggered when query_complexity = "high" in rag_pipeline.py
# IMPORTANT: Verify the exact slug at https://openrouter.ai/models before use.
# Slug format example: anthropic/claude-sonnet-4-5 (OpenRouter adds minor version suffix)
LLM_MODEL_PAID=anthropic/claude-sonnet-4-5

LLM_MAX_TOKENS_SIMPLE=1024   # single-company / single-metric queries — keeps free model lean
LLM_MAX_TOKENS_COMPLEX=4096  # multi-company / multi-quarter queries — prevents table truncation
LLM_TEMPERATURE=0.2

# Input context guard — rag_pipeline truncates chunk list if total input chars exceed this
# ~30,000 tokens at ~4 chars/token — safe for all OpenRouter models (most support 32K+)
# Prevents silent context overflow when top_up adds extra chunks for 27-company queries
LLM_MAX_INPUT_CHARS=120000

# ─────────────────────────────────────────
# EMBEDDING MODEL
# ─────────────────────────────────────────
# Options: sentence-transformers/all-MiniLM-L6-v2 (free, local)
#          text-embedding-3-small (OpenAI, paid)
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384

# ─────────────────────────────────────────
# VECTOR DATABASE
# ─────────────────────────────────────────
CHROMA_DB_PATH=./vectordb/chroma_db
CHROMA_COLLECTION_NAME=insurance_pd_reports

# ─────────────────────────────────────────
# CHUNKING SETTINGS
# ─────────────────────────────────────────
CHUNK_SIZE=1200         # characters per chunk — raised from 800; financial tables need more space
CHUNK_OVERLAP=150       # overlap between consecutive chunks
MIN_CHUNK_SIZE=100      # discard chunks smaller than this

# ─────────────────────────────────────────
# RETRIEVAL SETTINGS
# ─────────────────────────────────────────
TOP_K_SIMPLE=8          # chunks retrieved for single-company / single-metric queries
TOP_K_COMPLEX=30        # chunks retrieved for cross-company / multi-quarter queries
SIMILARITY_THRESHOLD=0.4 # minimum similarity score to include chunk (raised from 0.3)

# ─────────────────────────────────────────
# PDF PROCESSING
# ─────────────────────────────────────────
PDF_INPUT_DIR=./data/pdfs
PROCESSED_OUTPUT_DIR=./data/processed

# ─────────────────────────────────────────
# COMPANY METADATA
# ─────────────────────────────────────────
# No whitelist required. Company code is inferred directly from the filename.
# Any well-formed filename is accepted: {COMPANY_CODE}_{QUARTER}_{FY}.pdf
# Examples: HDFC_Life_Q1_FY25.pdf, Canara_HSBC_Q1_FY25.pdf, Edelweiss_Q2_FY26.pdf
# New companies are auto-registered on first ingest — no .env change needed.

# ─────────────────────────────────────────
# STREAMLIT APP
# ─────────────────────────────────────────
APP_TITLE=Insurance PD Report Analyzer
APP_PORT=8501
MAX_UPLOAD_SIZE_MB=50
```
