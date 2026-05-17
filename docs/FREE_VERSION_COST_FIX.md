# Free Version Cost Issues - Fixed

## Problem
User was getting charged even when using the "free" version of the app.

## Root Causes Found

### 1. **PAID Embedding Model** ❌ (MAIN ISSUE)
- **Location**: `.env` line 39
- **Issue**: Using `openai/text-embedding-3-small` which is a **PAID** model
- **Impact**: Every search query generates embeddings, causing continuous charges
- **Fix**: Changed to `google/text-embedding-004` which is **FREE**

### 2. **Multi-Query Generation** ❌
- **Location**: `.env` line 73, `rag_pipeline.py` line 722
- **Issue**: `ENABLE_MULTI_QUERY=True` generates 2-3 alternative queries for complex questions
- **Impact**: Each alternative query = additional LLM call = more costs
- **Fix**: Set `ENABLE_MULTI_QUERY=False`

### 3. **Query Optimization Layer** ⚠️ (Already using free model)
- **Location**: `rag_pipeline.py` line 591
- **Status**: Already configured to use `use_paid=False` with free model
- **Impact**: Minimal - only runs for complex queries and uses free model
- **Action**: No change needed, but added clarifying comments

## Changes Made

### `.env` File Changes:

1. **Embedding Model** (Line 39):
   ```env
   # OLD (PAID):
   EMBEDDING_MODEL=openai/text-embedding-3-small
   EMBEDDING_DIMENSION=1536
   
   # NEW (FREE):
   EMBEDDING_MODEL=google/text-embedding-004
   EMBEDDING_DIMENSION=768
   ```

2. **Multi-Query Generation** (Line 73):
   ```env
   # OLD:
   ENABLE_MULTI_QUERY=True
   
   # NEW:
   ENABLE_MULTI_QUERY=False
   ```

## Important Notes

### ⚠️ You Need to Re-Index Your PDFs!

Because we changed the embedding model from OpenAI (1536 dimensions) to Google (768 dimensions), your existing vector database is **incompatible**.

**You MUST re-ingest all PDFs:**

```bash
# Delete old vector database
rm -rf vectordb/chroma_db

# Re-run PDF ingestion
python scripts/ingest_pdfs.py
```

### Cost Breakdown (Before vs After)

**BEFORE (with paid embedding):**
- Every search: ~$0.0001 per query (embedding cost)
- Complex queries: +$0.001-0.01 (multi-query generation)
- **Estimated**: $0.01-0.05 per session

**AFTER (with free embedding):**
- Every search: $0 (free Google embeddings)
- Complex queries: $0 (multi-query disabled)
- Main answer generation: Uses `openrouter/free` = $0
- **Estimated**: $0 per session ✅

### What Still Uses LLM (Free Model)

1. **Query Optimization** (complex queries only):
   - Uses `openrouter/free` model
   - Small prompt (~500 tokens)
   - Should be free or negligible cost

2. **Answer Generation**:
   - Uses `openrouter/free` for simple queries
   - Uses `openrouter/free` for complex queries (if you select "Free" in UI)
   - Only uses paid model if you explicitly select "Paid" in the UI

## Testing

After making these changes:

1. **Restart the app** (already done)
2. **Re-index PDFs** (required due to embedding model change)
3. **Test a few queries** and monitor OpenRouter dashboard
4. **Verify $0 charges** for embedding and query optimization

## Monitoring Costs

Check your OpenRouter dashboard:
- https://openrouter.ai/activity

Look for:
- `openai/text-embedding-3-small` calls (should be ZERO after fix)
- `openrouter/free` calls (should be all queries)
- Any `anthropic/claude-sonnet-4-5` calls (should only appear if you select "Paid" model in UI)

## Summary

✅ **Fixed**: Embedding model changed to free Google model  
✅ **Fixed**: Multi-query generation disabled  
✅ **Verified**: Query optimization already using free model  
⚠️ **Action Required**: Re-index PDFs with new embedding model  

Your app should now be **100% free** when using the free model option!
