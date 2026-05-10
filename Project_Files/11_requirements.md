# 11. requirements.txt

```txt
# PDF Processing
pdfplumber==0.11.0

# LLM (OpenRouter uses OpenAI-compatible API)
openai==1.30.0

# Embeddings (free, local — no API key needed)
sentence-transformers==2.7.0
torch==2.2.0          # required by sentence-transformers — see Known Dependency Notes for CPU-only install

# Vector Database
chromadb==0.5.0

# Config
python-dotenv==1.0.0

# Web UI
streamlit==1.35.0

# Utilities
pandas==2.2.0
tqdm==4.66.0

# Testing
pytest==8.2.0
pytest-mock==3.14.0   # mock LLM calls in tests — no live API key required
```

---

## Notes

| Package | Why |
|---------|-----|
| `pdfplumber` | Best Python library for extracting tables from text-based PDFs |
| `openai` | OpenAI SDK — used as OpenRouter client (OpenRouter is OpenAI-compatible) |
| `sentence-transformers` | Free local embeddings — no OpenAI API key needed |
| `torch` | Required by sentence-transformers for local model inference |
| `chromadb` | Simple local vector database — no server setup required |
| `python-dotenv` | Loads `.env` file into environment variables |
| `streamlit` | Fast web UI — no HTML/CSS/JS needed |
| `pandas` | For table formatting in Streamlit |
| `tqdm` | Progress bars in CLI scripts |
| `pytest` | Automated test runner for the `tests/` suite |
| `pytest-mock` | `mocker` fixture for patching `ask_llm` and OpenRouter calls in tests |

---

## Python Version

Requires **Python 3.10+**

```bash
python --version  # Should be 3.10 or higher
```

---

## Known Dependency Notes

| Issue | Resolution |
|-------|------------|
| `chromadb` and `sentence-transformers` both pull `onnxruntime` — versions may conflict | Pin `onnxruntime==1.17.3` in `requirements.txt` if `pip install` fails with onnxruntime errors |
| `torch==2.2.0` downloads a large CUDA build by default on Windows | Use CPU-only build: `pip install torch==2.2.0 --index-url https://download.pytorch.org/whl/cpu` before running `pip install -r requirements.txt` |
| `chromadb>=0.5` changed the collection `.add()` API (ids now required) | Ensure `embedder.py` always passes explicit `ids=` when calling `collection.add()` — do not rely on auto-generated IDs |

---

## Install Command

```bash
# Windows: install CPU-only torch first to avoid downloading CUDA binaries
pip install torch==2.2.0 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```
