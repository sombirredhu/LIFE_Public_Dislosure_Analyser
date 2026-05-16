# Quick Start: Definitions System

## 🚀 Get Started in 3 Steps

### Step 1: Open the App
```bash
streamlit run app/streamlit_app.py
```

### Step 2: Go to "Definitions" Tab
Click on the **📚 Definitions** tab in the app

### Step 3: Start Adding Definitions!

---

## 💬 Chat Commands (Quick Reference)

### Add Page Definition
```
define GWP as L-4
define Premium Schedule as L-5
add definition: Analytical Ratios = L-6
```

### Add Calculation
```
define Margin % = Margin / ANP
define ROE = Net Profit / Equity
add calculation: Loss Ratio = Claims / Premium
```

### Search Definition
```
what is GWP?
define Margin %
```

---

## 🎯 Common Insurance Terms to Add

### Premium Related (L-4)
```
define GWP as L-4
define Gross Written Premium as L-4
define Premium Schedule as L-4
define Total Premium as L-4
```

### Claims Related (L-5)
```
define Claims Paid as L-5
define Claims Outstanding as L-5
define Total Claims as L-5
```

### Ratios & Metrics (L-6)
```
define Analytical Ratios as L-6
define Key Ratios as L-6
define Performance Metrics as L-6
```

### Common Calculations
```
define Loss Ratio = Claims Paid / GWP
define Expense Ratio = Operating Expenses / GWP
define Combined Ratio = Loss Ratio + Expense Ratio
define Margin % = Margin / ANP
define ROE = Net Profit / Equity
define Solvency Ratio = Available Capital / Required Capital
```

---

## 📊 Example Workflow

### Scenario: You want to analyze GWP data

**Step 1**: Define the term
```
Chat: define GWP as L-4
System: ✓ Added 'GWP' → L-4
```

**Step 2**: Add related terms
```
Chat: define Gross Written Premium as L-4
System: ✓ Added 'Gross Written Premium' → L-4
```

**Step 3**: Now ask questions using any term
```
Chat: What is the GWP for HDFC in Q3 FY26?
System: [Returns L-4 data for HDFC Q3 FY26]

Chat: Show me Gross Written Premium trends
System: [Returns same L-4 data - knows they're the same]
```

---

## 🔧 Settings Page Features

### Add Definitions
1. Select "Page Definition" or "Calculation"
2. Fill in the fields
3. Click "Add"

### View Definitions
- **Page Definitions Tab**: See all terms organized by L-page
- **Calculations Tab**: See all formulas

### Delete Definitions
- Click the 🗑️ button next to any definition

### Search
- Type any term in the search box
- See all related information instantly

### Sync with PDFs
- Click "🔄 Sync with PDF Definitions"
- Merges all PDF-extracted definitions with your custom ones

---

## 💡 Pro Tips

### 1. Build Your Glossary
Create a complete glossary of your domain terms:
```
define GWP as L-4
define NWP as L-5
define ANP as L-6
define FYP as L-7
```

### 2. Document Calculations
Add all important formulas:
```
define Loss Ratio = Claims / Premium
define Expense Ratio = Expenses / Premium
define Combined Ratio = Loss Ratio + Expense Ratio
```

### 3. Use Consistent Names
- Good: "Gross Written Premium", "Loss Ratio"
- Avoid: "GWP1", "Ratio2", "Metric_X"

### 4. Sync After Uploads
After uploading new PDFs:
1. Go to Definitions tab
2. Click "Sync with PDF Definitions"
3. Review new terms added

### 5. Test Your Definitions
```
what is GWP?
what is Loss Ratio?
```

---

## 🎓 Learning Path

### Beginner
1. Add 5 basic terms (GWP, NWP, Claims, etc.)
2. Test them in chat
3. View them in Definitions tab

### Intermediate
1. Add 10+ terms covering all L-pages
2. Add 5 common calculations
3. Use chat commands fluently

### Advanced
1. Build complete glossary (50+ terms)
2. Document all formulas
3. Sync regularly with PDFs
4. Use definitions in complex queries

---

## 📝 Cheat Sheet

| Action | Chat Command | Settings Page |
|--------|-------------|---------------|
| Add page def | `define X as L-Y` | Fill form → Add |
| Add calculation | `define X = formula` | Fill form → Add |
| Search | `what is X?` | Type in search box |
| Delete | N/A | Click 🗑️ button |
| Sync PDFs | N/A | Click Sync button |
| View all | N/A | Browse tabs |

---

## ❓ FAQ

**Q: Can I add the same term to multiple L-pages?**
A: No, each term can only map to one L-page. Delete it first if you need to reassign.

**Q: Are searches case-sensitive?**
A: No, searches are case-insensitive. "GWP" = "gwp" = "Gwp"

**Q: What happens when I upload a new PDF?**
A: System auto-extracts definitions and merges them with your custom ones.

**Q: Can I export my definitions?**
A: Yes, they're stored in `data/processed/custom_definitions.json` - you can backup this file.

**Q: How do I bulk add definitions?**
A: Currently one at a time. Future versions will support CSV import.

---

## 🆘 Troubleshooting

**Problem**: Chat command not working
**Solution**: Check format - must be exact: `define X as L-Y` or `define X = formula`

**Problem**: Term not found
**Solution**: Check spelling - must match exactly (case-insensitive)

**Problem**: Can't add duplicate
**Solution**: Delete existing term first, then add new one

**Problem**: PDF definitions not showing
**Solution**: Click "Sync with PDF Definitions" in Definitions tab

---

## 🎉 You're Ready!

Start by adding a few basic terms and see how it works. The system will help you build a comprehensive knowledge base over time.

**Happy defining!** 🚀
