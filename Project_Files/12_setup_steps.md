# 12. Setup & Run Steps

---

## Step 1: Clone and Create Virtual Environment

```powershell
# Windows (PowerShell)
git clone <repo-url>
cd insurance_rag
python -m venv .venv
.venv\Scripts\Activate.ps1
```

```bash
# macOS / Linux
git clone <repo-url>
cd insurance_rag
python -m venv .venv
source .venv/bin/activate
```

> **Always activate the venv before any `pip install` or `python` command.**

---

## Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Step 3: Configure .env

```powershell
# Windows (PowerShell)
Copy-Item .env.example .env

# macOS / Linux
# cp .env.example .env
```

Open `.env` and fill in at minimum:

```env
OPENROUTER_API_KEY=sk-or-your-key-here
```

All other settings have sensible defaults. See [03_env_config.md](./03_env_config.md) for full reference.

---

## Step 4: Create `.streamlit/config.toml`

This file is **required** for Streamlit to respect the upload size limit and port setting. It is not created automatically.

```powershell
# Windows (PowerShell)
New-Item -ItemType Directory -Force -Path .streamlit
New-Item -ItemType File -Path .streamlit\config.toml
```

Paste this content into `.streamlit/config.toml`:

```toml
[server]
port = 8501
maxUploadSize = 50
enableCORS = false

[theme]
base = "light"
```

---

## Step 5: Add PDF Files

Copy your PD PDF files into `data/pdfs/`. Make sure filenames follow the naming convention:

```
data/pdfs/
├── HDFC_Life_Q1_FY25.pdf
├── SBI_Life_Q1_FY25.pdf
├── ICICI_Pru_Q1_FY25.pdf
└── LIC_Q1_FY25.pdf
```

See [04_file_naming.md](./04_file_naming.md) for naming rules.

---

## Step 6: Ingest PDFs

```bash
# Ingest all PDFs in data/pdfs/
python scripts/ingest_all.py

# Ingest a single file
python scripts/ingest_all.py --file HDFC_Life_Q1_FY25.pdf

# Ingest and force re-index (even if already indexed)
python scripts/ingest_all.py --force
```

Expected output:

```
Processing HDFC_Life_Q1_FY25.pdf...
  Pages processed: 18
  Chunks created: 142
  Status: success ✅

Processing SBI_Life_Q1_FY25.pdf...
  Pages processed: 17
  Chunks created: 138
  Status: success ✅

Ingestion complete. Total chunks in DB: 280
```

---

## Step 7: Test from CLI

```bash
python scripts/test_query.py --q "Which company had highest GWP in Q1 FY25?"
```

Expected output:

```
Query: Which company had highest GWP in Q1 FY25?
Complexity: complex  (triggered by "highest", "which company")
Model: anthropic/claude-sonnet-4  (paid — complex query)
Chunks retrieved: 34  (30 initial + 4 top-up for missing companies)
Confidence: high

Answer:
Premium Ranking — Q1 FY2024-25
...

Sources: HDFC_Life_Q1_FY25.pdf p.4, LIC_Q1_FY25.pdf p.7
```

---

## Step 8: Launch Streamlit App

```bash
streamlit run app/streamlit_app.py
```

Opens in browser at `http://localhost:8501`

---

## Adding a New Quarter (Incremental)

When Q2 reports are available:

```powershell
# Windows (PowerShell) — copy new files to data/pdfs/
Copy-Item HDFC_Life_Q2_FY25.pdf data/pdfs/
Copy-Item SBI_Life_Q2_FY25.pdf data/pdfs/

# macOS / Linux
# cp HDFC_Life_Q2_FY25.pdf data/pdfs/

# Ingest only new files (already-indexed files are skipped automatically)
python scripts/ingest_all.py
```

The system checks `is_already_indexed()` before processing — no duplicates.
