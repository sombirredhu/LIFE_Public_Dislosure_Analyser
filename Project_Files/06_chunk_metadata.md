# 6. Chunk Metadata Schema

Every chunk stored in ChromaDB carries this metadata. This allows the retriever to filter by company, quarter, or report section when answering questions.

---

## Schema

```json
{
  "chunk_id":      "HDFC_Life_Q1_FY25_page3_chunk2",
  "company":       "HDFC Life",
  "company_code":  "HDFC_Life",
  "quarter":       "Q1",
  "fy":            "FY25",
  "period_label":  "Q1 FY2024-25",
  "page_number":   3,
  "page_label":    "L-5",
  "section":       "Premium Income",
  "content_type":  "table",
  "source_file":   "HDFC_Life_Q1_FY25.pdf",
  "char_count":    742,
  "ingested_at":   "2025-05-10T14:32:00"
}
```

---

## Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `chunk_id` | string | Unique ID — `{company_code}_{quarter}_{fy}_page{n}_chunk{n}` |
| `company` | string | Full company name — e.g. "HDFC Life" |
| `company_code` | string | Code from filename — e.g. "HDFC_Life" |
| `quarter` | string | Q1, Q2, Q3, or Q4 |
| `fy` | string | FY25, FY26, etc. |
| `period_label` | string | Human-readable period — "Q1 FY2024-25" |
| `page_number` | int | Page number in source PDF |
| `page_label` | string | IRDAI L-page label — e.g. "L-1", "L-5", "L-12" |
| `section` | string | Human-readable section name derived from index page — e.g. "Revenue Account", "Claims", "Persistency" |
| `content_type` | string | `table`, `text`, `summary`, or `header` |
| `source_file` | string | Original PDF filename |
| `char_count` | int | Character length of this chunk |
| `ingested_at` | string | ISO timestamp of when chunk was ingested |

---

## content_type Values

| Value | When Used |
|-------|-----------|
| `table` | Chunk came from a detected table in the PDF |
| `text` | Regular paragraph text |
| `summary` | Executive summary or highlights section (see detection rules below) |
| `header` | Section heading or page title |

### `summary` Detection Rules (in `pdf_parser.py`)

A page or block is tagged `content_type = "summary"` if **any** of the following are true:

1. The page `section` name (from the L-page index) contains any of: `"summary"`, `"highlights"`, `"key metrics"`, `"overview"`, `"executive"`
2. The page is the **first page** of the PDF (page 1) and the section is `"unknown"` — first pages are often cover/summary pages with no L-label
3. The text block (first 200 chars) starts with any of: `"Key Highlights"`, `"Executive Summary"`, `"Performance Highlights"`, `"Summary of Operations"`

All other text blocks default to `content_type = "text"` unless they are a detected table (`"table"`) or a line with no sentence-ending punctuation under 100 chars (`"header"`).

---

## How Filtering Works

The retriever uses metadata to narrow searches before similarity matching:

```python
# Filter to one company
filters = {"company_code": "HDFC_Life"}

# Filter to a specific quarter + FY
filters = {"quarter": "Q1", "fy": "FY25"}

# Filter to multiple companies
filters = {"company_code": {"$in": ["HDFC_Life", "SBI_Life", "LIC"]}}

# Filter to tables only
filters = {"content_type": "table"}
```
