# 14. Known Limitations & Handling

---

## Limitation Table

| Limitation | How It's Handled |
|------------|-----------------|
| No index page in some PDFs | Parser falls back to `data/processed/page_definitions.json` (user-provided master map). If that's also missing, section = "unknown" and a warning is logged |
| Tables with merged cells | pdfplumber handles most cases; complex merges stored as raw text with a warning logged |
| Scanned pages in mostly-text PDF | Page is skipped if no text extracted; warning logged with page number |
| Same file uploaded twice | `embedder.py` checks `is_already_indexed()` — skips without re-ingesting |
| Very large PDFs (50+ pages) | Chunked progressively page by page; progress bar shown in UI |
| Numbers in different formats | System prompt instructs the LLM to normalize all values to ₹ Crore |
| Missing data for a company/quarter | LLM instructed in system prompt to state clearly when data is not in context |
| New company not seen before | Auto-registered from filename on first ingest — no action needed |
| Wrong filename format | File rejected at upload with format example shown |
| ChromaDB corruption | Clear all button in Tab 3 **wipes ChromaDB only** — PDFs in `data/pdfs/` are untouched; re-run `python scripts/ingest_all.py` to rebuild the index |

---

## PDF Parsing Edge Cases

### Tables with merged cells
```
# pdfplumber may return None for merged cells
# chunker.py handles this:
row_text = " | ".join(cell if cell else "" for cell in row)
```

### Pages with no extractable text
```python
# pdf_parser.py skips empty pages:
if not page_text.strip() and not page_tables:
    print(f"Warning: No content extracted from page {page_num}")
    continue
```

### Very wide tables (truncated in PDF)
```
# If table columns are cut off, pdfplumber may miss rightmost columns
# These are stored as raw text with a note: "[TABLE MAY BE INCOMPLETE]"
```

---

## Query Edge Cases

### Question spans multiple quarters not yet indexed
```
Answer: "Data for Q3 FY25 is not available for HDFC Life. 
Only Q1 and Q2 FY25 are currently indexed."
```

### Question asks for data not in PD reports
```
Answer: "VNB margin is typically disclosed in embedded value reports, 
not IRDAI Public Disclosure reports. This data is not available."
```

### Ambiguous company name in question
```
# "SBI" could mean SBI Life or State Bank of India
# System prompt instructs the LLM to ask for clarification
Answer: "Did you mean SBI Life Insurance? Please confirm."
```

---

## Performance Notes

| Operation | Expected Time | Notes |
|-----------|--------------|-------|
| Ingest one PDF (18 pages) | 10-15 seconds | Embedding is local, no API calls |
| Ingest 27 companies × 4 quarters | ~20-30 minutes total | Sequential; parallelisable later |
| Simple query (single company, free model) | 4-10 seconds | 1 ChromaDB call + OpenRouter latency |
| Complex query (cross-company, paid model) | 8-20 seconds | TOP_K_COMPLEX fetch + parallel top-up (ThreadPoolExecutor, 8 workers) + paid model latency |
| Streamlit UI load | 2-3 seconds | |
| ChromaDB similarity search | < 1 second | Local, no network |
