# 7. Module Descriptions

Each file has a single responsibility. No module does more than one thing.

---

## 7.1 `src/config.py`

Loads all settings from `.env` using `python-dotenv`. All other modules import from `config` — never directly from `.env`.

```python
# What it exposes:
OPENROUTER_API_KEY, OPENROUTER_BASE_URL
LLM_MODEL_FREE, LLM_MODEL_PAID
LLM_MAX_TOKENS_SIMPLE, LLM_MAX_TOKENS_COMPLEX, LLM_TEMPERATURE
LLM_MAX_INPUT_CHARS          # input context guard — added in Pass-2 fix
EMBEDDING_MODEL, EMBEDDING_DIMENSION
CHROMA_DB_PATH, CHROMA_COLLECTION_NAME
CHUNK_SIZE, CHUNK_OVERLAP, MIN_CHUNK_SIZE
TOP_K_SIMPLE, TOP_K_COMPLEX, SIMILARITY_THRESHOLD
PDF_INPUT_DIR, PROCESSED_OUTPUT_DIR
```

---

## 7.2 `src/pdf_parser.py`

Extracts text and tables from PD PDF files using `pdfplumber`. Handles both regular text paragraphs and structured tables. Uses the IRDAI PD report's own index page to map L-page labels to section names — no guessing needed.

```python
# Input:  path to PDF file
# Output: dict with pages, each page has text blocks + tables + section label
# Key functions:
#   parse_pdf(pdf_path) -> dict
#   extract_index_page(pdf_path) -> dict   e.g. {"L-1": "Revenue Account", "L-2": "Balance Sheet", ...}
#
# Section detection strategy (IRDAI PD reports use L-page labels):
#   Step 1 — Parse index page (usually page 1 or 2):
#             Scan for a table/list mapping L-1, L-2... to section names.
#             Save result as data/processed/{company_code}_page_definitions.json
#   Step 2 — For every subsequent page:
#             Read the page label from the top line (e.g. "L-5 : Analytical Ratios")
#             Look up label in the index map -> section name
#   Step 3 — Fallback (if index page missing or label not found):
#             Load from data/processed/page_definitions.json (user-provided master file)
#             If still not found, set section = "unknown"
#
# Table extraction strategy:
# 1. Use pdfplumber table detection on each page
# 2. Convert table rows to pipe-separated text: "Col1 | Col2 | Col3"
# 3. Prepend table with column headers for context
# 4. Fall back to raw text extraction if table detection fails
```

**Output format:**

```json
{
  "source_file": "HDFC_Life_Q1_FY25.pdf",
  "company_code": "HDFC_Life",
  "quarter": "Q1",
  "fy": "FY25",
  "total_pages": 18,
  "pages": [
    {
      "page_number": 1,
      "page_label": "L-1",
      "section": "Revenue Account",
      "text_blocks": ["Executive Summary...", "..."],
      "tables": [
        {
          "headers": ["Particulars", "Q1 FY25 (₹ Cr)", "Q1 FY24 (₹ Cr)"],
          "rows": [
            ["Gross Written Premium", "8432.15", "7891.23"],
            ["New Business Premium", "3241.50", "2987.10"]
          ],
          "raw_text": "Particulars | Q1 FY25 (₹ Cr) | Q1 FY24 (₹ Cr)\nGross Written Premium | 8432.15 | 7891.23"
        }
      ]
    }
  ]
}
```

---

## 7.3 `src/chunker.py`

Splits extracted page content into overlapping chunks of configurable size. Preserves table rows together — never splits a table row across two chunks. Attaches metadata to each chunk.

```python
# Input:  parsed PDF dict + company/quarter/fy metadata
# Output: list of chunk dicts, each with structure:
# {
#   "text":     "Gross Written Premium | 8432.15 | 7891.23\n...",  # chunk content
#   "metadata": { ...all fields from 06_chunk_metadata.md... }
# }
# Key function: chunk_document(parsed_doc, metadata) -> list[dict]
#   NOTE: 'text' and 'metadata' are the only top-level keys in a chunk dict.
#         All filtering/retrieval operates on 'metadata'; LLM receives 'text'.

# Chunking rules:
# - Tables: kept as single chunk if under CHUNK_SIZE
# - Long tables: split by row groups with header repeated in each chunk
# - Text: split at sentence boundary closest to CHUNK_SIZE
# - Always include page number and section heading in chunk
```

---

## 7.4 `src/embedder.py`

Creates vector embeddings for each chunk and stores in ChromaDB. Checks if file is already indexed before re-ingesting — prevents duplicate entries on re-upload.

```python
# Input:  list of chunks with metadata
# Output: chunks stored in ChromaDB
# Key functions:
#   get_or_create_collection() -> ChromaDB collection
#   embed_chunks(chunks) -> None  (stores to ChromaDB)
#   is_already_indexed(source_file) -> bool
#   delete_file_chunks(source_file) -> None  (for re-indexing)
#   get_indexed_companies() -> list[str]  (returns all unique company_codes in ChromaDB)
#     — used by top_up_missing_companies() in retriever.py to know who is missing
```

---

## 7.5 `src/retriever.py`

Searches ChromaDB for the most relevant chunks for a given query. Supports optional filtering by company, quarter, or FY. Implements hybrid dynamic TOP_K + source-span top-up to ensure no company is silently dropped from cross-company queries.

```python
# Key functions:
#   retrieve(query, filters=None, top_k=None) -> list[dict]
#   top_up_missing_companies(query, chunks, expected_companies, filters) -> list[dict]
#
# Each returned chunk dict has exactly 3 keys:
# {
#   "text":     str,    # chunk content (same as what chunker stored)
#   "metadata": dict,   # all metadata fields from 06_chunk_metadata.md
#   "score":    float   # similarity score (1 - distance) — retriever converts ChromaDB
#                       # 'distances' to 'score' so callers always get 0.0-1.0 range
# }
#
# Dynamic TOP_K scaling (set in rag_pipeline based on complexity):
#   simple query   → top_k = TOP_K_SIMPLE   (default: 8)
#   complex query  → top_k = TOP_K_COMPLEX  (default: 30)
#
# Source-span top-up (runs after initial retrieve on complex queries):
#   1. Check which companies from the indexed list are missing from retrieved chunks
#   2. Fetch all missing companies IN PARALLEL using concurrent.futures.ThreadPoolExecutor:
#      with ThreadPoolExecutor(max_workers=8) as pool:
#          futures = {pool.submit(retrieve, query, {"company_code": co}, 2): co
#                     for co in missing_companies}
#   3. Merge top-up results into main chunk list
#   This guarantees every indexed company is represented in the LLM context
#   NOTE: parallel top-up reduces worst-case latency from O(27) → O(ceil(27/8)) sequential calls
#
# Filter examples:
# filters = {"company_code": "HDFC_Life"}
# filters = {"quarter": "Q1", "fy": "FY25"}
# filters = {"company_code": {"$in": ["HDFC_Life", "SBI_Life"]}}
```

---

## 7.6 `src/llm_client.py`

Simple wrapper around OpenRouter API using the `openai` SDK. Supports two-tier model routing — uses the free model by default and escalates to the paid model only when explicitly requested.

```python
# Key function: ask_llm(system_prompt, user_message, use_paid=False) -> str
#
# use_paid=False  →  model=LLM_MODEL_FREE,  max_tokens=LLM_MAX_TOKENS_SIMPLE  (1024)
# use_paid=True   →  model=LLM_MODEL_PAID,  max_tokens=LLM_MAX_TOKENS_COMPLEX (4096)
#
# Uses: openai.OpenAI(base_url=OPENROUTER_BASE_URL, api_key=OPENROUTER_API_KEY)
# Retries: 3 attempts with exponential backoff
# Timeout: 30 seconds per request
# Checks finish_reason == 'length' after every call — logs a warning if truncated
# Logs model + tokens used on every call (for cost tracking)
```

---

## 7.7 `src/rag_pipeline.py`

Orchestrates the full RAG flow: takes user question → classifies complexity → retrieves relevant chunks → builds prompt → calls OpenRouter API (free or paid model) → returns answer with source references.

```python
# Key function: answer_question(question, filters=None) -> dict
#
# Internally calls classify_complexity(question) -> "simple" | "complex"
# "simple"  → ask_llm(..., use_paid=False)   free model, zero cost
# "complex" → ask_llm(..., use_paid=True)    paid model, only when needed
#
# classify_complexity() rules (pure keyword/heuristic — no LLM call, runs BEFORE retrieval):
#
#   ALWAYS COMPLEX (even if one company named):
#     "compare", "vs", "versus", "all companies", "all quarters",
#     "industry total", "channel-wise", "rank", "ranking", "which company"
#
#   COMPLEX only when NO single company is explicitly named:
#     "highest", "lowest", "top", "bottom", "best", "worst", "most", "least", "trend"
#     e.g. "highest GWP in Q1 FY25?"   → COMPLEX (no company named)
#          "HDFC Life highest GWP?"     → SIMPLE  (one company named, superlative is scoped)
#
#   SIMPLE: exactly ONE company named AND none of the always-complex keywords present
#
#   NOTE: complexity is determined from the question text only — never from chunk results
#   NOTE: when in doubt, default to COMPLEX — cost of extra retrieval < cost of wrong answer
#
# Retrieval strategy based on complexity:
#   simple  → retrieve(query, top_k=TOP_K_SIMPLE)   — no top-up
#   complex → retrieve(query, top_k=TOP_K_COMPLEX)
#             indexed = embedder.get_indexed_companies()  — who is in ChromaDB?
#             + top_up_missing_companies(query, chunks, indexed, filters)
#
# Input token budget guard (runs after retrieval, before LLM call):
#   total_chars = sum(len(c['text']) for c in chunks)
#   if total_chars > LLM_MAX_INPUT_CHARS:
#       chunks = chunks[:LLM_MAX_INPUT_CHARS // avg_chunk_size]  # drop lowest-score chunks
#       log warning: "Input truncated: {total_chars} chars exceeded {LLM_MAX_INPUT_CHARS} limit"

# Returns: dict
# {
#   "answer":      "HDFC Life had the highest GWP of ₹8,432 Cr in Q1 FY25...",
#   "sources":     ["HDFC_Life_Q1_FY25.pdf p.4", "LIC_Q1_FY25.pdf p.7"],
#   "chunks_used": 6,
#   "confidence":  "high",   # high / medium / none — see 08_system_prompt.md for scale
#   "model_used":  "anthropic/claude-3-haiku:free"  # logged for cost visibility
# }
```

---

## 7.8 `src/ingestor.py`

End-to-end pipeline: takes a PDF file path → parses → chunks → embeds → stores. Called by both the Streamlit UI (on upload) and the batch script.

```python
# Key function: ingest_pdf(pdf_path) -> dict
#
# period_label derivation (called during metadata build, before chunking):
#   FY suffix → fiscal year mapping rule:
#     "FY25" → last two digits = 25 → fiscal year = "FY2024-25"
#     "FY26" → "FY2025-26"
#     Formula: f"FY20{int(fy[2:])-1}-{fy[2:]}"   e.g. FY25 → "FY2024-25"
#   Combined with quarter: period_label = f"{quarter} FY20{int(fy[2:])-1}-{fy[2:]}"
#     e.g. Q1 + FY25 → "Q1 FY2024-25"

# Returns: dict
# {
#   "source_file":           "HDFC_Life_Q1_FY25.pdf",
#   "status":                "success",
#   "pages_processed":       18,
#   "chunks_created":        142,
#   "already_indexed":       False,
#   "page_definitions_found": True,   # False if index page missing (section = "unknown")
#   "duration_seconds":      12.4
# }
```
