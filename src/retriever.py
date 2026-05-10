"""
Retriever - searches ChromaDB for relevant chunks based on query.
Supports filtering by company, quarter, FY, and other metadata.
"""

from typing import List, Dict, Any, Optional
from src.embedder import get_or_create_collection, get_embedding_model
from src.config import TOP_K_RESULTS, SIMILARITY_THRESHOLD


def retrieve(query: str, filters: Optional[Dict[str, Any]] = None, top_k: int = None) -> List[Dict[str, Any]]:
    """
    Search ChromaDB for chunks relevant to the query.
    
    Args:
        query: Search query string
        filters: Optional metadata filters (e.g., {"company_code": "HDFC_Life"})
        top_k: Number of results to return (defaults to TOP_K_RESULTS from config)
    
    Returns:
        List of chunk dictionaries with text, metadata, and similarity scores
    
    Filter examples:
        filters = {"company_code": "HDFC_Life"}
        filters = {"quarter": "Q1", "fy": "FY25"}
        filters = {"company_code": {"$in": ["HDFC_Life", "SBI_Life"]}}
        filters = {"content_type": "table"}
    """
    if top_k is None:
        top_k = TOP_K_RESULTS
    
    # Get collection and embedding model
    collection = get_or_create_collection()
    model = get_embedding_model()
    
    # Create query embedding
    query_embedding = model.encode(query).tolist()
    
    # Build query parameters
    query_params = {
        "query_embeddings": [query_embedding],
        "n_results": top_k
    }
    
    # Add filters if provided
    if filters:
        query_params["where"] = filters
    
    # Query ChromaDB
    results = collection.query(**query_params)
    
    # Format results
    chunks = []
    
    if results["ids"] and results["ids"][0]:
        for i in range(len(results["ids"][0])):
            # Calculate similarity score (ChromaDB returns distances, convert to similarity)
            # Distance is L2 distance, convert to similarity score (0-1)
            distance = results["distances"][0][i]
            similarity = 1 / (1 + distance)  # Convert distance to similarity
            
            # Filter by similarity threshold
            if similarity < SIMILARITY_THRESHOLD:
                continue
            
            chunk = {
                "chunk_id": results["ids"][0][i],
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "score": round(similarity, 4),
                "distance": round(distance, 4)
            }
            chunks.append(chunk)
    
    return chunks


def retrieve_by_company(query: str, company_codes: List[str], top_k: int = None) -> List[Dict[str, Any]]:
    """
    Retrieve chunks filtered to specific companies.
    
    Args:
        query: Search query
        company_codes: List of company codes (e.g., ["HDFC_Life", "SBI_Life"])
        top_k: Number of results per company
    
    Returns:
        List of chunks from specified companies
    """
    if len(company_codes) == 1:
        filters = {"company_code": company_codes[0]}
    else:
        filters = {"company_code": {"$in": company_codes}}
    
    return retrieve(query, filters=filters, top_k=top_k)


def retrieve_by_period(query: str, quarter: str = None, fy: str = None, top_k: int = None) -> List[Dict[str, Any]]:
    """
    Retrieve chunks filtered to specific time period.
    
    Args:
        query: Search query
        quarter: Quarter filter (e.g., "Q1")
        fy: Financial year filter (e.g., "FY25")
        top_k: Number of results
    
    Returns:
        List of chunks from specified period
    """
    filters = {}
    
    if quarter:
        filters["quarter"] = quarter
    if fy:
        filters["fy"] = fy
    
    return retrieve(query, filters=filters if filters else None, top_k=top_k)


def retrieve_tables_only(query: str, filters: Optional[Dict[str, Any]] = None, top_k: int = None) -> List[Dict[str, Any]]:
    """
    Retrieve only table chunks (no text paragraphs).
    
    Args:
        query: Search query
        filters: Optional additional filters
        top_k: Number of results
    
    Returns:
        List of table chunks only
    """
    table_filters = {"content_type": "table"}
    
    if filters:
        table_filters.update(filters)
    
    return retrieve(query, filters=table_filters, top_k=top_k)


def get_confidence_level(chunks: List[Dict[str, Any]]) -> str:
    """
    Determine confidence level based on chunk similarity scores.
    
    Args:
        chunks: List of retrieved chunks with scores
    
    Returns:
        Confidence level: "high", "medium", "low", or "none"
    """
    if not chunks:
        return "none"
    
    top_score = chunks[0]["score"]
    
    if top_score > 0.7:
        return "high"
    elif top_score > 0.4:
        return "medium"
    else:
        return "low"


if __name__ == "__main__":
    # Test retriever
    import sys
    
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        query = "gross written premium"
    
    print(f"Query: {query}")
    print(f"Retrieving top {TOP_K_RESULTS} chunks...\n")
    
    results = retrieve(query)
    
    if not results:
        print("No results found above similarity threshold")
    else:
        print(f"✓ Found {len(results)} relevant chunks\n")
        
        confidence = get_confidence_level(results)
        print(f"Confidence Level: {confidence}\n")
        
        for i, chunk in enumerate(results[:3], 1):
            print(f"Result {i}:")
            print(f"  Score: {chunk['score']}")
            print(f"  Source: {chunk['metadata']['source_file']}")
            print(f"  Company: {chunk['metadata']['company']}")
            print(f"  Period: {chunk['metadata']['period_label']}")
            print(f"  Page: {chunk['metadata']['page_number']}")
            print(f"  Section: {chunk['metadata']['section']}")
            print(f"  Type: {chunk['metadata']['content_type']}")
            print(f"  Text Preview: {chunk['text'][:150]}...")
            print()
