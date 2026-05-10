# 10. Streamlit App — Views & Features

The app has 3 tabs. Simple, functional, no unnecessary complexity.

---

## Tab 1: Ask a Question

| Element | Description |
|---------|-------------|
| Text input | Type any plain English question |
| Company filter | Multi-select dropdown — filter to specific companies |
| Quarter filter | Dropdown — Q1, Q2, Q3, Q4, or All |
| FY filter | Dropdown — FY25, FY26, or All |
| Submit button | Calls `rag_pipeline.answer_question()` |
| Answer display | Shows LLM response in a clean card |
| Sources list | Shows source PDF filenames and page numbers below answer |
| Copy button | Copies answer text to clipboard |
| Confidence badge | Shows `high`, `medium`, or `none` confidence indicator (`none` = no relevant chunks found) |
| Model badge | Shows which model answered — `free` or `paid` — for cost awareness |

---

## Tab 2: Upload Reports

| Element | Description |
|---------|-------------|
| File uploader | Accepts PDF files — single or multiple at once |
| Filename validator | Checks naming convention before accepting |
| Progress bar | Shows ingestion progress (pages and chunks) |
| Ingestion summary | Pages processed, chunks created, time taken, status |
| Indexed files list | Table of all currently indexed files with metadata |
| Delete button | Remove a specific file from the index |

**Indexed files table columns:**

| Company | Quarter | FY | Chunks | Pages | Ingested At | Actions |
|---------|---------|----|--------|-------|-------------|---------|
| HDFC Life | Q1 | FY25 | 142 | 18 | 2025-05-10 14:32 | Delete |
| SBI Life | Q1 | FY25 | 138 | 17 | 2025-05-10 14:45 | Delete |

---

## Tab 3: Index Status

| Element | Description |
|---------|-------------|
| Summary stats | Total companies, quarters, chunks in ChromaDB |
| Coverage matrix | Table showing which company × quarter combinations are indexed |
| Re-index button | Re-process a specific file (use if PDF was updated) |
| Clear all button | Wipe ChromaDB completely — shows a **confirmation dialog** before executing: "This will delete all indexed data. Type CONFIRM to proceed." |

**Coverage matrix example:**

| Company | Q1 FY25 | Q2 FY25 | Q3 FY25 | Q4 FY25 |
|---------|---------|---------|---------|---------|
| LIC | ✅ | ✅ | ❌ | ❌ |
| HDFC Life | ✅ | ✅ | ✅ | ❌ |
| SBI Life | ✅ | ❌ | ❌ | ❌ |
| ICICI Pru | ✅ | ✅ | ❌ | ❌ |

---

## App Config

Streamlit server settings **must** be in `.streamlit/config.toml` — environment variables alone do not configure the Streamlit server:

```toml
# .streamlit/config.toml
[server]
port = 8501
maxUploadSize = 50   # MB — this is what actually enforces the upload limit
enableCORS = false

[theme]
base = "light"
```

The `.env` variables `APP_TITLE`, `APP_PORT`, and `MAX_UPLOAD_SIZE_MB` are used inside `streamlit_app.py` for display text and validation only — they do NOT override Streamlit server behavior on their own.

---

## Run Command

```bash
streamlit run app/streamlit_app.py
# Opens at http://localhost:8501
```
