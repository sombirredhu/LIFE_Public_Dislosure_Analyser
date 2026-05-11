# Definitions System Guide

## Overview

The Definitions System allows you to teach the system custom terminology and calculations. It supports two types of definitions:

1. **Page Definitions**: Map terms to L-pages (e.g., "GWP" → L-4)
2. **Calculation Definitions**: Define formulas (e.g., "Margin %" = "Margin / ANP")

## Key Features

### 🔄 Automatic Merging
- When you upload PDFs, the system extracts L-page definitions from index pages
- These are automatically merged with your custom definitions
- No duplicate terms - system prevents conflicts

### 🔗 Smart Linking
- If you define: `GWP = L-4`
- Then add: `GWP = Gross Written Premium`
- System understands: `GWP = L-4 = Gross Written Premium`
- All three terms become interchangeable

### 💬 Chat Interface
- Add definitions directly from the chat
- Search definitions by typing commands
- No need to switch tabs

### ⚙️ Settings Page
- Full management interface in the "Definitions" tab
- View all definitions organized by L-page
- Add, delete, and search definitions
- Sync with PDF-extracted definitions

---

## Usage

### Method 1: Chat Interface

#### Add Page Definition
```
define GWP as L-4
add definition: Premium Schedule = L-5
```

#### Add Calculation
```
define Margin % = Margin / ANP
add calculation: ROE = Net Profit / Equity
```

#### Search Definition
```
what is GWP?
define Margin %
```

### Method 2: Definitions Tab

1. Open Streamlit app
2. Go to **"Definitions"** tab
3. Use the interface to:
   - Add new definitions
   - View existing definitions
   - Delete definitions
   - Search definitions
   - Sync with PDF definitions

---

## How It Works

### Page Definitions Flow

```
User uploads PDF
    ↓
System extracts index (L-4 → "Premium Schedule")
    ↓
Saves to master_page_definitions.json
    ↓
User adds custom term: "GWP = L-4"
    ↓
System merges: L-4 → ["Premium Schedule", "GWP"]
    ↓
User asks: "Show me GWP data"
    ↓
System knows: GWP = L-4
    ↓
Retrieves all L-4 content
```

### Calculation Definitions Flow

```
User defines: "Margin % = Margin / ANP"
    ↓
Saved to custom_definitions.json
    ↓
User asks: "Calculate Margin % for HDFC"
    ↓
System knows the formula
    ↓
Can explain or compute the calculation
```

---

## File Structure

```
data/processed/
├── custom_definitions.json              # Your custom definitions
├── master_page_definitions.json         # PDF-extracted definitions
├── master_term_to_page.json            # Quick lookup: term → L-page
├── Aditya_Birla_page_definitions.json  # Company-specific (auto-generated)
└── HDFC_Life_page_definitions.json     # Company-specific (auto-generated)
```

### custom_definitions.json Structure

```json
{
  "page_definitions": {
    "L-4": ["GWP", "Gross Written Premium", "Premium Schedule"],
    "L-5": ["Analytical Ratios", "Key Ratios"]
  },
  "calculations": {
    "Margin %": "Margin / ANP",
    "ROE": "Net Profit / Equity",
    "Loss Ratio": "(Claims + Expenses) / Premium"
  },
  "metadata": {
    "last_updated": "2024-01-15T10:30:00",
    "total_page_terms": 5,
    "total_calculations": 3
  }
}
```

---

## Examples

### Example 1: Building a Complete Mapping

**Step 1**: Upload PDF with index
- System extracts: `L-4 → "Premium Schedule"`

**Step 2**: Add your terminology
```
define GWP as L-4
define Gross Written Premium as L-4
```

**Step 3**: Result
- L-4 now has 3 terms: "Premium Schedule", "GWP", "Gross Written Premium"
- You can ask about any of these terms and get L-4 data

### Example 2: Adding Calculations

```
define Margin % = Margin / ANP
define Loss Ratio = Claims / Premium
define Combined Ratio = Loss Ratio + Expense Ratio
```

Now when you ask:
- "What is the Margin % formula?" → System shows: "Margin / ANP"
- "Calculate Combined Ratio" → System knows it needs Loss Ratio and Expense Ratio

### Example 3: Chat Commands

```
User: define GWP as L-4
System: ✓ Added 'GWP' → L-4

User: what is GWP?
System: **GWP**
        📄 Page: L-4
        Related: Gross Written Premium, Premium Schedule

User: define ROE = Net Profit / Equity
System: ✓ Added calculation: ROE = Net Profit / Equity
```

---

## API Reference

### Python Functions

```python
from src.definitions_manager import (
    add_page_definition,
    add_calculation,
    delete_page_definition,
    delete_calculation,
    get_lpage_for_term,
    get_calculation_formula,
    search_definitions,
    merge_with_pdf_definitions
)

# Add page definition
success, msg = add_page_definition("GWP", "L-4")

# Add calculation
success, msg = add_calculation("Margin %", "Margin / ANP")

# Search for a term
lpage = get_lpage_for_term("GWP")  # Returns "L-4"

# Get calculation formula
formula = get_calculation_formula("Margin %")  # Returns "Margin / ANP"

# Search all definitions
result = search_definitions("GWP")
# Returns: {
#   "found": True,
#   "type": "page",
#   "lpage": "L-4",
#   "formula": None,
#   "related_terms": ["Gross Written Premium"]
# }

# Merge with PDF definitions
merge_with_pdf_definitions()
```

---

## Best Practices

### 1. Use Consistent Terminology
- Define common abbreviations (GWP, ANP, NWP, etc.)
- Map them to L-pages for easy retrieval

### 2. Document Calculations
- Add all important formulas
- Include industry-standard ratios
- Document custom metrics

### 3. Sync Regularly
- Click "Sync with PDF Definitions" after uploading new PDFs
- Ensures all extracted definitions are included

### 4. Avoid Conflicts
- System prevents duplicate terms
- If a term exists, delete it first before reassigning

### 5. Use Descriptive Names
- Good: "Gross Written Premium", "Loss Ratio"
- Avoid: "GWP1", "Ratio2"

---

## Common Use Cases

### Insurance Metrics
```
define GWP as L-4
define NWP as L-5
define Claims Ratio = Claims Paid / GWP
define Expense Ratio = Operating Expenses / GWP
define Combined Ratio = Claims Ratio + Expense Ratio
```

### Financial Ratios
```
define ROE = Net Profit / Equity
define ROA = Net Profit / Assets
define Solvency Ratio = Available Capital / Required Capital
```

### Custom Metrics
```
define Persistency % = Policies Renewed / Total Policies
define Surrender Rate = Policies Surrendered / Total Policies
define New Business Margin = Value of New Business / ANP
```

---

## Troubleshooting

### Issue: Term not found
**Solution**: Check spelling, search is case-insensitive but must match exactly

### Issue: Cannot add duplicate term
**Solution**: Delete existing term first, or use a different term

### Issue: PDF definitions not showing
**Solution**: Click "Sync with PDF Definitions" button in Definitions tab

### Issue: Chat commands not working
**Solution**: Use exact format: `define X as L-Y` or `define X = formula`

---

## Future Enhancements

Potential improvements:
- Fuzzy matching for partial terms
- Import/export definitions
- Bulk upload from CSV
- Version history
- Multi-language support
- Auto-suggest related terms
