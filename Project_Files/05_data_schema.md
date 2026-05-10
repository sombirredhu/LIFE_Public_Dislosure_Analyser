# 5. Data Extracted from PD Reports

IRDAI Public Disclosure reports follow a standard format across all companies. The parser is designed around this standard structure. Below are all key tables and sections extracted.

> **Important — how this schema is used:** The system does **not** perform structured field extraction. It does not parse `gross_written_premium` into a database column. All data is stored as text chunks (table rows + paragraphs) and retrieved via semantic vector search. These field names are **semantic reference labels** — they describe what data the system can find and answer about, not what it stores as named fields.

---

## 5.1 Premium Data (Most Important)

| Field Name | Description |
|------------|-------------|
| `new_business_premium` | First year premium from new policies — individual + group |
| `renewal_premium` | Premium from existing policy renewals |
| `single_premium` | One-time lump sum premium policies |
| `gross_written_premium` | Total of all premium types (GWP) |
| `net_premium` | GWP after reinsurance ceded |
| `channel_agency_premium` | New business via agency channel |
| `channel_banca_premium` | New business via bancassurance |
| `channel_direct_premium` | New business via direct / online |
| `channel_broker_premium` | New business via brokers |

---

## 5.2 Policy & Business Volume

| Field Name | Description |
|------------|-------------|
| `no_of_policies_nb` | Number of new business policies issued |
| `no_of_lives_covered` | Total lives covered (individual + group) |
| `sum_assured_nb` | Total sum assured for new business |
| `annualised_premium_equivalent` | APE — standard metric for comparing insurers |

---

## 5.3 Claims Data

| Field Name | Description |
|------------|-------------|
| `claims_paid_individual` | Claims settled for individual policies (₹ Cr) |
| `claims_paid_group` | Claims settled for group policies (₹ Cr) |
| `claims_repudiated` | Claims rejected with reason |
| `claims_pending` | Claims under process at quarter end |
| `claim_settlement_ratio` | % of claims settled vs received |
| `claims_intimated` | Total new claims received this quarter |

---

## 5.4 Persistency Ratios

| Field Name | Description |
|------------|-------------|
| `persistency_13th_month` | % policies surviving after 13 months |
| `persistency_25th_month` | % policies surviving after 25 months |
| `persistency_37th_month` | % policies surviving after 37 months |
| `persistency_49th_month` | % policies surviving after 49 months |
| `persistency_61st_month` | % policies surviving after 61 months |

---

## 5.5 Financial Performance

| Field Name | Description |
|------------|-------------|
| `total_income` | Total revenue including premium + investment income |
| `total_expenses` | All operating expenses |
| `profit_after_tax` | Net profit / loss for the quarter |
| `assets_under_management` | Total AUM — policyholder + shareholder funds |
| `solvency_ratio` | Required: >150%. Higher = more financially stable |
| `commission_expenses` | Total commission paid to agents and intermediaries |
| `operating_expense_ratio` | Opex as % of GWP — lower is better |

---

## 5.6 Product Mix

| Field Name | Description |
|------------|-------------|
| `ulip_premium` | Unit Linked Insurance Plan premium |
| `par_premium` | Participating (with profit) policy premium |
| `non_par_premium` | Non-participating policy premium |
| `annuity_premium` | Annuity / pension product premium |
| `health_premium` | Health rider and standalone health premium |
| `group_term_premium` | Group term life premium |

---

> **Note:** All monetary values are in Indian Rupees Crore (₹ Cr) unless otherwise stated in the source PDF.
