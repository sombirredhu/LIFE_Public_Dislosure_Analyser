# Getting Started - Quick Checklist

Follow this checklist to get your system up and running in minutes.

---

## ✅ Pre-Setup Checklist

- [ ] Python 3.10 or higher installed
- [ ] pip (Python package manager) available
- [ ] Claude API account created at https://console.anthropic.com/
- [ ] IRDAI Public Disclosure PDF files ready

---

## 🚀 Setup Steps (5 minutes)

### Step 1: Install Dependencies ⏱️ ~5-10 minutes

**Option A: Using setup script (Windows)**
```bash
setup.bat
```

**Option B: Manual installation**
```bash
pip install -r requirements.txt
```

- [ ] Dependencies installed successfully

---

### Step 2: Configure API Key ⏱️ ~1 minute

1. Copy the example environment file:
```bash
copy .env.example .env
```

2. Get your Claude API key:
   - Go to https://console.anthropic.com/
   - Sign up or log in
   - Navigate to API Keys
   - Create a new key
   - Copy the key (starts with `sk-ant-`)

3. Edit `.env` file and add your key:
```env
ANTHROPIC_API_KEY=sk-ant-your-actual-key-here
```

- [ ] `.env` file created
- [ ] API key added to `.env`

---

### Step 3: Verify Setup ⏱️ ~30 seconds

```bash
python scripts/verify_setup.py
```

Expected output: All checks should pass ✓

- [ ] Verification script passes

---

## 📄 Add Your Data (2 minutes)

### Step 4: Prepare PDF Files

1. Rename your PDF files to follow the convention:
   ```
   {COMPANY_CODE}_{QUARTER}_{FY}.pdf
   ```

2. Examples:
   ```
   HDFC_Life_Q1_FY25.pdf
   SBI_Life_Q1_FY25.pdf
   LIC_Q2_FY25.pdf
   ```

3. Place files in `data/pdfs/` folder

- [ ] PDF files renamed correctly
- [ ] Files placed in `data/pdfs/`

---

### Step 5: Ingest PDFs ⏱️ ~10-30 seconds per file

```bash
python scripts/ingest_all.py
```

This will:
- Parse each PDF
- Extract text and tables
- Create embeddings
- Store in ChromaDB

Expected output:
```
Successfully Ingested: X
Skipped: 0
Errors: 0
```

- [ ] All PDFs ingested successfully

---

## 🎯 Test Your System (1 minute)

### Step 6: Test from Command Line

```bash
python scripts/test_query.py --q "Which company had the highest gross written premium?"
```

Expected: You should get an answer with source citations

- [ ] CLI query works

---

### Step 7: Launch Web Interface

```bash
streamlit run app/streamlit_app.py
```

Opens at: http://localhost:8501

- [ ] Web UI launches successfully
- [ ] Can ask questions in Tab 1
- [ ] Can see indexed files in Tab 2
- [ ] Can view stats in Tab 3

---

## 🎉 You're Ready!

If all checkboxes are marked, your system is fully operational!

---

## 📝 Quick Test Questions

Try these to verify everything works:

### Basic Query
```
What was HDFC Life's gross written premium in Q1 FY25?
```

### Comparison
```
Compare HDFC Life and SBI Life's new business premium
```

### Ranking
```
Which company had the highest claim settlement ratio?
```

### Trend
```
Show HDFC Life's premium for all quarters in FY25
```

---

## 🔧 Troubleshooting

### Issue: "ANTHROPIC_API_KEY is not set"
**Solution:** Edit `.env` file and add your API key

### Issue: "No PDF files found"
**Solution:** Add PDF files to `data/pdfs/` folder

### Issue: "Invalid filename format"
**Solution:** Rename files to match: `COMPANY_CODE_QUARTER_FY.pdf`

### Issue: "No data in ChromaDB"
**Solution:** Run `python scripts/ingest_all.py`

### Issue: "Module not found"
**Solution:** Run `pip install -r requirements.txt`

---

## 📚 Next Steps

### Learn More
- Read `README.md` for project overview
- Check `SETUP_GUIDE.md` for detailed instructions
- See `QUICK_REFERENCE.md` for command reference
- Explore `Project_Files/` for complete documentation

### Add More Data
- Add more PDF files to `data/pdfs/`
- Run `python scripts/ingest_all.py` again
- New data is automatically indexed

### Customize
- Edit `.env` to adjust settings
- Modify `CHUNK_SIZE` for different granularity
- Change `TOP_K_RESULTS` for more/less context
- Adjust `SIMILARITY_THRESHOLD` for filtering

---

## 💡 Tips for Best Results

### File Naming
- ✅ Use underscores: `HDFC_Life_Q1_FY25.pdf`
- ❌ Don't use spaces: `HDFC Life Q1 FY25.pdf`
- ❌ Don't use hyphens: `HDFC-Life-Q1-FY25.pdf`

### Questions
- Be specific: "What was HDFC Life's GWP in Q1 FY25?"
- Use company names: "Compare HDFC Life and SBI Life"
- Specify time periods: "Show data for Q1 FY25"

### Filters
- Use company filter for focused queries
- Use quarter/FY filter for time-specific questions
- Combine filters for precise results

---

## 🎓 Example Workflow

1. **Upload PDFs** (Tab 2 in Web UI)
   - Upload multiple files at once
   - System validates filenames
   - Shows ingestion progress

2. **Ask Questions** (Tab 1 in Web UI)
   - Type your question
   - Apply filters if needed
   - Get answer with sources

3. **Check Coverage** (Tab 3 in Web UI)
   - See which companies are indexed
   - View coverage matrix
   - Check collection stats

---

## 📊 What You Can Analyze

### Financial Metrics
- Gross Written Premium (GWP)
- New Business Premium
- Renewal Premium
- Net Premium

### Performance Indicators
- Claim Settlement Ratio
- Persistency Ratios (13th, 25th, 37th, 49th, 61st month)
- Solvency Ratio
- Operating Expense Ratio

### Business Mix
- Channel-wise Premium (Agency, Banca, Direct, Broker)
- Product Mix (ULIP, Par, Non-Par, Annuity)
- Individual vs Group Business

### Comparisons
- Company vs Company
- Quarter vs Quarter
- Year over Year
- Industry Aggregates

---

## 🔒 Security Reminders

- ✅ Keep your API key secret
- ✅ Never commit `.env` to version control
- ✅ All data stays on your local machine
- ✅ No external database connections

---

## 📞 Need Help?

1. **Run verification:**
   ```bash
   python scripts/verify_setup.py
   ```

2. **Check documentation:**
   - `SETUP_GUIDE.md` - Detailed setup
   - `QUICK_REFERENCE.md` - Command reference
   - `Project_Files/` - Complete specs

3. **Test individual components:**
   ```bash
   python src/config.py          # Test config
   python src/pdf_parser.py      # Test parser
   python src/retriever.py       # Test retrieval
   ```

---

## ✨ Success Indicators

You'll know everything is working when:

- ✅ Verification script passes all checks
- ✅ PDFs ingest without errors
- ✅ CLI queries return answers with sources
- ✅ Web UI loads and shows your data
- ✅ Questions get accurate, cited answers

---

## 🎯 Your First Real Query

Once setup is complete, try this:

```bash
python scripts/test_query.py --q "Which company had the highest gross written premium in Q1 FY25?"
```

If you get a detailed answer with source citations, **you're all set!** 🎉

---

**Ready to analyze your insurance data? Let's go! 🚀**

For detailed documentation, see:
- `README.md` - Overview
- `SETUP_GUIDE.md` - Setup details
- `QUICK_REFERENCE.md` - Commands
- `PROJECT_SUMMARY.md` - What was built
