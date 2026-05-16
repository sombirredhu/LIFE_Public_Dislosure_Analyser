# Model Filter Implementation - UI Only

**Date:** 2026-05-16  
**Location:** `app/streamlit_app.py` (Streamlit UI only)

---

## ✅ What Was Done

### 1. **UI Filtering Logic** (No .env Changes)

The Streamlit app now **automatically filters** the paid model dropdown to:
- ✅ **ONLY show models with output cost <$3 per million tokens**
- ✅ **Sort by reasoning quality** (best reasoning models first)
- ✅ **Block users from selecting expensive models** (Opus, Sonnet, GPT-5)

### 2. **Free Model Default**

- Free model dropdown defaults to `openrouter/free` (best free model auto-selection)
- Users can still select other free models if they want

### 3. **Paid Model Auto-Selection**

- Paid models are **sorted by reasoning score** (highest first)
- Best reasoning model within budget is shown first
- Users can only choose from affordable models (<$3/MTok output)

---

## 🔒 What Users CANNOT Do

Users **CANNOT** select these expensive models in the UI:
- ❌ Claude Opus 4.6/4.7 ($25/MTok output)
- ❌ Claude Sonnet 4.5/4.6 ($15/MTok output)
- ❌ Claude Haiku 4.5 ($5/MTok output)
- ❌ GPT-5.x ($15-75/MTok output)
- ❌ Any model with output cost ≥$3/MTok

**These models are filtered out at the UI level** - they won't even appear in the dropdown.

---

## ✅ What Users CAN Select

### Free Models (All Available)
- openrouter/free (default - auto-selects best free model)
- anthropic/claude-3-haiku:free
- google/gemini-flash:free
- Any other free models from OpenRouter

### Paid Models (Only <$3/MTok Output)
**Sorted by reasoning quality (best first):**

1. **DeepSeek Reasoner** ($2.19/MTok) - Best reasoning
2. **DeepSeek V3** ($0.28-2.19/MTok) - Good reasoning
3. **Gemini Flash** ($0.40/MTok) - Fast + cheap
4. **DeepSeek Chat** ($0.28/MTok) - Cheapest
5. **Qwen Turbo** (varies) - Good balance
6. **Llama 3.x** (varies) - Open source

---

## 🎯 Reasoning Score Logic

Models are ranked by reasoning capability:

### Tier 1: Dedicated Reasoning (Score 90-100)
- Models with "reasoner" or "reasoning" in name
- DeepSeek R1, OpenAI O1/O3 variants

### Tier 2: Advanced Models (Score 70-89)
- DeepSeek V3
- Gemini Pro/Ultra
- Qwen Turbo/Plus

### Tier 3: Standard Models (Score 50-69)
- DeepSeek Chat
- Gemini Flash
- Llama 3.x

### Tier 4: Basic Models (Score <50)
- Other models

**The dropdown shows models in this order** - best reasoning first.

---

## 📊 Cost Comparison

### What Users Will See (Affordable)

| Model | Output Cost | Reasoning | Shown in UI |
|-------|-------------|-----------|-------------|
| DeepSeek Reasoner | $2.19/MTok | ⭐⭐⭐⭐⭐ | ✅ YES (First) |
| Gemini Flash | $0.40/MTok | ⭐⭐⭐⭐ | ✅ YES |
| DeepSeek Chat | $0.28/MTok | ⭐⭐⭐ | ✅ YES |

### What Users Will NOT See (Blocked)

| Model | Output Cost | Reasoning | Shown in UI |
|-------|-------------|-----------|-------------|
| Claude Haiku | $5.00/MTok | ⭐⭐⭐⭐ | ❌ NO (>$3) |
| Claude Sonnet | $15.00/MTok | ⭐⭐⭐⭐⭐ | ❌ NO (>$3) |
| Claude Opus | $25.00/MTok | ⭐⭐⭐⭐⭐ | ❌ NO (>$3) |
| GPT-5.x | $15-75/MTok | ⭐⭐⭐⭐⭐ | ❌ NO (>$3) |

---

## 🔧 How It Works

### 1. Model Fetching
```python
models = fetch_available_models()  # Get all models from OpenRouter
```

### 2. Filtering (Paid Models Only)
```python
def is_affordable_model(model):
    completion_price = float(model.get("completion_price", "999"))
    if completion_price >= 3.0:
        return False  # Block expensive models
    return True

affordable_models = [m for m in models if not m["is_free"] and is_affordable_model(m)]
```

### 3. Sorting by Reasoning
```python
def get_reasoning_score(model):
    # Returns 40-100 based on model capabilities
    # Higher = better reasoning
    
affordable_models_sorted = sorted(affordable_models, key=get_reasoning_score, reverse=True)
```

### 4. Display in UI
```python
paid_ids = [m["id"] for m in affordable_models_sorted]
st.selectbox("Select paid model", options=paid_ids)  # Only shows affordable models
```

---

## 🚀 User Experience

### When User Opens Sidebar

1. **Free Model Dropdown:**
   - Shows all free models
   - Defaults to `openrouter/free`
   - User can change if desired

2. **Paid Model Dropdown:**
   - Shows ONLY models with output <$3/MTok
   - Sorted by reasoning quality (best first)
   - Caption: "🔒 Only models with output cost <$3/MTok shown"
   - Shows model price below dropdown

3. **Model Info:**
   - Selected model name
   - Output cost per million tokens
   - Example: "💡 DeepSeek Reasoner • Output: $2.19/MTok"

---

## 💰 Cost Savings

### Example: 1000 Complex Queries/Month

**Assumptions:**
- 1000 complex queries
- 2K output tokens per query
- Total: 2M output tokens

| Model | Monthly Cost | Blocked? |
|-------|-------------|----------|
| DeepSeek Reasoner | **$4.38** | ✅ Allowed |
| Gemini Flash | **$0.80** | ✅ Allowed |
| DeepSeek Chat | **$0.56** | ✅ Allowed |
| Claude Haiku | $10.00 | ❌ Blocked |
| Claude Sonnet | $30.00 | ❌ Blocked |
| Claude Opus | $50.00 | ❌ Blocked |

**Savings:** $25.62-49.44/month by blocking expensive models!

---

## 🔍 Testing

### Test the Filter

```bash
# 1. Start the app
streamlit run app/streamlit_app.py

# 2. Open sidebar (⚙️ Model Settings)

# 3. Check "Paid Model" dropdown
# Should ONLY show:
# - DeepSeek Reasoner
# - DeepSeek Chat
# - Gemini Flash
# - Other models <$3/MTok

# Should NOT show:
# - Claude Opus
# - Claude Sonnet
# - Claude Haiku
# - GPT-5.x
```

### Test a Query

```python
# Ask a complex question
"Compare gross written premium across all companies"

# Check response metadata
# - model_used should be one of the affordable models
# - Should NOT be Opus/Sonnet/Haiku
```

---

## ⚠️ Important Notes

### 1. .env File NOT Changed
- `.env` still has original defaults
- Filtering happens ONLY in the UI
- Users cannot bypass the filter

### 2. No Backdoor Access
- Even if user edits `.env` to set expensive model
- UI will auto-select first affordable model if default not in list
- No way to select blocked models through the UI

### 3. API Key Still Works
- OpenRouter API key unchanged
- All affordable models work normally
- Just expensive models are hidden from selection

---

## 📝 Code Location

**File:** `app/streamlit_app.py`  
**Function:** `render_sidebar()`  
**Lines:** ~50-120

**Key Functions:**
- `is_affordable_model()` - Filters models by price
- `get_reasoning_score()` - Ranks models by reasoning
- Dropdown logic - Shows only filtered models

---

## ✅ Summary

**What Changed:**
- ✅ UI filters paid models to <$3/MTok output only
- ✅ Models sorted by reasoning quality (best first)
- ✅ Free model defaults to `openrouter/free`
- ✅ Users CANNOT select expensive models

**What Didn't Change:**
- ❌ .env file (kept original defaults)
- ❌ API configuration
- ❌ Core RAG logic

**Result:**
- 🔒 Users blocked from expensive models
- 💰 Automatic cost savings
- 🎯 Best reasoning model shown first
- ✅ No configuration needed

---

**Implementation:** UI-only filtering  
**Status:** COMPLETE ✅  
**Files Modified:** `app/streamlit_app.py` only

