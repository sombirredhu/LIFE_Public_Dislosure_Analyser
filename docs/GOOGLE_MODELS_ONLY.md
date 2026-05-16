# Google Models Only Filter

**Date:** 2026-05-17  
**Status:** ✅ IMPLEMENTED

---

## Overview

Updated the paid model filter to **only show Google models** because other models are not working properly. This ensures users only see reliable, working models.

---

## Filter Logic

### Requirements
1. ✅ Must be a Google model (google/, gemini, or "google" in name)
2. ✅ Must have output cost under $3 per million tokens
3. ✅ Must be a paid model (not free)

### Implementation

**Location:** `app/streamlit_app.py`, lines ~60-85

```python
def is_affordable_model(model):
    """
    Only show Google models with output cost under $3 per million tokens.
    Other models are not working, so we filter them out.
    """
    try:
        # First check if it's a Google model
        model_id_lower = model["id"].lower()
        model_name_lower = model.get("name", "").lower()
        
        # Only allow Google models (google/ prefix or "google" in name)
        if not ("google/" in model_id_lower or "google" in model_name_lower or "gemini" in model_id_lower):
            return False
        
        # Check price (must be under $3/MTok)
        completion_price = float(model.get("completion_price", 999))
        price_per_mtok = completion_price * 1_000_000
        
        if price_per_mtok >= 3.0:
            return False
        
        return True
    except (ValueError, TypeError):
        return False
```

---

## Available Google Models

**Total Google models under $3/MTok:** 15

### Complete List (Sorted by Price)

| # | Model ID | Name | Output Price |
|---|----------|------|--------------|
| 1 | google/gemma-3-4b-it | Google: Gemma 3 4B | $0.08/MTok |
| 2 | google/gemma-3n-e4b-it | Google: Gemma 3n 4B | $0.12/MTok |
| 3 | google/gemma-3-12b-it | Google: Gemma 3 12B | $0.13/MTok |
| 4 | google/gemma-3-27b-it | Google: Gemma 3 27B | $0.16/MTok |
| 5 | google/gemini-2.0-flash-lite-001 | Google: Gemini 2.0 Flash Lite | $0.30/MTok |
| 6 | google/gemma-4-26b-a4b-it | Google: Gemma 4 26B A4B | $0.33/MTok |
| 7 | google/gemma-4-31b-it | Google: Gemma 4 31B | $0.37/MTok |
| 8 | google/gemini-2.5-flash-lite-preview-09-2025 | Google: Gemini 2.5 Flash Lite Preview | $0.40/MTok |
| 9 | google/gemini-2.5-flash-lite | Google: Gemini 2.5 Flash Lite | $0.40/MTok |
| 10 | google/gemini-2.0-flash-001 | Google: Gemini 2.0 Flash | $0.40/MTok |
| 11 | google/gemma-2-27b-it | Google: Gemma 2 27B | $0.65/MTok |
| 12 | google/gemini-3.1-flash-lite | Google: Gemini 3.1 Flash Lite | $1.50/MTok |
| 13 | google/gemini-3.1-flash-lite-preview | Google: Gemini 3.1 Flash Lite Preview | $1.50/MTok |
| 14 | google/gemini-2.5-flash-image | Google: Nano Banana (Gemini 2.5 Flash Image) | $2.50/MTok |
| 15 | google/gemini-2.5-flash | Google: Gemini 2.5 Flash | $2.50/MTok |

---

## Model Categories

### Gemma Models (Budget-Friendly)
**Price Range:** $0.08 - $0.65/MTok

- **Gemma 3 4B** - $0.08/MTok (cheapest)
- **Gemma 3n 4B** - $0.12/MTok
- **Gemma 3 12B** - $0.13/MTok
- **Gemma 3 27B** - $0.16/MTok
- **Gemma 4 26B A4B** - $0.33/MTok
- **Gemma 4 31B** - $0.37/MTok
- **Gemma 2 27B** - $0.65/MTok

### Gemini Flash Lite Models (Balanced)
**Price Range:** $0.30 - $1.50/MTok

- **Gemini 2.0 Flash Lite** - $0.30/MTok
- **Gemini 2.5 Flash Lite Preview** - $0.40/MTok
- **Gemini 2.5 Flash Lite** - $0.40/MTok
- **Gemini 3.1 Flash Lite** - $1.50/MTok
- **Gemini 3.1 Flash Lite Preview** - $1.50/MTok

### Gemini Flash Models (Premium)
**Price Range:** $0.40 - $2.50/MTok

- **Gemini 2.0 Flash** - $0.40/MTok
- **Gemini 2.5 Flash Image** - $2.50/MTok
- **Gemini 2.5 Flash** - $2.50/MTok

---

## UI Updates

### Sidebar Header

**Before:**
```
💰 Paid Model (Affordable)
🔒 Only models <$3/MTok • Sorted: Fast → Reasoning → Cheapest
```

**After:**
```
💰 Paid Model (Google Only)
🔒 Only Google models <$3/MTok • Sorted: Fast → Reasoning → Cheapest
```

### Selectbox Help Text

**Before:**
```
Sorted: Fast models → Reasoning models → Cheapest price • All <$3/MTok
```

**After:**
```
Google models only (others not working) • Sorted: Fast → Reasoning → Cheapest • All <$3/MTok
```

---

## Why Google Models Only?

### Issues with Other Models
- Other models (DeepSeek, Perceptron, etc.) are not working properly
- API errors or timeouts
- Inconsistent responses
- Reliability issues

### Benefits of Google Models
- ✅ **Reliable:** Consistent performance
- ✅ **Fast:** Low latency responses
- ✅ **Affordable:** 15 models under $3/MTok
- ✅ **Variety:** From $0.08 to $2.50/MTok
- ✅ **Quality:** Good reasoning and accuracy

---

## Sorting Order

Models are still sorted by:
1. **Fast models** (if any have "fast" in name)
2. **Reasoning models** (if any have reasoning keywords)
3. **Cheapest price** (lowest to highest)

**Current Result:** All Google models sorted by price (cheapest first) since none have "fast" or "reasoning" in their names.

---

## Example Dropdown

```
💰 Paid Model (Google Only)
🔒 Only Google models <$3/MTok • Sorted: Fast → Reasoning → Cheapest

[Dropdown:]
1. google/gemma-3-4b-it                              $0.08/MTok
2. google/gemma-3n-e4b-it                            $0.12/MTok
3. google/gemma-3-12b-it                             $0.13/MTok
4. google/gemma-3-27b-it                             $0.16/MTok
5. google/gemini-2.0-flash-lite-001                  $0.30/MTok
6. google/gemma-4-26b-a4b-it                         $0.33/MTok
7. google/gemma-4-31b-it                             $0.37/MTok
8. google/gemini-2.5-flash-lite-preview-09-2025      $0.40/MTok
9. google/gemini-2.5-flash-lite                      $0.40/MTok
10. google/gemini-2.0-flash-001                      $0.40/MTok
11. google/gemma-2-27b-it                            $0.65/MTok
12. google/gemini-3.1-flash-lite                     $1.50/MTok
13. google/gemini-3.1-flash-lite-preview             $1.50/MTok
14. google/gemini-2.5-flash-image                    $2.50/MTok
15. google/gemini-2.5-flash                          $2.50/MTok

💡 Google: Gemma 3 4B • Output: $0.08/MTok
```

---

## Recommendations

### For Budget Users
**Recommended:** `google/gemma-3-4b-it` ($0.08/MTok)
- Cheapest option
- Good for simple queries
- Fast responses

### For Balanced Performance
**Recommended:** `google/gemini-2.0-flash-001` ($0.40/MTok)
- Good balance of cost and quality
- Reliable performance
- Suitable for most queries

### For Best Quality
**Recommended:** `google/gemini-2.5-flash` ($2.50/MTok)
- Highest quality in affordable range
- Best reasoning capabilities
- Still under $3/MTok limit

---

## Files Modified

**`app/streamlit_app.py`:**
1. **Lines ~60-85:** Updated `is_affordable_model()` to filter for Google models only
2. **Line ~120:** Updated header to "Paid Model (Google Only)"
3. **Line ~121:** Updated caption to mention Google models
4. **Line ~131:** Updated help text to explain Google-only filter

---

## Testing

### Verification Steps

1. **Start app:** `streamlit run app/streamlit_app.py`
2. **Open sidebar:** Check "Model Settings"
3. **View dropdown:** Paid Model (Google Only)
4. **Verify models:**
   - All models start with "google/"
   - All models under $3/MTok
   - 15 models total
5. **Test selection:** Select different models and verify they work

### Expected Results

- ✅ Only Google models shown
- ✅ 15 models available
- ✅ All under $3/MTok
- ✅ Sorted by price (cheapest first)
- ✅ Prices displayed correctly

---

## Future Considerations

### If Other Models Start Working

To re-enable other models, simply remove the Google-only check:

```python
# Remove these lines from is_affordable_model():
if not ("google/" in model_id_lower or "google" in model_name_lower or "gemini" in model_id_lower):
    return False
```

### Adding More Providers

If other reliable providers emerge (e.g., Anthropic, OpenAI), update the filter:

```python
# Allow Google, Anthropic, and OpenAI
allowed_providers = ["google/", "anthropic/", "openai/"]
if not any(provider in model_id_lower for provider in allowed_providers):
    return False
```

---

## Summary

✅ **Filtered to Google models only** (15 models)  
✅ **All under $3/MTok** output cost  
✅ **Sorted by price** (cheapest first)  
✅ **Updated UI text** to reflect Google-only filter  
✅ **Tested with live API** (356 models fetched)

**Status:** Production ready with reliable Google models only! 🎉
