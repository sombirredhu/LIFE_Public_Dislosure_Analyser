# 13. Recommended Build Order for Claude Code

Build in this exact sequence. Each module depends only on modules built before it. Verify each step before moving to the next.

---

## Build Sequence

| Step | File | Verify By |
|------|------|-----------|
| 1 | `src/config.py` | Print all loaded settings, confirm no missing keys |
| 2 | `src/pdf_parser.py` | Run on one PDF, print page count and first table |
| 3 | `src/chunker.py` | Print chunk count and first chunk with metadata |
| 4 | `src/embedder.py` | Check ChromaDB collection created, verify chunk count |
| 5 | `src/retriever.py` | Run a test query, print top 3 chunks with scores |
| 6 | `src/llm_client.py` | Ask "What is 2+2?" and verify OpenRouter responds |
| 7 | `src/rag_pipeline.py` | Ask a real question, verify answer + sources returned |
| 8 | `src/ingestor.py` | Ingest one PDF end-to-end, verify summary dict |
| 9 | `scripts/ingest_all.py` | Ingest all PDFs in data/pdfs/, verify counts |
| 10 | `tests/conftest.py` | Create shared pytest fixtures — seed a temp ChromaDB with 3-4 test chunks so retriever/truncation tests run without real PDFs |
| 11 | `tests/` | Run pytest suite — all 6 tests green (conftest fixtures provide ChromaDB; no live ingest required) |
| 12 | `scripts/test_query.py` | Run 3 example questions from 09_example_qa.md |
| 13 | `app/streamlit_app.py` | Full UI — all 3 tabs working |

---

## Verification Commands

```bash
# Step 1 — Config
python -c "from src.config import *; print(LLM_MODEL_FREE, LLM_MODEL_PAID, CHROMA_DB_PATH)"

# Step 2 — PDF Parser
python -c "
from src.pdf_parser import parse_pdf
result = parse_pdf('data/pdfs/HDFC_Life_Q1_FY25.pdf')
print(f'Pages: {result[\"total_pages\"]}')
print(f'First table: {result[\"pages\"][0][\"tables\"]}')
"

# Step 3 — Chunker
python -c "
from src.pdf_parser import parse_pdf
from src.chunker import chunk_document
parsed = parse_pdf('data/pdfs/HDFC_Life_Q1_FY25.pdf')
chunks = chunk_document(parsed, {})
print(f'Chunks: {len(chunks)}')
print(f'First chunk metadata: {chunks[0][\"metadata\"]}')
"

# Step 4 — Embedder
python -c "
from src.embedder import get_or_create_collection
col = get_or_create_collection()
print(f'Collection: {col.name}, Count: {col.count()}')
"

# Step 5 — Retriever
python -c "
from src.retriever import retrieve
results = retrieve('gross written premium')
for r in results[:3]:
    print(r['metadata']['source_file'], r['score'])
"

# Step 6 — LLM Client
python -c "
from src.llm_client import ask_llm
response = ask_llm('You are a helpful assistant.', 'What is 2+2?')
print(response)
"

# Step 7 — RAG Pipeline
python -c "
from src.rag_pipeline import answer_question
result = answer_question('Which company had highest GWP in Q1 FY25?')
print(result['answer'])
print('Sources:', result['sources'])
"
```

---

```bash
# Step 11 — Tests (no real PDFs required — conftest.py seeds a temp ChromaDB)
pytest tests/ -v
# Expected: 6 passed
```

---

## Important Notes

> **Do not build the Streamlit UI until Step 11 is passing.** The UI is the last layer — all logic must work correctly from CLI first.

> **Each step should be verified with a print/assert test before moving to the next.** Do not skip verification steps.

> **If a step fails**, fix it completely before proceeding. Later steps depend on earlier ones being correct.

> **`tests/conftest.py` must not depend on real PDFs or a live OpenRouter key.** Use `unittest.mock.patch` for LLM calls and a temp ChromaDB directory (`tmp_path` fixture) for retriever/truncation tests. This makes the test suite runnable in CI without any secrets or data files.
