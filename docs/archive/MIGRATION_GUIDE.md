# Migration Guide: Text-Based to Page-Wise Chunking

## Overview

This guide provides step-by-step instructions for migrating your IRDAI Public Disclosure PDF analyzer from text-based chunking to page-wise chunking. The migration will reduce your chunk count by approximately 70-80% (from ~1,820 to ~300-400 chunks) while improving semantic coherence and retrieval accuracy.

**Migration Time Estimate:** 15-30 minutes  
**Downtime Required:** Yes (during re-indexing)  
**Reversible:** Yes (rollback procedure included)

---

## Table of Contents

1. [Pre-Migration Checklist](#pre-migration-checklist)
2. [Backup Procedure](#backup-procedure)
3. [Migration Steps](#migration-steps)
4. [Verification](#verification)
5. [Rollback Procedure](#rollback-procedure)
6. [Performance Comparison](#performance-comparison)
7. [Troubleshooting](#troubleshooting)

---

## Pre-Migration Checklist

Before starting the migration, ensure you have:

- [ ] **Python environment activated** (`.venv` or your virtual environment)
- [ ] **All dependencies installed** (`pip install -r requirements.txt`)
- [ ] **Sufficient disk space** (at least 500MB free for backups)
- [ ] **No active queries running** (stop any Streamlit apps or API services)
- [ ] **Backup destination prepared** (folder for ChromaDB backup)
- [ ] **Read access to all PDF files** (in `data/pdfs/` or `data/processed/`)
- [ ] **Write access to vectordb directory** (for ChromaDB operations)

**Estimated Disk Space Requirements:**
- Current ChromaDB: ~100-200MB
- Backup: ~100-200MB
- New ChromaDB: ~50-100MB (smaller due to fewer chunks)
- **Total needed:** ~500MB

---

## Backup Procedure

### Step 1: Stop All Services

Stop any running services that use ChromaDB:

```bash
# Stop Streamlit app (if running)
# Press Ctrl+C in the terminal where it's running

# Or kill the process
# Windows:
taskkill /F /IM streamlit.exe

# Linux/Mac:
pkill -f streamlit
```

### Step 2: Backup ChromaDB Database

Create a timestamped backup of your current ChromaDB:

```bash
# Create backup directory
mkdir -p backups

# Copy ChromaDB to backup location
# Windows (PowerShell):
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
Copy-Item -Path "vectordb" -Destination "backups/vectordb_backup_$timestamp" -Recurse

# Linux/Mac:
timestamp=$(date +%Y%m%d_%H%M%S)
cp -r vectordb backups/vectordb_backup_$timestamp

# Verify backup
ls -lh backups/
```

**Expected Output:**
```
backups/
  vectordb_backup_20250511_143022/
    chroma.sqlite3
    [other ChromaDB files]
```

### Step 3: Export Current Chunk Statistics

Document your current system state for comparison:

```bash
# Run verification script to capture current stats
python scripts/verify_setup.py > backups/pre_migration_stats.txt

# Or use a custom script to export chunk counts
python -c "
import chromadb
from src.config import CHROMA_PERSIST_DIR

client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
collection = client.get_collection('irdai_disclosures')

print(f'Total chunks: {collection.count()}')
print(f'Collection metadata: {collection.metadata}')

# Get sample chunks
results = collection.get(limit=5, include=['metadatas'])
print(f'Sample chunk IDs: {[m[\"chunk_id\"] for m in results[\"metadatas\"]]}')
" > backups/pre_migration_chunks.txt
```

### Step 4: Backup Configuration Files

```bash
# Backup .env file
cp .env backups/.env.backup

# Backup config.py (if modified)
cp src/config.py backups/config.py.backup
```

**Backup Checklist:**
- [ ] ChromaDB directory backed up
- [ ] Pre-migration statistics exported
- [ ] Configuration files backed up
- [ ] Backup timestamp recorded
- [ ] Backup size verified (should be ~100-200MB)

---

## Migration Steps

### Step 1: Update Configuration

Edit your `.env` file to enable page-wise chunking:

```bash
# Open .env file in your editor
# Windows:
notepad .env

# Linux/Mac:
nano .env
# or
vim .env
```

Add or update these lines:

```bash
# Page-wise chunking configuration
PAGE_WISE_CHUNKING=True
MAX_PAGE_TOKENS=8000

# Legacy settings (keep for backward compatibility)
CHUNK_SIZE=1200
CHUNK_OVERLAP=150
MIN_CHUNK_SIZE=100
```

**Save and close the file.**

### Step 2: Verify Configuration

Confirm the configuration is loaded correctly:

```bash
python -c "
from src.config import PAGE_WISE_CHUNKING, MAX_PAGE_TOKENS
print(f'PAGE_WISE_CHUNKING: {PAGE_WISE_CHUNKING}')
print(f'MAX_PAGE_TOKENS: {MAX_PAGE_TOKENS}')
assert PAGE_WISE_CHUNKING == True, 'PAGE_WISE_CHUNKING must be True'
assert MAX_PAGE_TOKENS == 8000, 'MAX_PAGE_TOKENS must be 8000'
print('✓ Configuration verified')
"
```

**Expected Output:**
```
PAGE_WISE_CHUNKING: True
MAX_PAGE_TOKENS: 8000
✓ Configuration verified
```

### Step 3: Clear Existing ChromaDB

Remove the old text-based chunks:

```bash
# Option A: Delete and recreate ChromaDB directory
# Windows (PowerShell):
Remove-Item -Path "vectordb" -Recurse -Force
New-Item -Path "vectordb" -ItemType Directory

# Linux/Mac:
rm -rf vectordb
mkdir -p vectordb

# Option B: Use Python to clear collection
python -c "
import chromadb
from src.config import CHROMA_PERSIST_DIR

client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
try:
    client.delete_collection('irdai_disclosures')
    print('✓ Collection deleted')
except:
    print('✓ Collection does not exist (already clean)')
"
```

### Step 4: Re-index PDFs with Page-Wise Chunking

Run the ingestion script to create new page-wise chunks:

```bash
# If you have processed JSON files (recommended):
python scripts/ingest_all.py

# If you need to re-parse PDFs from scratch:
python scripts/ingest_all.py --reparse

# Monitor progress
# The script will show:
# - Files being processed
# - Chunks created per file
# - Total processing time
```

**Expected Output:**
```
[INFO] Processing: data/processed/HDFC_Life_Q1_FY25.json
[INFO] Created 85 chunks from 85 pages
[INFO] Embedded and stored 85 chunks
[INFO] Processing: data/processed/ICICI_Pru_Q1_FY25.json
[INFO] Created 155 chunks from 155 pages
[INFO] Embedded and stored 155 chunks
...
[INFO] Total files processed: 6
[INFO] Total chunks created: 560
[INFO] Total processing time: 45.2 seconds
```

**Processing Time Estimates:**
- 6 companies (560 pages): ~45-60 seconds
- 50 companies (~5,000 pages): ~6-8 minutes
- 500 companies (~50,000 pages): ~60-90 minutes

### Step 5: Verify Migration Success

Run verification checks:

```bash
# Check chunk count
python -c "
import chromadb
from src.config import CHROMA_PERSIST_DIR

client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
collection = client.get_collection('irdai_disclosures')

total = collection.count()
print(f'Total chunks: {total}')

# Expected: 300-600 chunks (depending on number of companies)
if 300 <= total <= 600:
    print('✓ Chunk count in expected range')
else:
    print(f'⚠ Warning: Chunk count {total} outside expected range (300-600)')

# Check sample chunk structure
results = collection.get(limit=1, include=['metadatas'])
if results['metadatas']:
    meta = results['metadatas'][0]
    print(f'Sample chunk_id: {meta.get(\"chunk_id\")}')
    print(f'Content type: {meta.get(\"content_type\")}')
    print(f'Is split: {meta.get(\"is_split\")}')
    
    # Verify page-wise format
    if meta.get('content_type') == 'page':
        print('✓ Page-wise chunks detected')
    else:
        print('⚠ Warning: Not page-wise chunks')
"
```

**Expected Output:**
```
Total chunks: 560
✓ Chunk count in expected range
Sample chunk_id: HDFC_Life_Q1_FY25_page1
Content type: page
Is split: False
✓ Page-wise chunks detected
```

---

## Verification

### Functional Verification

Test that the system works correctly with page-wise chunks:

#### 1. Test Query Retrieval

```bash
# Run test query script
python scripts/test_query.py

# Or test manually
python -c "
from src.rag_pipeline import query_documents

# Test query
result = query_documents('What is the premium income for HDFC Life?')
print(f'Answer: {result[\"answer\"]}')
print(f'Sources: {len(result[\"sources\"])} chunks retrieved')

# Verify chunks are complete pages
for source in result['sources'][:3]:
    print(f'  - {source[\"metadata\"][\"chunk_id\"]} (page {source[\"metadata\"][\"page_number\"]})')
"
```

#### 2. Test Streamlit App

```bash
# Start Streamlit app
streamlit run app/streamlit_app.py

# In browser:
# 1. Navigate to http://localhost:8501
# 2. Enter a test query
# 3. Verify results are returned
# 4. Check that source chunks show complete page content
# 5. Test 3D visualization (should show ~560 points)
```

#### 3. Verify Metadata Completeness

```bash
python -c "
import chromadb
from src.config import CHROMA_PERSIST_DIR

client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
collection = client.get_collection('irdai_disclosures')

# Get sample chunks
results = collection.get(limit=10, include=['metadatas'])

# Check required fields
required_fields = [
    'chunk_id', 'company', 'company_code', 'quarter', 'fy',
    'page_number', 'page_label', 'section', 'content_type',
    'char_count', 'ingested_at', 'table_count', 'text_block_count', 'is_split'
]

missing_fields = []
for meta in results['metadatas']:
    for field in required_fields:
        if field not in meta:
            missing_fields.append(field)

if missing_fields:
    print(f'⚠ Missing fields: {set(missing_fields)}')
else:
    print('✓ All required metadata fields present')

# Check chunk_id format
for meta in results['metadatas'][:5]:
    chunk_id = meta['chunk_id']
    if '_page' in chunk_id:
        print(f'✓ Valid chunk_id format: {chunk_id}')
    else:
        print(f'⚠ Invalid chunk_id format: {chunk_id}')
"
```

### Performance Verification

Compare performance metrics before and after migration:

```bash
# Create comparison report
python -c "
import chromadb
from src.config import CHROMA_PERSIST_DIR

client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
collection = client.get_collection('irdai_disclosures')

# Current stats
current_count = collection.count()

# Read pre-migration stats from backup
with open('backups/pre_migration_chunks.txt', 'r') as f:
    pre_migration_text = f.read()
    # Extract old count (assumes format 'Total chunks: 1820')
    import re
    match = re.search(r'Total chunks: (\d+)', pre_migration_text)
    old_count = int(match.group(1)) if match else 1820

# Calculate reduction
reduction_pct = ((old_count - current_count) / old_count) * 100

print('=== Migration Performance Comparison ===')
print(f'Before: {old_count} chunks (text-based)')
print(f'After:  {current_count} chunks (page-wise)')
print(f'Reduction: {reduction_pct:.1f}%')
print(f'Target: 70-80% reduction')

if 70 <= reduction_pct <= 85:
    print('✓ Reduction within expected range')
else:
    print(f'⚠ Reduction {reduction_pct:.1f}% outside expected range (70-85%)')
"
```

---

## Rollback Procedure

If you encounter issues during or after migration, follow these steps to rollback:

### When to Rollback

Consider rollback if:
- Retrieval accuracy drops significantly (>10% worse)
- Processing errors on >5% of pages
- Performance degradation >50%
- Critical metadata missing
- System instability or crashes

### Rollback Steps

#### Step 1: Stop All Services

```bash
# Stop Streamlit or any running services
# Windows:
taskkill /F /IM streamlit.exe

# Linux/Mac:
pkill -f streamlit
```

#### Step 2: Restore Configuration

```bash
# Restore .env file
cp backups/.env.backup .env

# Verify configuration
python -c "
from src.config import PAGE_WISE_CHUNKING
print(f'PAGE_WISE_CHUNKING: {PAGE_WISE_CHUNKING}')
"
```

#### Step 3: Restore ChromaDB from Backup

```bash
# Remove current ChromaDB
# Windows (PowerShell):
Remove-Item -Path "vectordb" -Recurse -Force

# Linux/Mac:
rm -rf vectordb

# Restore from backup (use your backup timestamp)
# Windows (PowerShell):
$backup = Get-ChildItem backups | Where-Object {$_.Name -like "vectordb_backup_*"} | Sort-Object Name -Descending | Select-Object -First 1
Copy-Item -Path $backup.FullName -Destination "vectordb" -Recurse

# Linux/Mac:
backup=$(ls -t backups/vectordb_backup_* | head -1)
cp -r "$backup" vectordb

# Verify restoration
python -c "
import chromadb
from src.config import CHROMA_PERSIST_DIR

client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
collection = client.get_collection('irdai_disclosures')
print(f'Restored chunks: {collection.count()}')
"
```

#### Step 4: Verify Rollback

```bash
# Test query
python scripts/test_query.py

# Check chunk format
python -c "
import chromadb
from src.config import CHROMA_PERSIST_DIR

client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
collection = client.get_collection('irdai_disclosures')

results = collection.get(limit=1, include=['metadatas'])
if results['metadatas']:
    chunk_id = results['metadatas'][0]['chunk_id']
    print(f'Sample chunk_id: {chunk_id}')
    
    # Text-based chunks have format: {company}_{quarter}_{fy}_page{N}_chunk{M}
    if '_chunk' in chunk_id and '_page' in chunk_id:
        print('✓ Rollback successful: text-based chunks restored')
    else:
        print('⚠ Warning: Unexpected chunk format')
"
```

#### Step 5: Document Rollback Reason

Create a rollback report for future reference:

```bash
# Create rollback report
cat > backups/rollback_report.txt << EOF
Rollback Date: $(date)
Reason: [Describe why rollback was necessary]
Issues Encountered:
- [Issue 1]
- [Issue 2]
- [Issue 3]

Pre-Rollback State:
- Chunks: [number]
- Errors: [description]

Post-Rollback State:
- Chunks: [number from verification]
- Status: [working/not working]

Next Steps:
- [Action items to resolve issues before retry]
EOF

# Edit the report with actual details
# Windows:
notepad backups/rollback_report.txt

# Linux/Mac:
nano backups/rollback_report.txt
```

---

## Performance Comparison

### Expected Improvements

| Metric | Text-Based | Page-Wise | Improvement |
|--------|------------|-----------|-------------|
| **Total Chunks** | ~1,820 | ~300-400 | 70-80% reduction |
| **Avg Chunk Size** | ~1,000 chars | ~4,000-6,000 chars | 4-6x larger |
| **Retrieval Speed** | Baseline | 70-80% faster | Fewer chunks to search |
| **Semantic Coherence** | Fragmented | Complete | Tables stay intact |
| **L-Page Alignment** | Partial | Perfect | 1 L-page = 1 chunk |
| **Storage Size** | ~150-200MB | ~50-100MB | 50-70% reduction |

### Benchmark Tests

Run these benchmarks to measure actual performance:

#### 1. Chunk Count Comparison

```bash
python -c "
import chromadb
from src.config import CHROMA_PERSIST_DIR

# Read pre-migration count
with open('backups/pre_migration_chunks.txt', 'r') as f:
    import re
    match = re.search(r'Total chunks: (\d+)', f.read())
    old_count = int(match.group(1)) if match else 1820

# Get current count
client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
collection = client.get_collection('irdai_disclosures')
new_count = collection.count()

print(f'Text-Based Chunks: {old_count}')
print(f'Page-Wise Chunks: {new_count}')
print(f'Reduction: {((old_count - new_count) / old_count * 100):.1f}%')
"
```

#### 2. Query Performance Test

```bash
python -c "
import time
from src.rag_pipeline import query_documents

# Test queries
queries = [
    'What is the premium income for HDFC Life?',
    'Show me claims data for Q1 FY25',
    'What is the balance sheet for ICICI Prudential?'
]

total_time = 0
for query in queries:
    start = time.time()
    result = query_documents(query)
    elapsed = time.time() - start
    total_time += elapsed
    print(f'Query: {query[:50]}...')
    print(f'  Time: {elapsed:.3f}s')
    print(f'  Sources: {len(result[\"sources\"])} chunks')

avg_time = total_time / len(queries)
print(f'\\nAverage query time: {avg_time:.3f}s')
"
```

#### 3. Storage Size Comparison

```bash
# Check ChromaDB size
# Windows (PowerShell):
$size = (Get-ChildItem -Path "vectordb" -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB
Write-Host "ChromaDB size: $([math]::Round($size, 2)) MB"

# Linux/Mac:
du -sh vectordb
```

#### 4. Retrieval Quality Test

```bash
# Run accuracy test script (if available)
python test_rag_accuracy.py

# Or manual quality check
python -c "
from src.rag_pipeline import query_documents

# Test query that requires complete table context
result = query_documents('Compare premium income across all companies')

print('Answer:', result['answer'][:200], '...')
print(f'Sources: {len(result[\"sources\"])} chunks')

# Check if sources contain complete tables
for i, source in enumerate(result['sources'][:3], 1):
    meta = source['metadata']
    text = source['text']
    print(f'\\nSource {i}:')
    print(f'  Chunk ID: {meta[\"chunk_id\"]}')
    print(f'  Page: {meta[\"page_number\"]} ({meta[\"page_label\"]})')
    print(f'  Section: {meta[\"section\"]}')
    print(f'  Tables: {meta.get(\"table_count\", 0)}')
    print(f'  Text length: {len(text)} chars')
    
    # Check if table is complete (has headers and multiple rows)
    if '|' in text:
        lines = [l for l in text.split('\\n') if '|' in l]
        print(f'  Table rows: {len(lines)}')
"
```

---

## Troubleshooting

### Common Issues and Solutions

#### Issue 1: Configuration Not Loading

**Symptoms:**
- PAGE_WISE_CHUNKING still shows False
- Chunks still have old format

**Solution:**
```bash
# Verify .env file is in correct location
ls -la .env

# Check for syntax errors in .env
cat .env | grep PAGE_WISE_CHUNKING

# Restart Python interpreter
# Exit and re-run your script

# Force reload config
python -c "
import importlib
import src.config
importlib.reload(src.config)
from src.config import PAGE_WISE_CHUNKING
print(f'PAGE_WISE_CHUNKING: {PAGE_WISE_CHUNKING}')
"
```

#### Issue 2: "Unsplittable Table Row" Errors

**Symptoms:**
- Error: "Page X rejected: unsplittable table row exceeds token limit"
- Some pages not indexed

**Solution:**
```bash
# Identify problematic pages
python -c "
import json
from src.pdf_parser import parse_pdf
from src.chunker import _estimate_tokens

# Check each processed JSON
import os
for filename in os.listdir('data/processed'):
    if not filename.endswith('.json'):
        continue
    
    with open(f'data/processed/{filename}', 'r') as f:
        doc = json.load(f)
    
    for page in doc.get('pages', []):
        for table in page.get('tables', []):
            if 'raw_text' in table:
                tokens = _estimate_tokens(table['raw_text'])
                if tokens > 7600:
                    print(f'{filename} - Page {page[\"page_number\"]}: {tokens} tokens')
"

# Options:
# 1. Increase MAX_PAGE_TOKENS (not recommended, may exceed model limit)
# 2. Manually split problematic tables in source PDF
# 3. Skip problematic pages (document in migration notes)
```

#### Issue 3: Chunk Count Too Low

**Symptoms:**
- Fewer than 300 chunks for 6 companies
- Many pages missing

**Solution:**
```bash
# Check for empty pages
python -c "
import json
import os

total_pages = 0
empty_pages = 0

for filename in os.listdir('data/processed'):
    if not filename.endswith('.json'):
        continue
    
    with open(f'data/processed/{filename}', 'r') as f:
        doc = json.load(f)
    
    for page in doc.get('pages', []):
        total_pages += 1
        tables = page.get('tables', [])
        text_blocks = page.get('text_blocks', [])
        
        if not tables and not text_blocks:
            empty_pages += 1

print(f'Total pages: {total_pages}')
print(f'Empty pages: {empty_pages}')
print(f'Expected chunks: {total_pages - empty_pages}')
"

# If many empty pages, check PDF parsing quality
python scripts/test_extraction.py
```

#### Issue 4: Retrieval Returns No Results

**Symptoms:**
- Queries return empty results
- "No relevant documents found"

**Solution:**
```bash
# Check if collection exists and has data
python -c "
import chromadb
from src.config import CHROMA_PERSIST_DIR

client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)

# List collections
collections = client.list_collections()
print(f'Collections: {[c.name for c in collections]}')

# Check collection count
if collections:
    collection = client.get_collection('irdai_disclosures')
    print(f'Chunks in collection: {collection.count()}')
    
    # Test query
    results = collection.query(
        query_texts=['premium income'],
        n_results=5
    )
    print(f'Query returned: {len(results[\"ids\"][0])} results')
else:
    print('⚠ No collections found - re-run ingestion')
"

# If collection is empty, re-run ingestion
python scripts/ingest_all.py
```

#### Issue 5: Memory Errors During Ingestion

**Symptoms:**
- "MemoryError" or "Out of memory"
- Process killed during embedding

**Solution:**
```bash
# Process files one at a time
python -c "
import os
from src.ingestor import ingest_pdf

for filename in os.listdir('data/processed'):
    if not filename.endswith('.json'):
        continue
    
    filepath = f'data/processed/{filename}'
    print(f'Processing: {filename}')
    
    try:
        result = ingest_pdf(filepath)
        print(f'  ✓ {result[\"chunks_created\"]} chunks created')
    except Exception as e:
        print(f'  ✗ Error: {e}')
"

# Or reduce batch size in embedder.py
# Edit src/embedder.py and change BATCH_SIZE to 32 or 16
```

#### Issue 6: Slow Query Performance

**Symptoms:**
- Queries take >5 seconds
- Slower than before migration

**Solution:**
```bash
# Check collection size
python -c "
import chromadb
from src.config import CHROMA_PERSIST_DIR

client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
collection = client.get_collection('irdai_disclosures')

print(f'Collection count: {collection.count()}')
print(f'Expected: 300-600 chunks')

# If count is correct but still slow, check embedding dimension
results = collection.get(limit=1, include=['embeddings'])
if results['embeddings']:
    dim = len(results['embeddings'][0])
    print(f'Embedding dimension: {dim}')
    print(f'Expected: 384')
"

# Rebuild index if needed
python -c "
import chromadb
from src.config import CHROMA_PERSIST_DIR

client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)

# Delete and recreate collection
client.delete_collection('irdai_disclosures')
print('Collection deleted - re-run ingestion')
"

python scripts/ingest_all.py
```

---

## Post-Migration Checklist

After completing migration and verification:

- [ ] **Backup successful** - ChromaDB and config files backed up
- [ ] **Configuration updated** - PAGE_WISE_CHUNKING=True in .env
- [ ] **Re-indexing complete** - All PDFs processed without errors
- [ ] **Chunk count verified** - 300-600 chunks (70-80% reduction)
- [ ] **Metadata complete** - All required fields present
- [ ] **Queries working** - Test queries return relevant results
- [ ] **Streamlit app tested** - UI works with new chunks
- [ ] **Performance measured** - Benchmarks show expected improvements
- [ ] **Documentation updated** - Migration notes recorded
- [ ] **Backup retention** - Keep backup for at least 30 days
- [ ] **Team notified** - Inform users of migration completion

---

## Support and Resources

### Documentation

- **README.md** - General system documentation
- **PAGE_WISE_CHUNKING_SUMMARY.md** - Feature implementation summary
- **SETUP_GUIDE.md** - Initial setup instructions
- **Design Document** - `.kiro/specs/page-wise-chunking/design.md`
- **Requirements** - `.kiro/specs/page-wise-chunking/requirements.md`

### Scripts

- **scripts/ingest_all.py** - Re-index all PDFs
- **scripts/test_query.py** - Test query functionality
- **scripts/verify_setup.py** - Verify system configuration
- **scripts/test_page_wise_chunking.py** - Test chunking logic

### Contact

For issues or questions:
1. Check troubleshooting section above
2. Review error logs in `logs/app.log`
3. Consult design document for technical details
4. Create issue report with error details

---

## Appendix: Migration Checklist

Print this checklist and mark off each step:

### Pre-Migration
- [ ] Python environment activated
- [ ] Dependencies installed
- [ ] Disk space verified (500MB+)
- [ ] Services stopped
- [ ] Backup destination prepared

### Backup
- [ ] ChromaDB backed up
- [ ] Pre-migration stats exported
- [ ] Configuration files backed up
- [ ] Backup verified

### Migration
- [ ] .env updated (PAGE_WISE_CHUNKING=True)
- [ ] Configuration verified
- [ ] Old ChromaDB cleared
- [ ] Re-indexing completed
- [ ] Migration success verified

### Verification
- [ ] Chunk count in range (300-600)
- [ ] Query retrieval tested
- [ ] Streamlit app tested
- [ ] Metadata completeness verified
- [ ] Performance benchmarks run

### Post-Migration
- [ ] Documentation updated
- [ ] Team notified
- [ ] Backup retention set (30 days)
- [ ] Migration notes recorded

---

**Migration Guide Version:** 1.0  
**Last Updated:** 2025-01-11  
**Compatible With:** Page-Wise Chunking v1.0+
