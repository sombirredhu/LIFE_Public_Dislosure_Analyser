# 1. Project Overview

This system ingests IRDAI Public Disclosure (PD) PDF reports from multiple life insurance companies across multiple quarters, extracts and indexes the content using RAG (Retrieval-Augmented Generation), and allows users to ask plain English questions across all companies and time periods simultaneously.

---

## Project Specification

| Attribute | Detail |
|-----------|--------|
| Report Type | IRDAI Public Disclosure (PD) — Quarterly |
| Companies | 27 total (start with 4-5 for testing) |
| File Format | Text-based PDF with tables and summaries |
| Granularity | Quarter-wise — Q1, Q2, Q3, Q4 per FY |
| Data Accumulation | Incremental — new quarter uploads add to existing index |
| Query Interface | Streamlit web UI — plain English questions |
| LLM | OpenRouter API (two-tier: free model for simple queries, paid model for complex — verify slugs at openrouter.ai/models) |
| Vector Store | ChromaDB (local, persistent) |
| PDF Parser | pdfplumber (handles tables + text accurately) |

---

## Example Questions the System Answers

- Which company had the highest total premium in Q2 FY2025?
- What was LIC's gross written premium in Q1 FY2025 in crore?
- Compare persistency ratio of HDFC Life vs SBI Life for Q3 FY2025
- Which company had the lowest claim settlement ratio this quarter?
- Show channel-wise new business premium ranking for all companies
- What was the total industry new business premium for Q2 FY2025?
