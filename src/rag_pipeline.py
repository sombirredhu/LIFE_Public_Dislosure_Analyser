"""
RAG Pipeline - orchestrates retrieval and LLM to answer questions.
Combines retriever + Claude API with proper prompt engineering.
"""

from typing import Dict, Any, Optional, List
from src.retriever import retrieve, get_confidence_level
from src.llm_client import ask_claude, ask_claude_streaming


# System prompt for Claude
SYSTEM_PROMPT = """You are a financial analyst specializing in Indian life insurance industry data.
You have access to IRDAI Public Disclosure reports from multiple life insurance companies across multiple quarters.

Your job is to answer questions accurately based ONLY on the provided report excerpts. Do not make up numbers or use outside knowledge for specific figures.

Rules:
1. Always mention the company name, quarter, and FY when quoting a number
2. If comparing companies, present results as a ranked table in markdown format
3. All monetary values are in Indian Rupees Crore (₹ Cr) unless stated otherwise
4. If data is not available in the provided excerpts, say so clearly
5. For ranking questions, rank all companies for which data is available
6. Always cite the source PDF filename at the end of your answer
7. Use markdown tables for comparisons and rankings
8. Be concise but complete - include all relevant numbers

Response format:
- For single company questions: direct answer with number + source
- For comparison/ranking questions: markdown table with all companies
- For trend questions: show quarter-wise data in a table
"""


def build_context(chunks: List[Dict[str, Any]]) -> str:
    """
    Build context string from retrieved chunks.
    
    Args:
        chunks: List of retrieved chunks with metadata
    
    Returns:
        Formatted context string for Claude
    """
    context_parts = []
    
    for chunk in chunks:
        metadata = chunk["metadata"]
        
        context_part = f"""Source: {metadata['source_file']} | Company: {metadata['company']} | Period: {metadata['period_label']} | Page: {metadata['page_number']}

{chunk['text']}"""
        
        context_parts.append(context_part)
    
    return "\n\n---\n\n".join(context_parts)


def build_user_message(question: str, chunks: List[Dict[str, Any]]) -> str:
    """
    Build the user message with question and context.
    
    Args:
        question: User's question
        chunks: Retrieved chunks
    
    Returns:
        Formatted user message for Claude
    """
    context = build_context(chunks)
    
    user_message = f"""Answer this question using the report excerpts below:

Question: {question}

Report Excerpts:
{context}"""
    
    return user_message


def answer_question(
    question: str,
    filters: Optional[Dict[str, Any]] = None,
    top_k: int = None,
    stream: bool = False
) -> Dict[str, Any]:
    """
    Answer a question using RAG pipeline.
    
    Args:
        question: User's question
        filters: Optional metadata filters for retrieval
        top_k: Number of chunks to retrieve
        stream: If True, return generator for streaming response
    
    Returns:
        Dictionary with answer, sources, and metadata
        If stream=True, returns dict with 'stream' generator
    """
    # Step 1: Retrieve relevant chunks
    chunks = retrieve(question, filters=filters, top_k=top_k)
    
    if not chunks:
        return {
            "answer": "I couldn't find any relevant information in the indexed reports to answer this question. Please ensure the relevant PDF files have been uploaded and indexed.",
            "sources": [],
            "chunks_used": 0,
            "confidence": "none",
            "question": question
        }
    
    # Step 2: Build prompt
    user_message = build_user_message(question, chunks)
    
    # Step 3: Get confidence level
    confidence = get_confidence_level(chunks)
    
    # Step 4: Call Claude
    if stream:
        # Return streaming generator
        return {
            "stream": ask_claude_streaming(SYSTEM_PROMPT, user_message),
            "sources": list(set(c["metadata"]["source_file"] for c in chunks)),
            "chunks_used": len(chunks),
            "confidence": confidence,
            "question": question
        }
    else:
        # Get complete response
        answer = ask_claude(SYSTEM_PROMPT, user_message)
        
        # Extract unique source files
        sources = list(set(c["metadata"]["source_file"] for c in chunks))
        
        return {
            "answer": answer,
            "sources": sources,
            "chunks_used": len(chunks),
            "confidence": confidence,
            "question": question,
            "retrieved_chunks": chunks  # Include for debugging
        }


def answer_with_company_filter(question: str, company_codes: List[str]) -> Dict[str, Any]:
    """
    Answer question filtered to specific companies.
    
    Args:
        question: User's question
        company_codes: List of company codes to filter
    
    Returns:
        Answer dictionary
    """
    if len(company_codes) == 1:
        filters = {"company_code": company_codes[0]}
    else:
        filters = {"company_code": {"$in": company_codes}}
    
    return answer_question(question, filters=filters)


def answer_with_period_filter(question: str, quarter: str = None, fy: str = None) -> Dict[str, Any]:
    """
    Answer question filtered to specific time period.
    
    Args:
        question: User's question
        quarter: Quarter filter (e.g., "Q1")
        fy: Financial year filter (e.g., "FY25")
    
    Returns:
        Answer dictionary
    """
    filters = {}
    if quarter:
        filters["quarter"] = quarter
    if fy:
        filters["fy"] = fy
    
    return answer_question(question, filters=filters if filters else None)


if __name__ == "__main__":
    # Test RAG pipeline
    import sys
    
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
    else:
        question = "Which company had the highest gross written premium?"
    
    print(f"Question: {question}\n")
    print("Retrieving relevant information and generating answer...\n")
    
    try:
        result = answer_question(question)
        
        print("=" * 80)
        print("ANSWER")
        print("=" * 80)
        print(result["answer"])
        print()
        
        print("=" * 80)
        print("METADATA")
        print("=" * 80)
        print(f"Confidence: {result['confidence']}")
        print(f"Chunks Used: {result['chunks_used']}")
        print(f"Sources: {', '.join(result['sources'])}")
        print()
        
    except ValueError as e:
        print(f"✗ Configuration error: {e}")
        print("\nPlease ensure:")
        print("1. .env file exists with ANTHROPIC_API_KEY")
        print("2. PDF files have been ingested into ChromaDB")
    
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
