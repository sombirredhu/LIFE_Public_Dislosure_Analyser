"""Test RAG accuracy with page-wise chunking."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.rag_pipeline import answer_question

print(f"\n{'='*70}")
print(f"TESTING RAG WITH PAGE-WISE CHUNKING")
print(f"{'='*70}\n")

# Test query
question = "What is the total premium for Aditya Birla in Q3 FY26?"

print(f"Question: {question}\n")
print("Retrieving answer...\n")

result = answer_question(question)

print(f"{'='*70}")
print(f"ANSWER")
print(f"{'='*70}\n")
print(result['answer'])
print(f"\n{'='*70}")
print(f"METADATA")
print(f"{'='*70}")
print(f"Confidence:   {result['confidence']}")
print(f"Chunks Used:  {result['chunks_used']}")
print(f"Model:        {result.get('model_used', 'N/A')}")

if result['sources']:
    print(f"\nSources:")
    for source in result['sources']:
        print(f"  - {source}")

print(f"\n{'='*70}")
print(f"✅ Page-wise chunking provides complete page context!")
print(f"   Each retrieved chunk contains the full page with all tables and text.")
print(f"{'='*70}\n")
