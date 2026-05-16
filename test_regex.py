import re

# Test the L-page regex pattern
# This should match L-4 from "L-4-PREMIUM" and treat "PREMIUM Schedule" as description
pattern = re.compile(r'\b(L-\d+[A-Z]?(?:-[A-Z]-[A-Z]{2})?)\s*(?:-\s*)?(.*)', re.IGNORECASE)

test_cases = [
    'L-4 Premium Schedule',
    '4 L-4 Premium Schedule',
    'L-14A Aggregate value',
    'L-1-A-RA Revenue Account',
    'L-4-PREMIUM Schedule',  # Should match L-4, description="PREMIUM Schedule"
    'L-4-COMMISSION Schedule',  # Should match L-4, description="COMMISSION Schedule"
    'L-25 (i) & (ii)',
    'Form L-4- Premium Schedule',
]

print("Testing L-page regex pattern:")
print("="*70)
for test in test_cases:
    match = pattern.search(test)
    if match:
        lpage = match.group(1)
        desc = match.group(2) if len(match.groups()) > 1 else ""
        print(f"✓ '{test}'")
        print(f"  -> L-page: '{lpage}', Description: '{desc.strip()}'")
    else:
        print(f"✗ '{test}' -> NO MATCH")
    print()
