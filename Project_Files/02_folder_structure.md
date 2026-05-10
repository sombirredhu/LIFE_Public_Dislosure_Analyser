# 2. Project Folder Structure

All modules are single-purpose Python files. Configuration is entirely in `.env`. No hardcoded values anywhere in the codebase.

```
insurance_rag/
├── .env                          # All config — API keys, paths, model settings
├── .env.example                  # Template — copy to .env and fill in
├── requirements.txt              # All Python dependencies
├── README.md                     # Setup and usage guide
│
├── data/
│   ├── pdfs/                     # Raw PD PDF files go here
│   │   ├── HDFC_Life_Q1_FY25.pdf
│   │   ├── HDFC_Life_Q2_FY25.pdf
│   │   ├── SBI_Life_Q1_FY25.pdf
│   │   ├── ICICI_Pru_Q1_FY25.pdf
│   │   └── LIC_Q1_FY25.pdf
│   └── processed/                # Extracted text/chunks stored here as JSON
│       ├── HDFC_Life_Q1_FY25.json
│       ├── HDFC_Life_page_definitions.json  # L-page index extracted from HDFC PDF
│       ├── ...
│       └── page_definitions.json # (optional) user-provided master L-page fallback
│                                   # place here if a PDF lacks an index page
│
├── vectordb/                     # ChromaDB persistent storage
│   └── chroma_db/                # Auto-created on first ingest
│
├── .streamlit/
│   └── config.toml               # Streamlit server settings — port, max upload size, theme
│
├── src/
│   ├── __init__.py               # Required — enables `from src.module import ...` imports
│   ├── config.py                 # Loads .env, exposes all settings
│   ├── pdf_parser.py             # Extracts text + tables from PD PDFs
│   ├── chunker.py                # Splits extracted content into chunks
│   ├── embedder.py               # Creates embeddings, manages ChromaDB
│   ├── retriever.py              # Searches ChromaDB for relevant chunks
│   ├── llm_client.py             # OpenRouter API wrapper — two-tier model routing
│   ├── rag_pipeline.py           # Orchestrates retriever + LLM
│   └── ingestor.py               # End-to-end: PDF → parse → chunk → embed
│
├── app/
│   └── streamlit_app.py          # Web UI — upload PDFs + ask questions
│
├── scripts/
│   ├── ingest_all.py             # Batch ingest all PDFs in data/pdfs/
│   └── test_query.py             # CLI test — ask a question from terminal
│
└── tests/
    ├── __init__.py               # Required for pytest discovery across packages
    ├── conftest.py               # Shared fixtures — ChromaDB seeded with test chunks
    ├── test_filename_parser.py   # Filename → company_code / quarter / FY extraction
    ├── test_chunker.py           # Chunker output shape + required metadata fields
    ├── test_complexity.py        # classify_complexity() simple vs complex routing
    ├── test_retriever.py         # Retrieval returns results + top-up logic
    ├── test_section_detection.py # L-page label → section name resolution
    └── test_truncation.py        # finish_reason='length' warning fires correctly
```
