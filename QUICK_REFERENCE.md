# Quick Reference Guide

Fast reference for common commands and operations.

---

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Create config file
copy .env.example .env
# Then edit .env and add your ANTHROPIC_API_KEY
```

---

## Verification

```bash
# Check setup
python scripts/verify_setup.py
```

---

## Ingestion

```bash
# Ingest all PDFs from data/pdfs/
python scripts/ingest_all.py

# Force re-index all files
python scripts/ingest_all.py --force

# Ingest from custom directory
python scripts/ingest_all.py --dir /path/to/pdfs
```

---

## CLI Queries

```bash
# Basic query
python scripts/test_query.py --q "your question here"

# With company filter
python scripts/test_query.py --q "question" --company HDFC_Life

# With time filter
python scripts/test_query.py --q "question" --quarter Q1 --fy FY25

# Debug mode (show retrieved chunks)
python scripts/test_query.py --q "question" --debug

# Custom top-k
python scripts/test_query.py --q "question" --top-k 15
```

---

## Web UI

```bash
# Launch Streamlit app
streamlit run app/streamlit_app.py

# Custom port
streamlit run app/streamlit_app.py --server.port 8502
```

Opens at: `http://localhost:8501`

---

## File Naming Convention

**Format:** `{COMPANY_CODE}_{QUARTER}_{FY}.pdf`

**Examples:**
- `HDFC_Life_Q1_FY25.pdf`
- `SBI_Life_Q2_FY25.pdf`
- `LIC_Q3_FY25.pdf`

**Rules:**
- Underscores only (no spaces/hyphens)
- Quarter: Q1, Q2, Q3, Q4
- FY: FY25, FY26, etc.

---

## Company Codes

Default codes:
- `LIC` - Life Insurance Corporation
- `HDFC_Life` - HDFC Life
- `SBI_Life` - SBI Life
- `ICICI_Pru` - ICICI Prudential
- `Max_Life` - Max Life
- `Bajaj_Life` - Bajaj Allianz
- `Kotak_Life` - Kotak Mahindra
- `Tata_AIA` - Tata AIA

Add more in `.env`: `COMPANY_CODES=LIC,HDFC_Life,...`

---

## Example Questions

### Single Company
```
What was HDFC Life's gross written premium in Q1 FY25?
What was the claim settlement ratio for SBI Life?
Show LIC's persistency ratios
```

### Comparisons
```
Compare HDFC Life and SBI Life's new business premium
Which company had better persistency in Q1 FY25?
Compare claim settlement ratios across all companies
```

### Rankings
```
Which company had the highest GWP in Q1 FY25?
Rank all companies by new business premium
Show top 5 companies by total premium
```

### Trends
```
Show HDFC Life's GWP for all quarters in FY25
Compare Q1 vs Q2 performance for all companies
What was the quarter-over-quarter growth?
```

### Channel Analysis
```
Which channel contributed most to new business?
Compare agency vs bancassurance premium
Show channel-wise breakdown for HDFC Life
```

---

## Configuration (.env)

### Required
```env
ANTHROPIC_API_KEY=sk-ant-xxxxx
```

### Common Settings
```env
# Model
CLAUDE_MODEL=claude-sonnet-4-20250514
CLAUDE_MAX_TOKENS=2048
CLAUDE_TEMPERATURE=0.2

# Chunking
CHUNK_SIZE=800
CHUNK_OVERLAP=150
MIN_CHUNK_SIZE=100

# Retrieval
TOP_K_RESULTS=8
SIMILARITY_THRESHOLD=0.3
```

---

## Module Testing

```bash
# Test config
python src/config.py

# Test PDF parser
python src/pdf_parser.py data/pdfs/HDFC_Life_Q1_FY25.pdf

# Test chunker
python src/chunker.py data/processed/HDFC_Life_Q1_FY25.json

# Test embedder
python src/embedder.py data/processed/HDFC_Life_Q1_FY25.json

# Test retriever
python src/retriever.py "gross written premium"

# Test LLM client
python src/llm_client.py "What is 2+2?"

# Test RAG pipeline
python src/rag_pipeline.py "Which company had highest GWP?"

# Test ingestor
python src/ingestor.py data/pdfs/HDFC_Life_Q1_FY25.pdf
```

---

## ChromaDB Operations

```python
# Get collection stats
python -c "from src.embedder import get_collection_stats; import json; print(json.dumps(get_collection_stats(), indent=2))"

# Check if file is indexed
python -c "from src.embedder import is_already_indexed; print(is_already_indexed('HDFC_Life_Q1_FY25.pdf'))"

# Delete file from index
python -c "from src.embedder import delete_file_chunks; print(delete_file_chunks('HDFC_Life_Q1_FY25.pdf'))"
```

---

## Troubleshooting

### Check API Key
```bash
python -c "from src.config import ANTHROPIC_API_KEY; print('OK' if ANTHROPIC_API_KEY else 'NOT SET')"
```

### Check ChromaDB
```bash
python -c "from src.embedder import get_collection_stats; stats = get_collection_stats(); print(f'Chunks: {stats[\"total_chunks\"]}, Files: {stats[\"unique_files\"]}')"
```

### Check PDF Files
```bash
dir data\pdfs\*.pdf
```

### Clear All Data
```python
python -c "from src.embedder import get_or_create_collection; col = get_or_create_collection(); col.delete(where={}); print('Cleared')"
```

---

## Directory Structure

```
insurance_rag/
├── .env                    # Your config (create from .env.example)
├── data/
│   ├── pdfs/              # Put PDF files here
│   └── processed/         # Auto-generated JSON
├── vectordb/              # ChromaDB storage (auto-created)
├── src/                   # Source code
├── app/                   # Streamlit UI
└── scripts/               # Utility scripts
```

---

## Performance Tuning

### Faster Ingestion
- Increase `CHUNK_SIZE` (fewer chunks)
- Use SSD for `vectordb/`

### Better Answers
- Increase `TOP_K_RESULTS` (more context)
- Lower `SIMILARITY_THRESHOLD` (more chunks)
- Increase `CLAUDE_MAX_TOKENS` (longer answers)

### Cost Optimization
- Decrease `CLAUDE_MAX_TOKENS`
- Use filters to reduce context
- Lower `TOP_K_RESULTS`

---

## Keyboard Shortcuts (Streamlit)

- `Ctrl+R` - Rerun app
- `Ctrl+C` - Stop server (in terminal)
- `Ctrl+Shift+R` - Clear cache and rerun

---

## File Locations

| Item | Location |
|------|----------|
| Config | `.env` |
| PDFs | `data/pdfs/` |
| Processed JSON | `data/processed/` |
| ChromaDB | `vectordb/chroma_db/` |
| Logs | Console output |

---

## Common Errors

| Error | Solution |
|-------|----------|
| API key not set | Add to `.env` file |
| No PDF files | Add to `data/pdfs/` |
| Invalid filename | Follow naming convention |
| Module not found | Run `pip install -r requirements.txt` |
| No data in ChromaDB | Run `python scripts/ingest_all.py` |

---

## Quick Start (TL;DR)

```bash
# 1. Install
pip install -r requirements.txt

# 2. Configure
copy .env.example .env
# Edit .env, add ANTHROPIC_API_KEY

# 3. Add PDFs to data/pdfs/

# 4. Ingest
python scripts/ingest_all.py

# 5. Test
python scripts/test_query.py --q "test question"

# 6. Launch UI
streamlit run app/streamlit_app.py
```

---

## Documentation

| File | Description |
|------|-------------|
| `README.md` | Project overview |
| `SETUP_GUIDE.md` | Detailed setup instructions |
| `QUICK_REFERENCE.md` | This file |
| `Project_Files/` | Complete specifications |

---

**For detailed information, see `SETUP_GUIDE.md` or `Project_Files/` directory.**
