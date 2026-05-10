# Setup Guide - Insurance PD Report Analyzer

Complete step-by-step guide to set up and run the system.

---

## Prerequisites

- **Python 3.10 or higher**
- **pip** (Python package manager)
- **Claude API key** from Anthropic

---

## Step 1: Verify Python Installation

```bash
python --version
```

Should show Python 3.10 or higher. If not, download from [python.org](https://www.python.org/downloads/).

---

## Step 2: Install Dependencies

```bash
# Navigate to project directory
cd c:\Users\Sombir\projects\LIFE_Public_Dislosure_Analyser

# Install all required packages
pip install -r requirements.txt
```

This will install:
- `pdfplumber` - PDF parsing
- `anthropic` - Claude API client
- `sentence-transformers` - Local embeddings
- `chromadb` - Vector database
- `streamlit` - Web UI
- `pandas`, `tqdm`, `python-dotenv` - Utilities

**Note:** First installation may take 5-10 minutes as it downloads ML models.

---

## Step 3: Configure Environment

### 3.1 Create .env file

```bash
# Copy the example file
copy .env.example .env
```

### 3.2 Get Claude API Key

1. Go to [https://console.anthropic.com/](https://console.anthropic.com/)
2. Sign up or log in
3. Navigate to API Keys section
4. Create a new API key
5. Copy the key (starts with `sk-ant-`)

### 3.3 Edit .env file

Open `.env` in a text editor and add your API key:

```env
ANTHROPIC_API_KEY=sk-ant-your-actual-api-key-here
```

**Important:** Keep this key secret! Never commit it to version control.

---

## Step 4: Verify Setup

Run the verification script:

```bash
python scripts/verify_setup.py
```

This checks:
- ✓ Python version
- ✓ All dependencies installed
- ✓ Configuration valid
- ✓ Directory structure correct
- ✓ ChromaDB accessible

If all checks pass, you're ready to go!

---

## Step 5: Add PDF Files

### 5.1 File Naming Convention

Files **must** follow this exact format:

```
{COMPANY_CODE}_{QUARTER}_{FY}.pdf
```

**Examples:**
```
HDFC_Life_Q1_FY25.pdf
SBI_Life_Q2_FY25.pdf
LIC_Q1_FY25.pdf
ICICI_Pru_Q3_FY25.pdf
```

**Rules:**
- Use underscores only (no spaces or hyphens)
- Quarter: `Q1`, `Q2`, `Q3`, or `Q4`
- FY: `FY25`, `FY26`, etc.
- Company code must be in the approved list (see below)

### 5.2 Supported Company Codes

Default codes (add more in `.env` if needed):
- `LIC` - Life Insurance Corporation of India
- `HDFC_Life` - HDFC Life Insurance
- `SBI_Life` - SBI Life Insurance
- `ICICI_Pru` - ICICI Prudential Life Insurance
- `Max_Life` - Max Life Insurance
- `Bajaj_Life` - Bajaj Allianz Life Insurance
- `Kotak_Life` - Kotak Mahindra Life Insurance
- `Tata_AIA` - Tata AIA Life Insurance

### 5.3 Place Files

Copy your PDF files to:

```
data/pdfs/
```

---

## Step 6: Ingest PDFs

Run the ingestion script:

```bash
python scripts/ingest_all.py
```

This will:
1. Parse each PDF (extract text and tables)
2. Split content into chunks
3. Create embeddings
4. Store in ChromaDB

**Time:** ~10-30 seconds per PDF depending on size.

**Output:**
```
Found 5 PDF files to process

================================================================================
Processing file 1/5: HDFC_Life_Q1_FY25.pdf
================================================================================
[1/3] Parsing PDF: HDFC_Life_Q1_FY25.pdf
[2/3] Chunking document...
[3/3] Creating embeddings and storing in ChromaDB...
✓ Success: 142 chunks in 12.4s

...

================================================================================
INGESTION COMPLETE
================================================================================
Total Files Found: 5
Successfully Ingested: 5
Skipped (Already Indexed): 0
Errors: 0
```

---

## Step 7: Test from CLI

Test with a sample question:

```bash
python scripts/test_query.py --q "Which company had the highest gross written premium?"
```

**Expected output:**
```
================================================================================
INSURANCE PD REPORT QUERY
================================================================================
Question: Which company had the highest gross written premium?

Retrieving relevant information and generating answer...

================================================================================
ANSWER
================================================================================
[Claude's answer with data from PDFs]

================================================================================
METADATA
================================================================================
Confidence: high
Chunks Used: 6
Sources: HDFC_Life_Q1_FY25.pdf, SBI_Life_Q1_FY25.pdf, LIC_Q1_FY25.pdf
```

### More Test Examples

```bash
# With company filter
python scripts/test_query.py --q "What was the claim settlement ratio?" --company HDFC_Life

# With time filter
python scripts/test_query.py --q "Show new business premium" --quarter Q1 --fy FY25

# Debug mode (shows retrieved chunks)
python scripts/test_query.py --q "Compare persistency ratios" --debug
```

---

## Step 8: Launch Web UI

Start the Streamlit app:

```bash
streamlit run app/streamlit_app.py
```

**Output:**
```
  You can now view your Streamlit app in your browser.

  Local URL: http://localhost:8501
  Network URL: http://192.168.1.x:8501
```

Open your browser to `http://localhost:8501`

### Web UI Features

**Tab 1: Ask a Question**
- Enter any question in plain English
- Filter by company, quarter, or FY
- Get answers with source citations
- See confidence level

**Tab 2: Upload Reports**
- Upload new PDF files
- View ingestion progress
- See all indexed files
- Delete files from index

**Tab 3: Index Status**
- View collection statistics
- See coverage matrix (which company × quarter combinations are indexed)
- Clear all data if needed

---

## Common Issues & Solutions

### Issue: "ANTHROPIC_API_KEY is not set"

**Solution:**
1. Ensure `.env` file exists in project root
2. Check that `ANTHROPIC_API_KEY=sk-ant-...` is in the file
3. Restart any running scripts

### Issue: "No PDF files found"

**Solution:**
1. Check files are in `data/pdfs/` directory
2. Verify filenames follow the exact naming convention
3. Ensure files have `.pdf` extension (lowercase)

### Issue: "Invalid filename format"

**Solution:**
Rename file to match format: `{COMPANY_CODE}_{QUARTER}_{FY}.pdf`

Example: `HDFC Life Q1 FY25.pdf` → `HDFC_Life_Q1_FY25.pdf`

### Issue: "No data in ChromaDB"

**Solution:**
Run ingestion: `python scripts/ingest_all.py`

### Issue: "Module not found"

**Solution:**
Install dependencies: `pip install -r requirements.txt`

### Issue: "Rate limit error"

**Solution:**
- Wait a few seconds and retry
- Check your Claude API usage limits
- The system has automatic retry with exponential backoff

---

## Re-indexing Files

If you update a PDF file:

```bash
# Re-index all files (force)
python scripts/ingest_all.py --force
```

Or delete specific file from UI (Tab 2) and re-upload.

---

## Adding New Companies

To add a new company code:

1. Edit `.env` file
2. Add to `COMPANY_CODES` list:

```env
COMPANY_CODES=LIC,HDFC_Life,SBI_Life,ICICI_Pru,Max_Life,Bajaj_Life,Kotak_Life,Tata_AIA,New_Company
```

3. Name your PDFs with the new code:

```
New_Company_Q1_FY25.pdf
```

---

## Performance Tips

### Faster Ingestion
- Use SSD storage for `vectordb/` directory
- Increase `CHUNK_SIZE` in `.env` for fewer chunks (faster but less granular)

### Better Answers
- Increase `TOP_K_RESULTS` in `.env` for more context (slower but more comprehensive)
- Lower `SIMILARITY_THRESHOLD` to include more chunks (may reduce precision)

### Cost Optimization
- Use smaller `CLAUDE_MAX_TOKENS` for shorter answers
- Filter queries by company/quarter to reduce context size

---

## Next Steps

1. **Add more PDFs** - Build your database with more companies and quarters
2. **Test queries** - Try different question types (rankings, comparisons, trends)
3. **Customize** - Adjust settings in `.env` for your use case
4. **Explore** - Check documentation in `Project_Files/` for advanced features

---

## Getting Help

- **Documentation:** See `Project_Files/` directory for detailed specs
- **Examples:** Check `Project_Files/09_example_qa.md` for sample questions
- **Verification:** Run `python scripts/verify_setup.py` to diagnose issues

---

## System Requirements

**Minimum:**
- Python 3.10+
- 4GB RAM
- 2GB free disk space

**Recommended:**
- Python 3.11+
- 8GB RAM
- 5GB free disk space (for larger databases)
- SSD storage

---

## Security Notes

- **Never commit `.env` file** to version control
- **Keep API key secret** - it's linked to your billing
- **Local data** - All PDFs and embeddings stay on your machine
- **No external database** - ChromaDB runs locally

---

## Success Checklist

- [ ] Python 3.10+ installed
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] `.env` file created with API key
- [ ] Verification script passes (`python scripts/verify_setup.py`)
- [ ] PDF files added to `data/pdfs/`
- [ ] Ingestion completed (`python scripts/ingest_all.py`)
- [ ] CLI test works (`python scripts/test_query.py --q "test"`)
- [ ] Web UI launches (`streamlit run app/streamlit_app.py`)

---

**You're all set! Start asking questions about your insurance data.**
