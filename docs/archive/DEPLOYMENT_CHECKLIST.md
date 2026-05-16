# Page-Wise Chunking Deployment Checklist

## Overview

This checklist guides the deployment of the page-wise chunking feature to production. The feature transforms the chunking strategy from text-based (~1,820 chunks) to page-wise (~300-400 chunks), improving semantic coherence and retrieval accuracy.

**Estimated Deployment Time:** 30-45 minutes  
**Rollback Time (if needed):** 15-20 minutes

---

## Pre-Deployment Phase

### 1. Backup Current System State

**Priority:** CRITICAL  
**Estimated Time:** 5-10 minutes

- [ ] **Backup ChromaDB Collection**
  ```bash
  # Create backup directory with timestamp
  $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
  $backupDir = ".\backups\chromadb_backup_$timestamp"
  New-Item -ItemType Directory -Path $backupDir -Force
  
  # Copy ChromaDB directory
  Copy-Item -Path ".\vectordb\chroma_db" -Destination "$backupDir\chroma_db" -Recurse
  
  # Verify backup
  Write-Host "Backup created at: $backupDir"
  Get-ChildItem $backupDir -Recurse | Measure-Object | Select-Object -ExpandProperty Count
  ```

- [ ] **Document Current Collection Stats**
  ```bash
  # Run stats collection
  python scripts/ingest_all.py
  
  # Expected output to document:
  # - Total Chunks: ~1,820
  # - Unique Files: 6
  # - Chunks by Company: (record all counts)
  ```
  
  **Record in deployment log:**
  - Total chunks before deployment: ___________
  - Unique files: ___________
  - Companies indexed: ___________
  - Date/Time: ___________

- [ ] **Backup .env Configuration**
  ```bash
  Copy-Item -Path ".\.env" -Destination ".\.env.backup_$timestamp"
  ```

- [ ] **Verify Backup Integrity**
  ```bash
  # Check backup size
  $originalSize = (Get-ChildItem ".\vectordb\chroma_db" -Recurse | Measure-Object -Property Length -Sum).Sum
  $backupSize = (Get-ChildItem "$backupDir\chroma_db" -Recurse | Measure-Object -Property Length -Sum).Sum
  
  if ($originalSize -eq $backupSize) {
      Write-Host "✓ Backup verified successfully"
  } else {
      Write-Host "✗ Backup size mismatch - DO NOT PROCEED"
  }
  ```

### 2. Pre-Deployment Testing

**Priority:** HIGH  
**Estimated Time:** 10-15 minutes

- [ ] **Run Full Test Suite**
  ```bash
  # Activate virtual environment
  .\.venv\Scripts\Activate.ps1
  
  # Run all tests
  pytest tests/ -v
  
  # Expected: All tests pass
  ```

- [ ] **Verify System Dependencies**
  ```bash
  # Check Python version
  python --version  # Should be 3.8+
  
  # Verify required packages
  pip list | Select-String "sentence-transformers|chromadb|pypdf"
  ```

- [ ] **Check Disk Space**
  ```bash
  # Ensure at least 500MB free space
  Get-PSDrive C | Select-Object Used,Free
  ```

- [ ] **Verify PDF Files Present**
  ```bash
  Get-ChildItem ".\data\pdfs\*.pdf" | Measure-Object | Select-Object -ExpandProperty Count
  # Expected: 6 PDF files
  ```

### 3. Review Deployment Plan

**Priority:** MEDIUM  
**Estimated Time:** 5 minutes

- [ ] **Review Requirements 4.1 and 4.2**
  - Requirement 4.1: Ingestor supports force_reindex parameter ✓
  - Requirement 4.2: Existing chunks deleted before creating new chunks ✓

- [ ] **Confirm Deployment Window**
  - Scheduled time: ___________
  - System downtime acceptable: Yes / No
  - Users notified: Yes / No

- [ ] **Identify Rollback Trigger Conditions**
  - Retrieval accuracy drops > 10%
  - Processing errors on > 5% of pages
  - Performance degradation > 50%
  - Critical metadata missing

---

## Deployment Phase

### 4. Update Configuration

**Priority:** CRITICAL  
**Estimated Time:** 2 minutes

- [ ] **Update .env File**
  
  Run the deployment script:
  ```bash
  .\scripts\deploy_page_wise_chunking.ps1
  ```
  
  Or manually add these lines to `.env`:
  ```bash
  # ─────────────────────────────────────────
  # PAGE-WISE CHUNKING SETTINGS
  # ─────────────────────────────────────────
  PAGE_WISE_CHUNKING=True
  MAX_PAGE_TOKENS=8000
  ```

- [ ] **Verify Configuration Loaded**
  ```bash
  python -c "from src.config import PAGE_WISE_CHUNKING, MAX_PAGE_TOKENS; print(f'PAGE_WISE_CHUNKING={PAGE_WISE_CHUNKING}'); print(f'MAX_PAGE_TOKENS={MAX_PAGE_TOKENS}')"
  
  # Expected output:
  # PAGE_WISE_CHUNKING=True
  # MAX_PAGE_TOKENS=8000
  ```

### 5. Re-Index with Page-Wise Chunking

**Priority:** CRITICAL  
**Estimated Time:** 5-10 minutes

- [ ] **Start Re-Indexing Process**
  ```bash
  # Run with force flag to re-index all PDFs
  python scripts/ingest_all.py --force
  
  # Monitor output for:
  # - Processing progress
  # - Any error messages
  # - Final chunk count (target: 300-400)
  ```

- [ ] **Monitor Processing Logs**
  ```bash
  # In separate terminal, tail the log file
  Get-Content ".\logs\app.log" -Wait -Tail 50
  
  # Watch for:
  # - "[CHUNKER] Using page-wise chunking strategy"
  # - "[CHUNKER] Created X chunks from Y pages"
  # - Any ERROR or WARNING messages
  ```

- [ ] **Record Re-Indexing Results**
  
  **Deployment Log:**
  - Total files processed: ___________
  - Successfully ingested: ___________
  - Errors: ___________
  - Total chunks created: ___________ (target: 300-400)
  - Processing time: ___________

### 6. Verify Deployment Success

**Priority:** CRITICAL  
**Estimated Time:** 5 minutes

- [ ] **Check Chunk Count Reduction**
  ```bash
  python -c "from src.embedder import get_collection_stats; stats = get_collection_stats(); print(f'Total Chunks: {stats[\"total_chunks\"]}'); print(f'Expected: 300-400'); print(f'Reduction: {((1820 - stats[\"total_chunks\"]) / 1820 * 100):.1f}%')"
  
  # Expected: 75-80% reduction from ~1,820 chunks
  ```

- [ ] **Verify All Companies Indexed**
  ```bash
  python -c "from src.embedder import get_collection_stats; stats = get_collection_stats(); print('Companies:', list(stats['chunks_by_company'].keys())); print('Count:', len(stats['chunks_by_company']))"
  
  # Expected: 6 companies
  ```

- [ ] **Check for Processing Errors**
  ```bash
  # Search logs for errors
  Select-String -Path ".\logs\app.log" -Pattern "ERROR|rejected" | Select-Object -Last 20
  
  # Expected: No critical errors
  # Acceptable: < 1% of pages rejected due to unsplittable content
  ```

---

## Post-Deployment Validation

### 7. Functional Testing

**Priority:** CRITICAL  
**Estimated Time:** 10-15 minutes

- [ ] **Test Query Retrieval**
  ```bash
  # Run test queries
  python scripts/test_query.py --q "What is the premium income for HDFC Life in Q1 FY25?"
  python scripts/test_query.py --q "Compare claims paid across all companies"
  python scripts/test_query.py --q "Show balance sheet for ICICI Prudential"
  
  # Verify:
  # - Queries return relevant results
  # - Complete tables retrieved (not fragmented)
  # - Response time acceptable (< 5 seconds)
  ```

- [ ] **Verify Metadata Completeness**
  ```bash
  python scripts/validate_metadata.py
  
  # Expected: All required fields present
  # - company, company_code, quarter, fy
  # - page_number, page_label, section
  # - chunk_id format: {company_code}_{quarter}_{fy}_page{page_number}
  # - content_type: "page"
  # - table_count, text_block_count
  # - is_split, total_parts (if split), part_number (if split)
  ```

- [ ] **Test Streamlit UI**
  ```bash
  # Launch UI
  streamlit run app/streamlit_app.py
  
  # Manual testing:
  # 1. Submit test query
  # 2. Verify results display correctly
  # 3. Check retrieved chunks show complete page content
  # 4. Test filtering by company/quarter
  # 5. Verify no UI errors
  ```

### 8. Performance Validation

**Priority:** HIGH  
**Estimated Time:** 5 minutes

- [ ] **Measure Query Response Time**
  ```bash
  # Run performance test
  Measure-Command { python scripts/test_query.py --q "What is the premium income for HDFC Life?" }
  
  # Expected: < 5 seconds total
  ```

- [ ] **Check Processing Time**
  ```bash
  # Review logs for processing time per document
  Select-String -Path ".\logs\app.log" -Pattern "Processing time" | Select-Object -Last 10
  
  # Expected: < 5 seconds per 50-page PDF
  ```

- [ ] **Verify Memory Usage**
  ```bash
  # Check ChromaDB size
  $dbSize = (Get-ChildItem ".\vectordb\chroma_db" -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB
  Write-Host "ChromaDB Size: $([math]::Round($dbSize, 2)) MB"
  
  # Expected: ~50-100 MB for 6 companies
  ```

### 9. Quality Assurance

**Priority:** HIGH  
**Estimated Time:** 5-10 minutes

- [ ] **Compare Retrieval Quality**
  
  **Test Query 1:** "What is the total premium income?"
  - [ ] Results include complete tables (not fragmented)
  - [ ] All relevant companies retrieved
  - [ ] Page labels (L-pages) correctly identified
  
  **Test Query 2:** "Show claims data for Q1 FY25"
  - [ ] Complete claims tables retrieved
  - [ ] Context preserved (headers + data rows together)
  - [ ] Multiple companies compared correctly
  
  **Test Query 3:** "What is the balance sheet total?"
  - [ ] Complete balance sheet page retrieved
  - [ ] All line items present
  - [ ] Calculations verifiable

- [ ] **Verify L-Page Alignment**
  ```bash
  # Check that chunk page_labels match expected L-pages
  python -c "
  from src.embedder import get_chroma_client
  client = get_chroma_client()
  collection = client.get_collection('insurance_pd_reports')
  results = collection.get(limit=10, include=['metadatas'])
  for meta in results['metadatas']:
      print(f\"Page {meta['page_number']}: {meta['page_label']} - {meta['section']}\")
  "
  
  # Verify: L-page labels match section types
  # L-1: Revenue Account
  # L-5: Claims
  # L-12: Balance Sheet
  # etc.
  ```

- [ ] **Check for Data Loss**
  ```bash
  # Verify all source files still indexed
  python -c "
  from src.embedder import get_collection_stats
  stats = get_collection_stats()
  print(f\"Unique Files: {stats['unique_files']}\")
  print(f\"Expected: 6\")
  if stats['unique_files'] == 6:
      print('✓ No data loss')
  else:
      print('✗ WARNING: Files missing!')
  "
  ```

### 10. Documentation Update

**Priority:** MEDIUM  
**Estimated Time:** 2 minutes

- [ ] **Update Deployment Log**
  
  Record in `DEPLOYMENT_LOG.md`:
  ```markdown
  ## Deployment: Page-Wise Chunking
  
  **Date:** [YYYY-MM-DD HH:MM]
  **Deployed By:** [Name]
  **Status:** SUCCESS / FAILED
  
  ### Pre-Deployment State
  - Total Chunks: [number]
  - Unique Files: [number]
  - Companies: [list]
  
  ### Post-Deployment State
  - Total Chunks: [number]
  - Chunk Reduction: [percentage]%
  - Processing Time: [seconds]
  - Errors: [count]
  
  ### Validation Results
  - Query Testing: PASS / FAIL
  - Metadata Validation: PASS / FAIL
  - Performance: PASS / FAIL
  - Quality Assurance: PASS / FAIL
  
  ### Issues Encountered
  [List any issues and resolutions]
  
  ### Rollback Required
  YES / NO
  ```

- [ ] **Update System Status**
  - [ ] Mark deployment as complete in project tracker
  - [ ] Notify team of successful deployment
  - [ ] Update README.md if needed

---

## Rollback Procedure (If Needed)

**Use this section ONLY if validation fails or critical issues are found.**

### Rollback Trigger Conditions

Execute rollback if ANY of the following occur:
- ✗ Retrieval accuracy drops > 10% compared to baseline
- ✗ Processing errors on > 5% of pages
- ✗ Performance degradation > 50%
- ✗ Critical metadata missing from chunks
- ✗ Query results incomplete or incorrect
- ✗ System instability or crashes

### Rollback Steps

**Priority:** CRITICAL  
**Estimated Time:** 15-20 minutes

1. [ ] **Stop All Running Processes**
   ```bash
   # Stop Streamlit if running
   # Press Ctrl+C in terminal
   
   # Verify no Python processes using ChromaDB
   Get-Process python | Stop-Process -Force
   ```

2. [ ] **Revert .env Configuration**
   ```bash
   # Option 1: Restore from backup
   Copy-Item -Path ".\.env.backup_$timestamp" -Destination ".\.env" -Force
   
   # Option 2: Manually set to False
   # Edit .env and change:
   # PAGE_WISE_CHUNKING=False
   ```

3. [ ] **Restore ChromaDB from Backup**
   ```bash
   # Remove current ChromaDB
   Remove-Item -Path ".\vectordb\chroma_db" -Recurse -Force
   
   # Restore from backup
   Copy-Item -Path "$backupDir\chroma_db" -Destination ".\vectordb\chroma_db" -Recurse
   
   # Verify restoration
   python -c "from src.embedder import get_collection_stats; stats = get_collection_stats(); print(f'Total Chunks: {stats[\"total_chunks\"]}')"
   # Expected: ~1,820 chunks (original count)
   ```

4. [ ] **Verify Rollback Success**
   ```bash
   # Test query
   python scripts/test_query.py --q "What is the premium income for HDFC Life?"
   
   # Check stats
   python scripts/ingest_all.py
   
   # Expected: System returns to pre-deployment state
   ```

5. [ ] **Document Rollback**
   
   Record in `DEPLOYMENT_LOG.md`:
   ```markdown
   ### Rollback Executed
   **Date:** [YYYY-MM-DD HH:MM]
   **Reason:** [Describe trigger condition]
   **Status:** SUCCESS / FAILED
   
   **Root Cause Analysis:**
   [Describe what went wrong]
   
   **Next Steps:**
   [Plan for addressing issues before retry]
   ```

6. [ ] **Notify Stakeholders**
   - [ ] Inform team of rollback
   - [ ] Schedule post-mortem meeting
   - [ ] Plan remediation steps

---

## Post-Deployment Monitoring

### First 24 Hours

- [ ] **Monitor Error Logs**
  ```bash
  # Check for errors every 2-4 hours
  Select-String -Path ".\logs\app.log" -Pattern "ERROR" | Select-Object -Last 50
  ```

- [ ] **Track Query Performance**
  - [ ] Monitor average response time
  - [ ] Check for timeout errors
  - [ ] Verify retrieval accuracy

- [ ] **User Feedback**
  - [ ] Collect feedback on answer quality
  - [ ] Note any reported issues
  - [ ] Track user satisfaction

### First Week

- [ ] **Performance Metrics**
  - [ ] Average query response time: ___________
  - [ ] Chunk retrieval accuracy: ___________
  - [ ] System uptime: ___________
  - [ ] Error rate: ___________

- [ ] **Quality Metrics**
  - [ ] User satisfaction score: ___________
  - [ ] Answer completeness: ___________
  - [ ] False positive rate: ___________

---

## Success Criteria

Deployment is considered successful when ALL of the following are met:

- ✓ Chunk count reduced by 75-80% (from ~1,820 to 300-400)
- ✓ All 6 companies successfully re-indexed
- ✓ Processing errors < 1% of pages
- ✓ Query response time < 5 seconds
- ✓ All metadata fields present and correct
- ✓ Retrieval quality maintained or improved
- ✓ No critical errors in logs
- ✓ Streamlit UI functioning correctly
- ✓ User acceptance testing passed

---

## Troubleshooting

### Issue: Chunk Count Not Reduced

**Symptoms:** Total chunks still ~1,820 after re-indexing

**Diagnosis:**
```bash
python -c "from src.config import PAGE_WISE_CHUNKING; print(f'PAGE_WISE_CHUNKING={PAGE_WISE_CHUNKING}')"
```

**Solution:**
- Verify PAGE_WISE_CHUNKING=True in .env
- Restart Python process to reload config
- Re-run ingestion with --force flag

### Issue: Processing Errors on Multiple Pages

**Symptoms:** Many pages rejected with "unsplittable table row" errors

**Diagnosis:**
```bash
Select-String -Path ".\logs\app.log" -Pattern "rejected|unsplittable"
```

**Solution:**
- Review rejected pages in logs
- If > 5% of pages rejected, consider increasing MAX_PAGE_TOKENS
- Document affected pages for manual review

### Issue: Retrieval Quality Degraded

**Symptoms:** Queries return incomplete or irrelevant results

**Diagnosis:**
- Run test queries and compare with baseline
- Check if complete tables are being retrieved
- Verify metadata completeness

**Solution:**
- Review chunk content for specific queries
- Adjust TOP_K_SIMPLE and TOP_K_COMPLEX if needed
- Consider rollback if quality drop > 10%

### Issue: Performance Degradation

**Symptoms:** Query response time > 5 seconds

**Diagnosis:**
```bash
Measure-Command { python scripts/test_query.py --q "test query" }
```

**Solution:**
- Check ChromaDB size and performance
- Verify embedding model loaded correctly
- Monitor system resources (CPU, memory)
- Consider hardware upgrade if persistent

---

## Contacts and Resources

### Support Contacts
- **Technical Lead:** [Name/Email]
- **System Administrator:** [Name/Email]
- **On-Call Support:** [Phone/Email]

### Documentation
- Requirements: `.kiro/specs/page-wise-chunking/requirements.md`
- Design: `.kiro/specs/page-wise-chunking/design.md`
- Tasks: `.kiro/specs/page-wise-chunking/tasks.md`
- Rollback Guide: `ROLLBACK_PROCEDURE.md`

### Backup Locations
- ChromaDB Backups: `./backups/chromadb_backup_*`
- Config Backups: `./.env.backup_*`
- Deployment Logs: `DEPLOYMENT_LOG.md`

---

## Checklist Summary

**Pre-Deployment:** ☐ 10 items  
**Deployment:** ☐ 6 items  
**Post-Deployment:** ☐ 10 items  
**Total:** ☐ 26 items

**Estimated Total Time:** 30-45 minutes  
**Rollback Time:** 15-20 minutes (if needed)

---

*Last Updated: [Date]*  
*Version: 1.0*  
*Feature: Page-Wise Chunking*
