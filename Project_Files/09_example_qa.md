# 9. Example Questions & Expected Answers

Use these to test the system after setup. These represent the full range of question types the system should handle.

---

## Q1: Ranking Question

**Question:** `Which company had the highest gross written premium in Q1 FY25?`

**Expected Answer:**

```
Premium Ranking — Q1 FY2024-25

Rank | Company              | GWP (₹ Cr)
-----|----------------------|------------
1    | LIC                  | 1,14,332
2    | HDFC Life            | 8,432
3    | SBI Life             | 7,891
4    | ICICI Prudential     | 6,234

Source: LIC_Q1_FY25.pdf, HDFC_Life_Q1_FY25.pdf, SBI_Life_Q1_FY25.pdf, ICICI_Pru_Q1_FY25.pdf
```

---

## Q2: Single Company Fact

**Question:** `What was HDFC Life's claim settlement ratio in Q2 FY25?`

**Expected Answer:**

```
HDFC Life Claim Settlement Ratio — Q2 FY2024-25: 98.66%

Source: HDFC_Life_Q2_FY25.pdf, Page 9
```

---

## Q3: Multi-Company Comparison

**Question:** `Compare persistency ratios of SBI Life and ICICI Pru for Q1 FY25`

**Expected Answer:**

```
Persistency Comparison — Q1 FY2024-25

Month | SBI Life | ICICI Prudential
------|----------|------------------
13th  | 86.2%    | 84.7%
25th  | 74.1%    | 71.3%
37th  | 65.8%    | 63.2%
49th  | 58.4%    | 56.1%
61st  | 52.1%    | 49.8%

Source: SBI_Life_Q1_FY25.pdf p.11, ICICI_Pru_Q1_FY25.pdf p.13
```

---

## Q4: Trend Question (Multi-Quarter)

**Question:** `Show HDFC Life's new business premium for all quarters in FY25`

**Expected Answer:**

```
HDFC Life — New Business Premium — FY2024-25

Quarter | New Business Premium (₹ Cr)
--------|-----------------------------
Q1 FY25 | 3,241
Q2 FY25 | 3,892
Q3 FY25 | 4,123
Q4 FY25 | 5,641

Full Year Total: ₹16,897 Cr
Source: HDFC_Life_Q1_FY25.pdf, HDFC_Life_Q2_FY25.pdf, HDFC_Life_Q3_FY25.pdf, HDFC_Life_Q4_FY25.pdf
```

---

## Q5: Channel-wise Question

**Question:** `Which channel contributed the most new business premium across all companies in Q1 FY25?`

**Expected Answer:**

```
Channel-wise New Business Premium — Q1 FY2024-25 (All Companies)

Channel    | Total Premium (₹ Cr) | % Share
-----------|----------------------|--------
Agency     | 42,341               | 51.2%
Bancassurance | 28,123            | 34.0%
Direct     | 8,234                | 9.9%
Broker     | 4,124                | 5.0%

Top channel: Agency
Source: LIC_Q1_FY25.pdf, HDFC_Life_Q1_FY25.pdf, SBI_Life_Q1_FY25.pdf, ICICI_Pru_Q1_FY25.pdf
```

---

## Q6: Data Not Available

**Question:** `What was Bajaj Life's VNB margin in Q1 FY25?`

**Expected Answer:**

```
VNB margin data for Bajaj Life for Q1 FY2024-25 is not available 
in the indexed Public Disclosure reports. 

Note: VNB margin is typically disclosed in annual/embedded value reports, 
not quarterly PD reports.
```

---

> **Testing Tip:** Run these from CLI first using `scripts/test_query.py` before testing in the Streamlit UI.
