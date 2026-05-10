# 4. PDF File Naming Convention

Strict naming convention is required. The system extracts company code, quarter, and financial year from the filename automatically — no manual metadata entry or pre-registration needed. Any company is supported as long as the filename is well-formed.

---

## Format

```
{COMPANY_CODE}_{QUARTER}_{FY}.pdf
```

---

## Examples

```
LIC_Q1_FY25.pdf
HDFC_Life_Q2_FY25.pdf
SBI_Life_Q3_FY25.pdf
ICICI_Pru_Q4_FY25.pdf
Bajaj_Life_Q1_FY26.pdf
Max_Life_Q2_FY26.pdf
```

---

## Rules

- Use underscores only — no spaces or hyphens
- Quarter values: `Q1`, `Q2`, `Q3`, `Q4`
- FY values: `FY25`, `FY26` (last two digits of financial year)
- Company code can be any alphanumeric string with underscores (e.g. `Canara_HSBC`, `Edelweiss`, `PNB_MetLife`)
- All lowercase extension: `.pdf` not `.PDF`

---

## Company Code Examples (all 27 IRDAI life insurers)

| Company Code | Full Name |
|-------------|-----------|
| `LIC` | Life Insurance Corporation of India |
| `HDFC_Life` | HDFC Life Insurance |
| `SBI_Life` | SBI Life Insurance |
| `ICICI_Pru` | ICICI Prudential Life Insurance |
| `Max_Life` | Max Life Insurance |
| `Bajaj_Life` | Bajaj Allianz Life Insurance |
| `Kotak_Life` | Kotak Mahindra Life Insurance |
| `Tata_AIA` | Tata AIA Life Insurance |
| `Aditya_Birla` | Aditya Birla Sun Life Insurance |
| `PNB_MetLife` | PNB MetLife India Insurance |
| `Canara_HSBC` | Canara HSBC Life Insurance |
| `IndiaFirst` | IndiaFirst Life Insurance |
| `Edelweiss` | Edelweiss Tokio Life Insurance |
| `Bandhan_Life` | Bandhan Life Insurance |
| `Pramerica` | Pramerica Life Insurance |
| `Reliance_Nippon` | Reliance Nippon Life Insurance |
| `Sahara_Life` | Sahara India Life Insurance |
| `Shriram_Life` | Shriram Life Insurance |
| `Star_Union` | Star Union Dai-ichi Life Insurance |
| `Future_Generali` | Future Generali India Life Insurance |
| `Ageas_Federal` | Ageas Federal Life Insurance |
| `Aviva` | Aviva Life Insurance |
| `Exide_Life` | Exide Life Insurance |
| `Bharti_AXA` | Bharti AXA Life Insurance |
| `IDBI_Federal` | IDBI Federal Life Insurance |
| `Aegon` | Aegon Life Insurance |
| `DHFL_Pramerica` | DHFL Pramerica Life Insurance |

> These are examples only — no pre-registration required. The system auto-infers the company code from any well-formed filename.

---

## `period_label` Derivation

The `period_label` field in chunk metadata is derived from the filename's `FY` token. The formula is:

```
period_label = f"{quarter} FY20{int(fy[2:])-1}-{fy[2:]}"
```

| Filename Token | `quarter` | `fy` | `period_label` |
|----------------|-----------|------|----------------|
| `Q1_FY25` | `Q1` | `FY25` | `Q1 FY2024-25` |
| `Q2_FY25` | `Q2` | `FY25` | `Q2 FY2024-25` |
| `Q1_FY26` | `Q1` | `FY26` | `Q1 FY2025-26` |
| `Q4_FY27` | `Q4` | `FY27` | `Q4 FY2026-27` |

This derivation runs in `ingestor.py` during metadata build — before chunking. The `fy` field stores the short form (`FY25`) and `period_label` stores the human-readable form (`Q1 FY2024-25`).

---

## Why Strict Naming?

The system uses filename parsing to tag every chunk with `company_code`, `quarter`, and `FY` metadata. This enables filtering by company or time period without any pre-configuration. Adding a new insurer requires no code or `.env` change — just drop the correctly named PDF into `data/pdfs/` and ingest.
