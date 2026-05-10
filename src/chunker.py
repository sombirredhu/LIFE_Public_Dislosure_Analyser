"""
Chunker - splits parsed PDF content into overlapping chunks with metadata.
Preserves table integrity and adds rich metadata for filtering.
"""

from datetime import datetime
from typing import Dict, List, Any
import re

from src.config import CHUNK_SIZE, CHUNK_OVERLAP, MIN_CHUNK_SIZE


def detect_section_heading(text: str) -> str:
    """
    Detect section heading from text.
    Common sections: Premium Income, Claims, Persistency, Financial Performance, etc.
    """
    text_lower = text.lower()
    
    # Common section keywords
    sections = {
        "premium": "Premium Income",
        "claim": "Claims",
        "persistency": "Persistency",
        "solvency": "Solvency",
        "financial": "Financial Performance",
        "business": "Business Performance",
        "channel": "Distribution Channels",
        "product": "Product Mix",
        "expense": "Expenses",
        "commission": "Commission",
        "asset": "Assets",
        "investment": "Investments",
        "policy": "Policy Statistics",
        "summary": "Executive Summary"
    }
    
    for keyword, section_name in sections.items():
        if keyword in text_lower:
            return section_name
    
    return "General"


def chunk_text(text: str, max_size: int, overlap: int) -> List[str]:
    """
    Split text into overlapping chunks at sentence boundaries.
    """
    if len(text) <= max_size:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + max_size
        
        if end >= len(text):
            # Last chunk
            chunks.append(text[start:])
            break
        
        # Try to break at sentence boundary (. ! ?)
        chunk_text = text[start:end]
        last_period = max(
            chunk_text.rfind('. '),
            chunk_text.rfind('! '),
            chunk_text.rfind('? ')
        )
        
        if last_period > max_size // 2:  # Only break if we're past halfway
            end = start + last_period + 1
        
        chunks.append(text[start:end].strip())
        start = end - overlap
    
    return chunks


def chunk_table(table_data: Dict[str, Any], metadata: Dict[str, str], page_number: int, chunk_counter: int) -> List[Dict[str, Any]]:
    """
    Convert table to chunks. Keep small tables as single chunk.
    For large tables, split by row groups but keep headers in each chunk.
    """
    raw_text = table_data["raw_text"]
    
    # If table fits in one chunk, return as single chunk
    if len(raw_text) <= CHUNK_SIZE:
        chunk_id = f"{metadata['company_code']}_{metadata['quarter']}_{metadata['fy']}_page{page_number}_chunk{chunk_counter}"
        return [{
            "chunk_id": chunk_id,
            "text": raw_text,
            "metadata": {
                **metadata,
                "page_number": page_number,
                "section": detect_section_heading(raw_text),
                "content_type": "table",
                "char_count": len(raw_text),
                "ingested_at": datetime.now().isoformat()
            }
        }]
    
    # Large table - split by row groups
    headers = " | ".join(table_data["headers"])
    rows = table_data["rows"]
    
    chunks = []
    current_rows = []
    current_size = len(headers)
    
    for row in rows:
        row_text = " | ".join(row)
        row_size = len(row_text) + 1  # +1 for newline
        
        if current_size + row_size > CHUNK_SIZE and current_rows:
            # Create chunk from accumulated rows
            chunk_text = headers + "\n" + "\n".join(current_rows)
            chunk_id = f"{metadata['company_code']}_{metadata['quarter']}_{metadata['fy']}_page{page_number}_chunk{chunk_counter}"
            
            chunks.append({
                "chunk_id": chunk_id,
                "text": chunk_text,
                "metadata": {
                    **metadata,
                    "page_number": page_number,
                    "section": detect_section_heading(chunk_text),
                    "content_type": "table",
                    "char_count": len(chunk_text),
                    "ingested_at": datetime.now().isoformat()
                }
            })
            
            chunk_counter += 1
            current_rows = []
            current_size = len(headers)
        
        current_rows.append(row_text)
        current_size += row_size
    
    # Add remaining rows as final chunk
    if current_rows:
        chunk_text = headers + "\n" + "\n".join(current_rows)
        chunk_id = f"{metadata['company_code']}_{metadata['quarter']}_{metadata['fy']}_page{page_number}_chunk{chunk_counter}"
        
        chunks.append({
            "chunk_id": chunk_id,
            "text": chunk_text,
            "metadata": {
                **metadata,
                "page_number": page_number,
                "section": detect_section_heading(chunk_text),
                "content_type": "table",
                "char_count": len(chunk_text),
                "ingested_at": datetime.now().isoformat()
            }
        })
    
    return chunks


def chunk_document(parsed_doc: Dict[str, Any], additional_metadata: Dict[str, str] = None) -> List[Dict[str, Any]]:
    """
    Convert parsed PDF document into chunks with metadata.
    
    Args:
        parsed_doc: Output from pdf_parser.parse_pdf()
        additional_metadata: Optional extra metadata to attach to chunks
    
    Returns:
        List of chunk dictionaries with text and metadata
    """
    # Base metadata from parsed document
    base_metadata = {
        "company": parsed_doc["company"],
        "company_code": parsed_doc["company_code"],
        "quarter": parsed_doc["quarter"],
        "fy": parsed_doc["fy"],
        "period_label": parsed_doc["period_label"],
        "source_file": parsed_doc["source_file"]
    }
    
    if additional_metadata:
        base_metadata.update(additional_metadata)
    
    all_chunks = []
    chunk_counter = 1
    
    for page in parsed_doc["pages"]:
        page_number = page["page_number"]
        
        # Process tables first
        for table in page["tables"]:
            table_chunks = chunk_table(table, base_metadata, page_number, chunk_counter)
            all_chunks.extend(table_chunks)
            chunk_counter += len(table_chunks)
        
        # Process text blocks
        for text_block in page["text_blocks"]:
            if len(text_block) < MIN_CHUNK_SIZE:
                continue  # Skip very small text blocks
            
            # Split text block into chunks
            text_chunks = chunk_text(text_block, CHUNK_SIZE, CHUNK_OVERLAP)
            
            for text_chunk in text_chunks:
                if len(text_chunk) < MIN_CHUNK_SIZE:
                    continue
                
                chunk_id = f"{base_metadata['company_code']}_{base_metadata['quarter']}_{base_metadata['fy']}_page{page_number}_chunk{chunk_counter}"
                
                all_chunks.append({
                    "chunk_id": chunk_id,
                    "text": text_chunk,
                    "metadata": {
                        **base_metadata,
                        "page_number": page_number,
                        "section": detect_section_heading(text_chunk),
                        "content_type": "text",
                        "char_count": len(text_chunk),
                        "ingested_at": datetime.now().isoformat()
                    }
                })
                
                chunk_counter += 1
    
    return all_chunks


if __name__ == "__main__":
    # Test chunker with a parsed document
    import sys
    import json
    from pathlib import Path
    from src.config import PROCESSED_OUTPUT_DIR
    
    if len(sys.argv) > 1:
        json_path = sys.argv[1]
    else:
        # Try to find any JSON in processed directory
        json_files = list(Path(PROCESSED_OUTPUT_DIR).glob("*.json"))
        if json_files:
            json_path = str(json_files[0])
        else:
            print(f"No JSON files found in {PROCESSED_OUTPUT_DIR}")
            print("Run pdf_parser.py first to generate parsed JSON files")
            print("Usage: python src/chunker.py <path_to_json>")
            sys.exit(1)
    
    print(f"Chunking: {json_path}")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        parsed_doc = json.load(f)
    
    chunks = chunk_document(parsed_doc)
    
    print(f"\n✓ Chunking complete!")
    print(f"  Total Chunks: {len(chunks)}")
    print(f"  Avg Chunk Size: {sum(c['metadata']['char_count'] for c in chunks) // len(chunks)} chars")
    print(f"\n  First chunk metadata:")
    print(f"    ID: {chunks[0]['chunk_id']}")
    print(f"    Section: {chunks[0]['metadata']['section']}")
    print(f"    Type: {chunks[0]['metadata']['content_type']}")
    print(f"    Size: {chunks[0]['metadata']['char_count']} chars")
    print(f"\n  First 200 chars of text:")
    print(f"    {chunks[0]['text'][:200]}...")
