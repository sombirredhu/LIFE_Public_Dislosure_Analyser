# Life Insurance Public Disclosure — RAG Analyzer

**RAG-Based Multi-Company Financial Report Analyzer**

> Author: Sombir  
> Stack: Python · OpenRouter API · ChromaDB · Streamlit · pdfplumber

---

## What This System Does

Ingests IRDAI Public Disclosure (PD) PDF reports from multiple life insurance companies across multiple quarters, extracts and indexes content using RAG, and answers plain English questions across all companies and time periods simultaneously.

### Example Questions

- Which company had the highest total premium in Q2 FY2025?
- What was LIC's gross written premium in Q1 FY2025 in crore?
- Compare persistency ratio of HDFC Life vs SBI Life for Q3 FY2025
- Which company had the lowest claim settlement ratio this quarter?
- Show channel-wise new business premium ranking for all companies
- What was the total industry new business premium for Q2 FY2025?

---

## Quick Start

```powershell
# Windows (PowerShell)

# 1. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# 2. Install dependencies (CPU-only torch first to avoid large CUDA download)
pip install torch==2.2.0 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

# 3. Configure environment
Copy-Item .env.example .env
# Open .env and fill in OPENROUTER_API_KEY

# 4. Create Streamlit config (required for upload size + port settings)
New-Item -ItemType Directory -Force -Path .streamlit
# Paste config content into .streamlit/config.toml — see 10_streamlit_ui.md

# 5. Add PDF files to data/pdfs/ following naming convention
# Example: HDFC_Life_Q1_FY25.pdf

# 6. Ingest all PDFs
python scripts/ingest_all.py

# 7. Test from CLI
python scripts/test_query.py --q "Which company had highest GWP in Q1 FY25?"

# 8. Launch app
streamlit run app/streamlit_app.py
```

> See [12_setup_steps.md](./12_setup_steps.md) for the full setup guide with expected output at each step.

---

## Documentation Index

| File | Description |
|------|-------------|
| [01_project_overview.md](./01_project_overview.md) | Scope, goals, tech stack |
| [02_folder_structure.md](./02_folder_structure.md) | Full project directory layout |
| [03_env_config.md](./03_env_config.md) | Complete .env file with all settings |
| [04_file_naming.md](./04_file_naming.md) | PDF file naming convention |
| [05_data_schema.md](./05_data_schema.md) | Data extracted from PD reports |
| [06_chunk_metadata.md](./06_chunk_metadata.md) | ChromaDB chunk metadata schema |
| [07_modules.md](./07_modules.md) | All module descriptions with input/output contracts |
| [08_system_prompt.md](./08_system_prompt.md) | Claude system prompt |
| [09_example_qa.md](./09_example_qa.md) | Example questions and expected answers |
| [10_streamlit_ui.md](./10_streamlit_ui.md) | Streamlit app views and features |
| [11_requirements.md](./11_requirements.md) | Python dependencies |
| [12_setup_steps.md](./12_setup_steps.md) | Step-by-step setup guide |
| [13_build_order.md](./13_build_order.md) | Recommended build order for Claude Code |
| [14_limitations.md](./14_limitations.md) | Known limitations and handling |
