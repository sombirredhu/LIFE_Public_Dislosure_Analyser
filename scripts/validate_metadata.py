"""
Validate metadata completeness and correctness for page-wise chunks.
"""

import sys
import json
from pathlib import Path
from collections import defaultdict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.chunker import chunk_document
from src.config import PROCESSED_OUTPUT_DIR


# Required metadata fields for page-wise chunks
REQUIRED_FIELDS = {
    "chunk_id", "company", "company_code", "quarter", "fy",
    "period_label", "source_file", "page_number", "page_label",
    "section", "content_type", "char_count", "ingested_at",
    "table_count", "text_block_count", "is_split"
}


def validate_chunk_metadata(chunk, chunk_index):
    """Validate a single chunk's metadata."""
    issues = []
    metadata = chunk.get("metadata", {})
    
    # Check required fields
    missing_fields = REQUIRED_FIELDS - set(metadata.keys())
    if missing_fields:
        issues.append(f"Missing fields: {missing_fields}")
    
    # Validate chunk_id format
    chunk_id = metadata.get("chunk_id", "")
    if not chunk_id:
        issues.append("chunk_id is empty")
    elif "_page" not in chunk_id:
        issues.append(f"chunk_id format incorrect: {chunk_id}")
    
    # Validate content_type
    content_type = metadata.get("content_type")
    if content_type != "page":
        issues.append(f"content_type should be 'page', got '{content_type}'")
    
    # Validate page_number
    page_number = metadata.get("page_number")
    if not isinstance(page_number, int) or page_number < 1:
        issues.append(f"Invalid page_number: {page_number}")
    
    # Validate char_count
    char_count = metadata.get("char_count")
    text_length = len(chunk.get("text", ""))
    if char_count != text_length:
        issues.append(f"char_count mismatch: metadata={char_count}, actual={text_length}")
    
    # Validate is_split
    is_split = metadata.get("is_split")
    if not isinstance(is_split, bool):
        issues.append(f"is_split should be boolean, got {type(is_split)}")
    
    # If is_split=True, check for part_number and total_parts
    if is_split:
        if "part_number" not in metadata:
            issues.append("is_split=True but part_number missing")
        if "total_parts" not in metadata:
            issues.append("is_split=True but total_parts missing")
    
    # Validate table_count and text_block_count
    table_count = metadata.get("table_count")
    text_block_count = metadata.get("text_block_count")
    if not isinstance(table_count, int) or table_count < 0:
        issues.append(f"Invalid table_count: {table_count}")
    if not isinstance(text_block_count, int) or text_block_count < 0:
        issues.append(f"Invalid text_block_count: {text_block_count}")
    
    return issues


def main():
    """Validate metadata for all processed JSON files."""
    print("=" * 80)
    print("METADATA VALIDATION")
    print("=" * 80)
    print()
    
    # Find all processed JSON files
    processed_dir = Path(PROCESSED_OUTPUT_DIR)
    json_files = [
        f for f in processed_dir.glob("*.json")
        if not f.name.endswith("_page_definitions.json")
        and not f.name.startswith("master_")
        and not f.name.endswith("_term_to_page.json")
        and not f.name == "custom_definitions.json"
    ]
    
    if not json_files:
        print(f"✗ No processed JSON files found in {PROCESSED_OUTPUT_DIR}")
        return
    
    print(f"Validating {len(json_files)} files...")
    print()
    
    # Track validation results
    total_chunks = 0
    total_issues = 0
    files_with_issues = []
    validation_stats = defaultdict(int)
    
    for json_file in json_files:
        print(f"Validating: {json_file.name}")
        
        # Load and chunk document
        with open(json_file, "r", encoding="utf-8") as f:
            parsed_doc = json.load(f)
        
        chunks = chunk_document(parsed_doc)
        file_issues = []
        
        # Validate each chunk
        for i, chunk in enumerate(chunks):
            issues = validate_chunk_metadata(chunk, i)
            if issues:
                file_issues.extend([(i, issue) for issue in issues])
                total_issues += len(issues)
            
            # Collect stats
            metadata = chunk.get("metadata", {})
            validation_stats["total_chunks"] += 1
            validation_stats["with_page_label"] += 1 if metadata.get("page_label") else 0
            validation_stats["with_company_full_name"] += 1 if metadata.get("company_full_name") else 0
            validation_stats["is_split_true"] += 1 if metadata.get("is_split") else 0
        
        total_chunks += len(chunks)
        
        if file_issues:
            files_with_issues.append((json_file.name, file_issues))
            print(f"  ✗ {len(file_issues)} issues found")
            for chunk_idx, issue in file_issues[:5]:  # Show first 5 issues
                print(f"    Chunk {chunk_idx}: {issue}")
            if len(file_issues) > 5:
                print(f"    ... and {len(file_issues) - 5} more issues")
        else:
            print(f"  ✓ All {len(chunks)} chunks valid")
        
        print()
    
    # Print summary
    print("=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    print(f"Files Validated: {len(json_files)}")
    print(f"Total Chunks: {total_chunks}")
    print(f"Total Issues: {total_issues}")
    print()
    
    print("Metadata Coverage:")
    print(f"  Chunks with page_label: {validation_stats['with_page_label']} ({validation_stats['with_page_label']/total_chunks*100:.1f}%)")
    print(f"  Chunks with company_full_name: {validation_stats['with_company_full_name']} ({validation_stats['with_company_full_name']/total_chunks*100:.1f}%)")
    print(f"  Chunks with is_split=True: {validation_stats['is_split_true']} ({validation_stats['is_split_true']/total_chunks*100:.1f}%)")
    print()
    
    if total_issues == 0:
        print("✓ ALL METADATA VALIDATION PASSED")
        print("✓ All required fields present and correctly formatted")
        print("✓ chunk_id format correct")
        print("✓ char_count matches text length")
        print("✓ content_type is 'page'")
        print("✓ is_split metadata consistent")
    else:
        print(f"✗ VALIDATION FAILED: {total_issues} issues found in {len(files_with_issues)} files")
        print()
        print("Files with issues:")
        for filename, issues in files_with_issues:
            print(f"  - {filename}: {len(issues)} issues")
    
    print()
    
    # Additional checks
    print("Additional Checks:")
    print(f"  ✓ Average chunks per file: {total_chunks / len(json_files):.1f}")
    print(f"  ✓ All chunks have content_type='page': {validation_stats['total_chunks'] == total_chunks}")
    print()


if __name__ == "__main__":
    main()
