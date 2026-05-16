"""
Test script to verify the updated L-page regex pattern.
Tests various formats that should be matched by the improved regex.
"""

import re

# Updated regex pattern (same as in pdf_parser.py)
_LPAGE_LABEL_RE = re.compile(r'\s*(L-\d+(?:-[A-Z]+(?:-[A-Z]+)?)?)\s*[:\-]?\s*(.*)', re.IGNORECASE)

# Test cases that should match
test_cases = [
    # Original formats (should still work)
    ("L-1", "L-1", ""),
    ("L-14", "L-14", ""),
    ("L-1 : Revenue Account", "L-1", "Revenue Account"),
    ("L-14 : Investments - Assets Held to Cover Linked Liabilities Schedule", "L-14", "Investments - Assets Held to Cover Linked Liabilities Schedule"),
    ("L-5 - Analytical Ratios", "L-5", "Analytical Ratios"),
    
    # New formats with leading whitespace
    ("  L-1", "L-1", ""),
    ("   L-4 Premium Schedule", "L-4", "Premium Schedule"),
    ("\tL-2 Balance Sheet", "L-2", "Balance Sheet"),
    
    # New formats with serial numbers (real PDF format)
    ("1 L-1-A-RA Revenue Account", "L-1-A-RA", "Revenue Account"),
    ("2 L-2 Balance Sheet", "L-2", "Balance Sheet"),
    ("3 L-3 : Receipts and Payments Account", "L-3", "Receipts and Payments Account"),
    ("4 L-4-Premium", "L-4", "Premium"),
    ("14 L-14 Investments - Assets Held to Cover Linked Liabilities Schedule", "L-14", "Investments - Assets Held to Cover Linked Liabilities Schedule"),
    
    # Formats with suffixes
    ("L-1-A-RA", "L-1-A-RA", ""),
    ("L-1-A-RA : Revenue Account", "L-1-A-RA", "Revenue Account"),
    
    # Formats without colons
    ("L-4 Premium", "L-4", "Premium"),
    ("L-5 Analytical Ratios", "L-5", "Analytical Ratios"),
]

print("Testing L-page regex pattern...")
print("=" * 80)

all_passed = True
for test_input, expected_label, expected_section in test_cases:
    match = _LPAGE_LABEL_RE.search(test_input)
    
    if match:
        label = match.group(1).upper()
        section = match.group(2).strip()
        
        if label == expected_label and section == expected_section:
            print(f"✓ PASS: '{test_input}'")
            print(f"  → Label: {label}, Section: {section}")
        else:
            print(f"✗ FAIL: '{test_input}'")
            print(f"  Expected: Label={expected_label}, Section={expected_section}")
            print(f"  Got:      Label={label}, Section={section}")
            all_passed = False
    else:
        print(f"✗ FAIL: '{test_input}' - NO MATCH")
        print(f"  Expected: Label={expected_label}, Section={expected_section}")
        all_passed = False
    
    print()

print("=" * 80)
if all_passed:
    print("✓ All tests passed!")
else:
    print("✗ Some tests failed!")

# Test that the old regex would have failed on new formats
print("\n" + "=" * 80)
print("Comparison with old regex (should fail on new formats):")
print("=" * 80)

old_regex = re.compile(r'^(L-\d+)\s*[:\-]?\s*(.*)', re.IGNORECASE)

new_format_tests = [
    "1 L-1-A-RA Revenue Account",
    "  L-4 Premium Schedule",
    "14 L-14 Investments",
]

for test_input in new_format_tests:
    old_match = old_regex.match(test_input)
    new_match = _LPAGE_LABEL_RE.search(test_input)
    
    print(f"\nInput: '{test_input}'")
    print(f"  Old regex (match): {old_match is not None}")
    print(f"  New regex (search): {new_match is not None}")
    if new_match:
        print(f"  New regex result: Label={new_match.group(1).upper()}, Section={new_match.group(2).strip()}")
