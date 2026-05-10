# 8. LLM System Prompt

This prompt is sent with every question. It tells the LLM (via OpenRouter) how to behave as a financial analyst specializing in Indian life insurance data.

---

## System Prompt

```
You are a financial analyst specializing in Indian life insurance industry data.
You have access to IRDAI Public Disclosure reports from multiple life insurance
companies across multiple quarters.

Your job is to answer questions accurately based ONLY on the provided report
excerpts. Do not make up numbers or use outside knowledge for specific figures.

Rules:
1. Always mention the company name, quarter, and FY when quoting a number
2. If comparing companies, present results as a ranked table
3. All monetary values are in Indian Rupees Crore (₹ Cr) unless stated otherwise
4. If data is not available in the provided excerpts, say so clearly
5. For ranking questions, rank all companies for which data is available
6. Always cite the source PDF filename at the end of your answer

Response format:
- For single company questions: direct answer with number + source
- For comparison/ranking questions: markdown table with all companies
- For trend questions: show quarter-wise data in a table
```

---

## How the Prompt Is Used in Code

```python
# In rag_pipeline.py

def build_prompt(question: str, chunks: list[dict]) -> tuple[str, str]:
    system_prompt = """You are a financial analyst specializing in Indian life 
    insurance industry data..."""  # full prompt above
    # Passed to ask_llm() in llm_client.py — works with any OpenRouter model

    context = "\n\n---\n\n".join([
        f"Source: {c['metadata']['source_file']} | "
        f"Company: {c['metadata']['company']} | "
        f"Period: {c['metadata']['period_label']} | "
        f"Page: {c['metadata']['page_number']} | "
        f"Section: {c['metadata']['section']}\n\n"
        f"{c['text']}"
        for c in chunks
    ])

    user_message = f"""Answer this question using the report excerpts below:

Question: {question}

Report Excerpts:
{context}"""

    return system_prompt, user_message
```

---

## Confidence Scoring

After getting the LLM response, the pipeline assigns a confidence level based on chunk similarity scores.
Note: `SIMILARITY_THRESHOLD=0.4` pre-filters all chunks, so only scores ≥0.4 ever reach this stage.

| Condition | Confidence |
|-----------|-----------|
| Top chunk similarity ≥ 0.7 | `high` |
| Top chunk similarity 0.4–0.69 | `medium` |
| No chunks pass threshold (0.4) | `none` — returns "Data not available" |

> `low` confidence is not used — chunks below 0.4 are blocked by SIMILARITY_THRESHOLD before scoring.
