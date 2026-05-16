# RAG Process Check - Summary

**Date:** May 17, 2026  
**Status:** 🟡 **Operational but Incomplete**

---

## Quick Status

| Component | Status | Details |
|-----------|--------|---------|
| **Configuration** | ✅ Good | All settings properly configured |
| **Vector Database** | ⚠️ Partial | Only 1/6 companies indexed |
| **Retrieval** | ✅ Working | Good similarity scores (0.59-0.62) |
| **Embeddings** | ✅ Working | OpenAI text-embedding-3-small |
| **LLM Integration** | ✅ Working | Claude models configured |
| **PDF Files** | ⚠️ Incomplete | 5/6 files not indexed |

---

## Current State

### ✅ What's Working

1. **RAG Pipeline Architecture**
   - Clean modular design
   - Page-wise chunking enabled (optimal strategy)
   - Multi-query expansion for complex queries
   - Intelligent free/paid model selection
   - Response caching for performance

2. **Retrieval Quality**
   - Test query "total premium" returns 5 relevant chunks
   - Similarity scores: 0.589 - 0.616 (good range)
   - Proper metadata extraction (company, quarter, FY, section)
   - Fast retrieval (<500ms)

3. **Configuration**
   - API key set correctly
   - Embedding model: `openai/text-embedding-3-small`
   - Free model: `anthropic/claude-3-haiku:free`
   - Paid model: `anthropic/claude-sonnet-4-5`
   - Page-wise chunking enabled

### ⚠️ What Needs Attention

1. **Missing Companies (CRITICAL)**
   - **Indexed:** 1/6 companies (Aditya Birla only)
   - **Not Indexed:** 5 companies
     - Bhartiaxa
     - Edelweiss
     - ICICI Pru Life
     - Shriram Insurance
     - Tata AIA
   
   **Impact:** Cross-company queries will fail or return incomplete results

2. **Similarity Threshold**
   - Current: 0.20 (very permissive)
   - Recommendation: Increase to 0.35 for better relevance
   - Fallback: 0.10 (too low, should be 0.20)

---

## RAG Process Flow

### 1. Ingestion Pipeline ✅

```
PDF → Parse (pdfplumber) → Extract L-pages → Chunk (page-wise) → 
Embed (OpenAI) → Store (ChromaDB)
```

**Current Stats:**
- Total chunks: 85 (should be ~560 for all 6 companies)
- Chunking: Page-wise (1 chunk per page)
- Embedding dimension: 1536D
- Storage: ChromaDB with cosine similarity

### 2. Query Pipeline ✅

```
Question → Refine → Auto-filter → Classify Complexity → 
Multi-query (if complex) → Retrieve → Top-up Companies → 
Assemble Context → LLM → Answer
```

**Key Features:**
- **Query Refinement:** Extracts format instructions, cleans query
- **Auto-filtering:** Detects company/quarter/FY in query
- **Complexity Classification:**
  - Simple: Single company, single metric → Free model, top-k=12
  - Complex: Comparisons, rankings, trends → Paid model, top-k=40
- **Multi-query Expansion:** Generates 3 diverse queries for complex questions
- **Company Top-up:** Ensures all companies represented in results
- **Context Limiting:** Max 120,000 chars to prevent token overflow

### 3. Retrieval Strategy ✅

**Vector Search:**
- Domain prefix: "IRDAI life insurance financial report: "
- Similarity threshold: 0.20 (primary), 0.10 (fallback)
- Top-K: 12 (simple) or 40 (complex)
- Deduplication: By chunk_id for multi-query results

**Metadata Filtering:**
- Company code (e.g., `Aditya_Birla`)
- Quarter (e.g., `Q3`)
- Financial year (e.g., `FY26`)
- Section (e.g., `L-5`, `Revenue Account`)

---

## Test Results

### Retrieval Test: "total premium"

| Rank | Score | Company | Page | Section |
|------|-------|---------|------|---------|
| 1 | 0.616 | Aditya Birla | 38 | Geographical Distribution |
| 2 | 0.613 | Aditya Birla | 37 | Geographical Distribution |
| 3 | 0.611 | Aditya Birla | 8 | L-5 |
| 4 | 0.593 | Aditya Birla | 2 | Revenue Account |
| 5 | 0.589 | Aditya Birla | 75 | Premium by Policy Type |

**Analysis:**
- ✅ Good similarity scores (0.59-0.62)
- ✅ Relevant pages retrieved
- ✅ Diverse sections (not just one page)
- ⚠️ Only Aditya Birla results (expected, only company indexed)

---

## Immediate Actions Required

### 1. Index Remaining Companies (CRITICAL)

```powershell
# Option 1: Ingest all PDFs
python scripts/ingest_all.py

# Option 2: Use Streamlit UI
streamlit run app/streamlit_app.py
# Upload PDFs through the interface
```

**Expected Result:**
- Total chunks: ~560 (85-155 per company)
- All 6 companies indexed
- Cross-company queries working

### 2. Test Cross-Company Query

After indexing all companies:

```powershell
python scripts/test_query.py --q "Compare total premium across all companies in Q3 FY26"
```

**Expected Answer:**
- Should include data from all 6 companies
- Formatted as markdown table
- Sources cited for each company

### 3. Adjust Similarity Threshold (Optional)

Edit `.env`:
```env
SIMILARITY_THRESHOLD=0.35  # More selective (currently 0.20)
```

Test impact:
```powershell
python scripts/diagnose_rag.py
```

---

## Architecture Strengths

### 1. Page-Wise Chunking ✅
- **Benefit:** Complete page context (tables + text together)
- **Impact:** 69% fewer chunks than text-based (1,820 → 560)
- **Result:** Better semantic coherence, no table fragmentation

### 2. Multi-Query Expansion ✅
- **Benefit:** Increases recall for complex queries
- **Impact:** Finds relevant data with different terminology
- **Result:** More comprehensive answers

### 3. Intelligent Model Selection ✅
- **Benefit:** Cost optimization
- **Impact:** Free model for simple, paid for complex
- **Result:** Lower API costs without sacrificing quality

### 4. Company Top-Up ✅
- **Benefit:** Fair representation across companies
- **Impact:** Prevents bias toward specific companies
- **Result:** Complete cross-company analysis

### 5. Response Caching ✅
- **Benefit:** Avoids redundant LLM calls
- **Impact:** Faster responses for repeated queries
- **Result:** Better user experience

---

## Potential Improvements

### 1. Add Reranking (Medium Priority)
**Current:** Single-stage retrieval (embedding similarity only)  
**Improvement:** Add cross-encoder reranking for better relevance  
**Benefit:** 10-20% improvement in answer quality

### 2. Implement Hybrid Search (Medium Priority)
**Current:** Pure vector search  
**Improvement:** Combine vector + keyword (BM25) search  
**Benefit:** Better recall for specific terms and numbers

### 3. Add Evaluation Metrics (High Priority)
**Current:** No automated quality tracking  
**Improvement:** Track retrieval precision/recall, answer accuracy  
**Benefit:** Data-driven optimization

### 4. Query Expansion for Simple Queries (Low Priority)
**Current:** Only complex queries get multi-query expansion  
**Improvement:** Lightweight expansion for simple queries (acronyms)  
**Benefit:** Better handling of terminology variations

### 5. Query Routing (Low Priority)
**Current:** All queries use same pipeline  
**Improvement:** Route to specialized handlers (aggregation, comparison, trend)  
**Benefit:** Better accuracy for specific query types

---

## Configuration Reference

### Current Settings (`.env`)

```env
# API
OPENROUTER_API_KEY=sk-or-xxxxx  ✅ Set

# Chunking
PAGE_WISE_CHUNKING=True          ✅ Optimal
MAX_PAGE_TOKENS=8000             ✅ Good
CHUNK_SIZE=1200                  ⚠️ Not used (page-wise enabled)
CHUNK_OVERLAP=150                ⚠️ Not used (page-wise enabled)

# Retrieval
TOP_K_SIMPLE=12                  ✅ Reasonable
TOP_K_COMPLEX=40                 ✅ Good for comparisons
SIMILARITY_THRESHOLD=0.20        ⚠️ Consider increasing to 0.35

# Embeddings
EMBEDDING_MODEL=openai/text-embedding-3-small  ✅ Good
EMBEDDING_DIMENSION=1536                       ✅ Standard
EMBEDDING_BATCH_SIZE=64                        ✅ Efficient

# LLM
LLM_MODEL_FREE=anthropic/claude-3-haiku:free   ✅ Cost-effective
LLM_MODEL_PAID=anthropic/claude-sonnet-4-5     ✅ High quality
LLM_MAX_TOKENS_SIMPLE=1024                     ✅ Sufficient
LLM_MAX_TOKENS_COMPLEX=4096                    ✅ Good for complex
LLM_MAX_INPUT_CHARS=120000                     ✅ Prevents overflow
LLM_TEMPERATURE=0.2                            ✅ Balanced
```

---

## Diagnostic Commands

### Check System Health
```powershell
python scripts/diagnose_rag.py
```

### Test Query
```powershell
python scripts/test_query.py --q "What is the total premium for Aditya Birla?"
```

### Test with Debug (see retrieved chunks)
```powershell
python scripts/test_query.py --q "What is the total premium?" --debug
```

### Check Database Stats
```powershell
python -c "from src.embedder import get_collection_stats; import json; print(json.dumps(get_collection_stats(), indent=2))"
```

### Test Retrieval
```powershell
python -c "from src.retriever import retrieve; chunks = retrieve('total premium', top_k=5); print(f'Retrieved {len(chunks)} chunks'); [print(f'{i}. Score: {c[\"score\"]:.3f} | {c[\"metadata\"][\"company\"]}') for i, c in enumerate(chunks, 1)]"
```

---

## Files Reference

### Core RAG Components
- `src/rag_pipeline.py` - Main orchestration
- `src/retriever.py` - Vector search and filtering
- `src/embedder.py` - Embedding generation and ChromaDB
- `src/llm_client.py` - LLM API calls
- `src/chunker.py` - Document chunking
- `src/pdf_parser.py` - PDF extraction

### Configuration
- `.env` - Environment variables
- `src/config.py` - Configuration loader

### Scripts
- `scripts/ingest_all.py` - Batch ingestion
- `scripts/test_query.py` - CLI query testing
- `scripts/diagnose_rag.py` - System diagnostics

### Documentation
- `docs/RAG_PROCESS_ANALYSIS.md` - Detailed analysis
- `docs/RAG_PROCESS_SUMMARY.md` - This file
- `docs/archive/RAG_ACCURACY_FIX_COMPLETE.md` - L-page fix details
- `docs/archive/PAGE_WISE_CHUNKING_SUMMARY.md` - Chunking strategy

---

## Summary

### Overall Assessment: 🟡 **Good Architecture, Needs Data**

**Strengths:**
- ✅ Modern RAG architecture with best practices
- ✅ Page-wise chunking for semantic coherence
- ✅ Intelligent model selection for cost optimization
- ✅ Multi-query expansion for complex queries
- ✅ Good retrieval quality (0.59-0.62 similarity scores)

**Issues:**
- ⚠️ Only 1/6 companies indexed (critical)
- ⚠️ Similarity threshold may be too low
- ℹ️ No reranking or hybrid search
- ℹ️ No evaluation metrics

**Next Steps:**
1. **Index all 6 companies** (critical - do now)
2. Test cross-company queries
3. Adjust similarity threshold to 0.35
4. Add evaluation metrics
5. Consider reranking for better relevance

**Time to Fix:** ~10 minutes (just run `python scripts/ingest_all.py`)

---

**Report Generated:** May 17, 2026  
**Diagnostic Tool:** `scripts/diagnose_rag.py`  
**Status:** Ready for production after indexing remaining companies
