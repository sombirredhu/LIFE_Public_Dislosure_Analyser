"""Test query translation and retrieval for premium data"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.embedder import get_collection_stats, get_indexed_companies
from src.rag_pipeline import answer_question, classify_complexity
from src.retriever import retrieve

print("="*70)
print("TESTING QUERY TRANSLATION AND RETRIEVAL")
print("="*70)

# Check database status
stats = get_collection_stats()
print(f"\n1. DATABASE STATUS")
print("-"*70)
print(f"Total chunks: {stats['total_chunks']}")
print(f"Companies indexed: {len(stats['chunks_by_company'])}")
print("\nChunks by company:")
for company, count in sorted(stats['chunks_by_company'].items()):
    print(f"  {company}: {count} chunks")

companies = get_indexed_companies()
print(f"\nCompany codes: {companies}")

# Test query
query = "which company did the most premium"
print(f"\n2. QUERY ANALYSIS")
print("-"*70)
print(f"Query: '{query}'")
print(f"Complexity: {classify_complexity(query)}")

# Test retrieval
print(f"\n3. RETRIEVAL TEST")
print("-"*70)
print("Retrieving chunks for 'premium'...")
chunks = retrieve("premium", top_k=20)
print(f"Retrieved {len(chunks)} chunks")

# Check which companies are represented
companies_in_results = {}
for chunk in chunks:
    company = chunk['metadata']['company']
    page_label = chunk['metadata'].get('page_label', 'unknown')
    if company not in companies_in_results:
        companies_in_results[company] = []
    companies_in_results[company].append({
        'page': chunk['metadata']['page_number'],
        'label': page_label,
        'score': chunk['score']
    })

print(f"\nCompanies in results: {len(companies_in_results)}/{len(companies)}")
for company, pages in sorted(companies_in_results.items()):
    print(f"\n  {company}:")
    for p in pages[:3]:  # Show first 3 pages
        print(f"    Page {p['page']} ({p['label']}) - Score: {p['score']:.3f}")

# Check for L-4 pages specifically
print(f"\n4. L-4 PAGE CHECK")
print("-"*70)
l4_chunks = [c for c in chunks if c['metadata'].get('page_label', '').startswith('L-4')]
print(f"L-4 pages in results: {len(l4_chunks)}")
for chunk in l4_chunks[:5]:
    meta = chunk['metadata']
    print(f"  {meta['company']} - Page {meta['page_number']} ({meta['page_label']}) - Score: {chunk['score']:.3f}")

# Test with L-4 specific query
print(f"\n5. L-4 SPECIFIC RETRIEVAL")
print("-"*70)
l4_query = "L-4 premium schedule"
l4_chunks = retrieve(l4_query, top_k=20)
print(f"Retrieved {len(l4_chunks)} chunks for '{l4_query}'")

l4_companies = {}
for chunk in l4_chunks:
    company = chunk['metadata']['company']
    if company not in l4_companies:
        l4_companies[company] = chunk['score']

print(f"\nCompanies with L-4 data: {len(l4_companies)}/{len(companies)}")
for company, score in sorted(l4_companies.items(), key=lambda x: x[1], reverse=True):
    print(f"  {company}: {score:.3f}")

# Test full RAG pipeline
print(f"\n6. FULL RAG PIPELINE TEST")
print("-"*70)
print(f"Query: '{query}'")
result = answer_question(query)
print(f"\nAnswer preview (first 500 chars):")
print(result['answer'][:500])
print(f"\nMetadata:")
print(f"  Chunks used: {result['chunks_used']}")
print(f"  Confidence: {result['confidence']}")
print(f"  Sources: {result['sources']}")

print("\n" + "="*70)
