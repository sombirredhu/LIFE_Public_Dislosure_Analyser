# RAG Process Flow Diagram

## Overview

This document provides a visual representation of the RAG (Retrieval-Augmented Generation) process in your IRDAI PDF analyzer.

---

## 1. Ingestion Pipeline (PDF → Vector DB)

```
┌─────────────────────────────────────────────────────────────────────┐
│                         INGESTION PIPELINE                          │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────┐
│  PDF Files   │  (data/pdfs/*.pdf)
│  6 Companies │
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│  PDF Parser (src/pdf_parser.py)                                  │
│  • Extract text with pdfplumber                                  │
│  • Extract tables (preserve structure)                           │
│  • Identify L-page sections from index                           │
│  • Extract metadata: company, quarter, FY                        │
└──────┬───────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│  Parsed Document (JSON)                                          │
│  {                                                               │
│    "company": "Aditya Birla",                                    │
│    "quarter": "Q3", "fy": "FY26",                                │
│    "pages": [                                                    │
│      {                                                           │
│        "page_number": 1,                                         │
│        "page_label": "L-1",                                      │
│        "section": "Revenue Account",                             │
│        "tables": [...],                                          │
│        "text_blocks": [...]                                      │
│      }                                                           │
│    ]                                                             │
│  }                                                               │
└──────┬───────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│  Chunker (src/chunker.py)                                        │
│  Strategy: PAGE_WISE_CHUNKING = True                             │
│                                                                  │
│  For each page:                                                  │
│    1. Combine all tables + text from page                       │
│    2. Check token limit (8000 tokens)                           │
│    3. If too large, split intelligently:                        │
│       • Keep tables intact                                      │
│       • Split text at sentence boundaries                       │
│    4. Add metadata: page_number, section, L-page                │
│                                                                  │
│  Result: 1 chunk per page (or multiple if page is large)        │
└──────┬───────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│  Chunks (List of Dicts)                                          │
│  [                                                               │
│    {                                                             │
│      "text": "FORM L-1-A-RA Revenue Account...",                │
│      "metadata": {                                               │
│        "chunk_id": "Aditya_Birla_Q3_FY26_page1",                │
│        "company": "Aditya Birla",                                │
│        "company_code": "Aditya_Birla",                           │
│        "quarter": "Q3", "fy": "FY26",                            │
│        "page_number": 1,                                         │
│        "page_label": "L-1",                                      │
│        "section": "Revenue Account",                             │
│        "content_type": "page",                                   │
│        "table_count": 2,                                         │
│        "text_block_count": 3                                     │
│      }                                                           │
│    },                                                            │
│    ...                                                           │
│  ]                                                               │
└──────┬───────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│  Embedder (src/embedder.py)                                      │
│  • Generate embeddings via OpenRouter API                       │
│  • Model: openai/text-embedding-3-small                         │
│  • Dimension: 1536D                                             │
│  • Batch size: 64 texts per request                             │
│  • Retry logic for rate limits                                  │
└──────┬───────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│  ChromaDB (vectordb/chroma_db)                                   │
│  Collection: insurance_pd_reports                                │
│  • Stores: embeddings (1536D vectors)                           │
│  • Stores: text (original chunk content)                        │
│  • Stores: metadata (company, quarter, FY, page, section)       │
│  • Similarity: Cosine distance                                  │
│  • Index: HNSW (fast approximate search)                        │
│                                                                  │
│  Current: 85 chunks (1 company)                                  │
│  Expected: 560 chunks (6 companies)                              │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. Query Pipeline (Question → Answer)

```
┌─────────────────────────────────────────────────────────────────────┐
│                          QUERY PIPELINE                             │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────┐
│ User Question│  "Compare total premium across all companies in Q3 FY26"
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│  Query Refinement (src/rag_pipeline.py)                          │
│  • Extract format instructions: "table", "bullet", "detailed"    │
│  • Clean search query: remove format keywords                    │
│  • Sanitize: strip control chars, limit to 2000 chars           │
│                                                                  │
│  Input:  "Compare total premium in table format"                │
│  Output: search_query = "Compare total premium"                 │
│          format_instruction = "Present in table format"         │
└──────┬───────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│  Auto-Filter Extraction                                          │
│  • Detect company names in query                                 │
│  • Extract quarter mentions (Q1, Q2, Q3, Q4)                     │
│  • Extract FY mentions (FY25, FY26)                              │
│                                                                  │
│  Example: "Aditya Birla Q3 FY26" →                              │
│    filters = {                                                   │
│      "company_code": "Aditya_Birla",                             │
│      "quarter": "Q3",                                            │
│      "fy": "FY26"                                                │
│    }                                                             │
└──────┬───────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│  Complexity Classification                                       │
│                                                                  │
│  Simple Query:                                                   │
│    • Single company, single metric                              │
│    • Example: "What is Aditya Birla's GWP?"                     │
│    → Use free model, top_k=12, single query                     │
│                                                                  │
│  Complex Query:                                                  │
│    • Comparisons: "compare", "vs", "versus"                     │
│    • Rankings: "highest", "lowest", "top", "rank"               │
│    • Multi-company: mentions multiple companies                 │
│    • Trends: "growth", "trend", "change"                        │
│    → Use paid model, top_k=40, multi-query expansion            │
└──────┬───────────────────────────────────────────────────────────┘
       │
       ├─────────────────┬─────────────────┐
       │                 │                 │
       ▼                 ▼                 ▼
   [Simple]         [Complex]         [Complex]
       │                 │                 │
       │                 ▼                 │
       │    ┌────────────────────────┐    │
       │    │ Multi-Query Generation │    │
       │    │ (LLM-based expansion)  │    │
       │    │                        │    │
       │    │ Input: "Compare GWP"   │    │
       │    │ Output:                │    │
       │    │  1. "Compare GWP"      │    │
       │    │  2. "GWP comparison"   │    │
       │    │  3. "Gross Written     │    │
       │    │     Premium ranking"   │    │
       │    └────────┬───────────────┘    │
       │             │                    │
       └─────────────┴────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────────┐
│  Retrieval (src/retriever.py)                                    │
│                                                                  │
│  For each query:                                                 │
│    1. Add domain prefix: "IRDAI life insurance financial        │
│       report: " + query                                          │
│    2. Generate embedding via OpenRouter API                     │
│    3. Query ChromaDB with:                                      │
│       • Embedding vector (1536D)                                │
│       • Filters (company, quarter, FY)                          │
│       • Top-K (12 for simple, 40 for complex)                   │
│       • Similarity threshold: 0.20 (fallback: 0.10)             │
│    4. Return chunks with score >= threshold                     │
│                                                                  │
│  Multi-query: Deduplicate by chunk_id, keep highest score       │
└──────┬───────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│  Retrieved Chunks                                                │
│  [                                                               │
│    {                                                             │
│      "text": "...",                                              │
│      "metadata": {...},                                          │
│      "score": 0.616                                              │
│    },                                                            │
│    ...                                                           │
│  ]                                                               │
└──────┬───────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│  Company Top-Up (Complex queries only)                           │
│  • Check which companies are represented in results              │
│  • For missing companies:                                        │
│    - Fetch 2 additional chunks per company                      │
│    - Use same query, filter by company_code                     │
│  • Append to results                                             │
│                                                                  │
│  Ensures all indexed companies appear in cross-company queries   │
└──────┬───────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│  Context Assembly                                                │
│  • Limit total chars to 120,000 (prevent token overflow)        │
│  • Format each chunk:                                            │
│    "Source: {file} | Company: {company} | Period: {period} |    │
│     Section: {section}                                           │
│                                                                  │
│     {chunk_text}"                                                │
│  • Join with separator: "\n\n---\n\n"                            │
│  • Add format instruction if present                             │
└──────┬───────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│  LLM Generation (src/llm_client.py)                              │
│                                                                  │
│  System Prompt:                                                  │
│    "You are a financial analyst specializing in Indian life     │
│     insurance. Answer based ONLY on excerpts. Rules:            │
│     1. Mention company, quarter, FY                              │
│     2. Use markdown tables for comparisons                       │
│     3. Monetary values in ₹ Cr                                   │
│     4. Cite sources"                                             │
│                                                                  │
│  User Message:                                                   │
│    "Question: {question}                                         │
│     Format Instruction: {format_instruction}                     │
│                                                                  │
│     Excerpts:                                                    │
│     {context}"                                                   │
│                                                                  │
│  Model Selection:                                                │
│    • Simple: anthropic/claude-3-haiku:free (max 1024 tokens)    │
│    • Complex: anthropic/claude-sonnet-4-5 (max 4096 tokens)     │
│                                                                  │
│  Temperature: 0.2 (balanced)                                     │
│  Timeout: 30 seconds                                             │
│  Retry: 3 attempts with exponential backoff                      │
└──────┬───────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│  Response                                                        │
│  {                                                               │
│    "answer": "Based on Q3 FY26 data:\n\n| Company | Total        │
│               Premium (₹ Cr) |\n|---------|------------------|\n│
│               | Aditya Birla | 5,234.56 |\n...",               │
│    "sources": ["Aditya_Birla_Q3_FY26.pdf", ...],                │
│    "chunks_used": 15,                                            │
│    "confidence": "high",                                         │
│    "model_used": "anthropic/claude-sonnet-4-5"                   │
│  }                                                               │
└──────┬───────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│  Response Cache (LRU, max 100 entries)                           │
│  • Cache key: hash(question + filters + top_k + models)          │
│  • Avoids redundant LLM calls                                    │
│  • Evicts oldest when full                                       │
└──────────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────┐
│ Display to   │
│ User         │
└──────────────┘
```

---

## 3. Key Decision Points

### A. Chunking Strategy Decision

```
┌─────────────────────────────────────┐
│ PAGE_WISE_CHUNKING = True?          │
└────────┬────────────────────────────┘
         │
    ┌────┴────┐
    │         │
   Yes       No
    │         │
    ▼         ▼
┌─────────┐ ┌──────────────┐
│ Page-   │ │ Text-based   │
│ wise    │ │ Chunking     │
│         │ │              │
│ • 1     │ │ • Split text │
│   chunk │ │   into 1200  │
│   per   │ │   char       │
│   page  │ │   chunks     │
│ • Keep  │ │ • 150 char   │
│   tables│ │   overlap    │
│   +text │ │ • Fragment   │
│   together│ │   tables   │
│ • 560   │ │ • 1820       │
│   chunks│ │   chunks     │
│         │ │              │
│ ✅ BETTER│ │ ⚠️ LEGACY   │
└─────────┘ └──────────────┘
```

### B. Query Complexity Decision

```
┌─────────────────────────────────────┐
│ Classify Query Complexity           │
└────────┬────────────────────────────┘
         │
    ┌────┴────┐
    │         │
 Simple    Complex
    │         │
    ▼         ▼
┌─────────┐ ┌──────────────┐
│ Simple  │ │ Complex      │
│ Query   │ │ Query        │
│         │ │              │
│ • Free  │ │ • Paid model │
│   model │ │   (Claude    │
│   (Haiku│ │   Sonnet)    │
│   free) │ │ • Top-K: 40  │
│ • Top-K:│ │ • Multi-     │
│   12    │ │   query      │
│ • Single│ │   expansion  │
│   query │ │ • Company    │
│         │ │   top-up     │
│         │ │              │
│ Fast &  │ │ Thorough &   │
│ Cheap   │ │ Accurate     │
└─────────┘ └──────────────┘

Triggers for Complex:
• Keywords: compare, vs, versus, rank, highest, lowest
• Multiple companies mentioned
• Superlatives without specific company
```

### C. Retrieval Threshold Decision

```
┌─────────────────────────────────────┐
│ Query ChromaDB                      │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ Filter by similarity >= 0.20        │
└────────┬────────────────────────────┘
         │
    ┌────┴────┐
    │         │
 Found     Not Found
 Results   (empty)
    │         │
    ▼         ▼
┌─────────┐ ┌──────────────┐
│ Return  │ │ Retry with   │
│ Chunks  │ │ Fallback     │
│         │ │ Threshold    │
│         │ │ (0.10)       │
│         │ │              │
│         │ │ More         │
│         │ │ permissive   │
└─────────┘ └──────┬───────┘
                   │
              ┌────┴────┐
              │         │
           Found     Not Found
              │         │
              ▼         ▼
         ┌─────────┐ ┌──────────┐
         │ Return  │ │ Return   │
         │ Chunks  │ │ Empty    │
         └─────────┘ └──────────┘
```

---

## 4. Data Flow Summary

### Ingestion (One-time per PDF)
```
PDF (5-10 MB) 
  → Parsed JSON (1-2 MB)
  → Chunks (85-155 per PDF)
  → Embeddings (1536D vectors)
  → ChromaDB (persistent storage)

Time: ~30-60 seconds per PDF
```

### Query (Per user question)
```
Question (text)
  → Refined query (text)
  → Embedding (1536D vector)
  → Similarity search (ChromaDB)
  → Retrieved chunks (5-40 chunks)
  → Context (10-100 KB text)
  → LLM API call
  → Answer (text)

Time: ~2-5 seconds per query
```

---

## 5. Performance Characteristics

### Ingestion Performance
| Metric | Value |
|--------|-------|
| PDF parsing | ~5-10 sec/PDF |
| Chunking | ~1-2 sec/PDF |
| Embedding generation | ~10-20 sec/PDF |
| ChromaDB insertion | ~1-2 sec/PDF |
| **Total per PDF** | **~20-35 sec** |

### Query Performance
| Metric | Simple | Complex |
|--------|--------|---------|
| Query refinement | <100ms | <100ms |
| Multi-query gen | N/A | ~1-2 sec |
| Embedding gen | ~200ms | ~500ms |
| ChromaDB search | ~100ms | ~300ms |
| Company top-up | N/A | ~500ms |
| LLM generation | ~1-2 sec | ~3-5 sec |
| **Total** | **~2-3 sec** | **~5-8 sec** |

### Storage
| Metric | Value |
|--------|-------|
| Chunk size | 500-8000 chars |
| Embedding size | 1536D × 4 bytes = 6 KB |
| Metadata size | ~500 bytes |
| **Per chunk** | **~6.5 KB** |
| **560 chunks** | **~3.6 MB** |

---

## 6. Error Handling

```
┌─────────────────────────────────────┐
│ Error Handling at Each Stage        │
└─────────────────────────────────────┘

PDF Parsing Error
  → Log error
  → Return error status
  → Skip file, continue with others

Chunking Error
  → Log error
  → Return empty chunks
  → Skip file

Embedding API Error
  → Retry 3 times with exponential backoff
  → If rate limit: wait and retry
  → If timeout: retry
  → If persistent error: raise exception

ChromaDB Error
  → Log error
  → Retry without filters (if filter issue)
  → Return empty results if persistent

LLM API Error
  → Retry 3 times with exponential backoff
  → If rate limit: wait and retry
  → If timeout: retry
  → If persistent error: raise exception

No Results Found
  → Return "No relevant info found" message
  → Confidence: "none"
  → Suggest checking filters or rephrasing
```

---

## 7. Caching Strategy

```
┌─────────────────────────────────────┐
│ Two-Level Caching                   │
└─────────────────────────────────────┘

Level 1: Response Cache
  • Cache key: hash(question + filters + top_k + models)
  • Max size: 100 entries
  • Eviction: LRU (Least Recently Used)
  • Benefit: Avoid redundant LLM calls
  • Hit rate: ~20-30% for repeated queries

Level 2: Metadata Cache
  • Cache: List of all chunk metadata
  • TTL: 30 seconds
  • Invalidation: On new ingestion
  • Benefit: Fast company/quarter/FY lookups
  • Used by: get_indexed_companies(), get_available_quarters()
```

---

## Summary

This RAG system implements a **two-stage pipeline**:

1. **Ingestion**: PDF → Parse → Chunk → Embed → Store
2. **Query**: Question → Refine → Retrieve → Generate → Answer

**Key Features:**
- ✅ Page-wise chunking for semantic coherence
- ✅ Multi-query expansion for complex queries
- ✅ Intelligent model selection (free vs paid)
- ✅ Company top-up for fair representation
- ✅ Response caching for performance
- ✅ Robust error handling and retries

**Current Status:**
- ⚠️ Only 1/6 companies indexed
- ✅ All components working correctly
- ✅ Good retrieval quality (0.59-0.62 scores)

**Next Action:**
```powershell
python scripts/ingest_all.py
```

This will index all 6 companies and enable full cross-company analysis.
