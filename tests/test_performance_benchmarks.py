"""
Performance benchmarks for page-wise chunking implementation.
Task 12.1: Run performance benchmarks

This test suite measures:
- Processing time for 50-page PDF
- Comparison with text-based chunking performance
- Chunk count reduction verification (≥ 75%)
- Memory and CPU usage documentation

Requirements: 7.3, 7.4
"""

import pytest
import time
import psutil
import os
from pathlib import Path
from src.chunker import chunk_document
from src.pdf_parser import parse_pdf
from src.config import PAGE_WISE_CHUNKING, CHUNK_SIZE, CHUNK_OVERLAP


class PerformanceMetrics:
    """Helper class to track performance metrics."""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.start_memory = None
        self.end_memory = None
        self.start_cpu = None
        self.end_cpu = None
        self.process = psutil.Process(os.getpid())
    
    def start(self):
        """Start tracking metrics."""
        self.start_time = time.time()
        self.start_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        self.start_cpu = self.process.cpu_percent(interval=0.1)
    
    def stop(self):
        """Stop tracking metrics."""
        self.end_time = time.time()
        self.end_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        self.end_cpu = self.process.cpu_percent(interval=0.1)
    
    def get_elapsed_time(self):
        """Get elapsed time in seconds."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None
    
    def get_memory_usage(self):
        """Get memory usage delta in MB."""
        if self.start_memory and self.end_memory:
            return self.end_memory - self.start_memory
        return None
    
    def get_cpu_usage(self):
        """Get average CPU usage percentage."""
        if self.start_cpu is not None and self.end_cpu is not None:
            return (self.start_cpu + self.end_cpu) / 2
        return None
    
    def report(self):
        """Generate performance report."""
        return {
            "elapsed_time_seconds": self.get_elapsed_time(),
            "memory_delta_mb": self.get_memory_usage(),
            "avg_cpu_percent": self.get_cpu_usage(),
            "peak_memory_mb": self.end_memory
        }


def find_sample_pdf():
    """Find a sample PDF file for testing."""
    pdf_dir = Path("data/pdfs")
    if pdf_dir.exists():
        pdf_files = list(pdf_dir.glob("*.pdf"))
        if pdf_files:
            return str(pdf_files[0])
    return None


def create_large_test_document(num_pages=50):
    """
    Create a synthetic parsed document with specified number of pages.
    Each page contains realistic content similar to IRDAI disclosure PDFs.
    Content is sized to be large enough to trigger text-based chunking.
    """
    pages = []
    for i in range(1, num_pages + 1):
        # Create realistic table data with many rows
        table_rows = []
        for row_idx in range(50):  # 50 rows per table to make it larger
            table_rows.append([
                f"Item Category {row_idx + 1} - Detailed Description of Financial Line Item",
                f"{1000000 + row_idx * 100000}",
                f"{500000 + row_idx * 50000}",
                f"{500000 + row_idx * 50000}",
                f"{(row_idx * 10):.2f}%"
            ])
        
        # Create realistic text blocks with substantial content
        text_blocks = [
            f"This is page {i} of the quarterly disclosure document for the period ending March 31, 2026. " * 5,
            f"The following table presents comprehensive financial information for the reporting period, including detailed breakdowns of revenue, expenses, claims, and other key financial metrics. " * 3,
            f"All amounts are presented in thousands of Indian Rupees unless otherwise explicitly stated in the accompanying notes and schedules. " * 3,
            f"For detailed notes, explanations, assumptions, and methodological considerations, please refer to the accompanying schedules and appendices attached to this disclosure document. " * 3,
            f"This page corresponds to L-page identifier L-{i} as per IRDAI guidelines and regulatory requirements for public disclosure of financial information. " * 3,
            f"Additional context and background information: The insurance industry in India has seen significant growth over the past fiscal year, with increasing penetration in both urban and rural markets. " * 2,
            f"Regulatory compliance note: This disclosure is prepared in accordance with IRDAI (Preparation of Financial Statements and Auditor's Report of Insurance Companies) Regulations, 2002. " * 2
        ]
        
        # Create multiple tables per page for more realistic content
        tables = []
        for table_idx in range(2):  # 2 tables per page
            tables.append({
                "headers": ["Particulars", "Current Quarter (Rs '000)", "Previous Quarter (Rs '000)", "Year to Date (Rs '000)", "Growth %"],
                "rows": table_rows,
                "raw_text": "Particulars | Current Quarter (Rs '000) | Previous Quarter (Rs '000) | Year to Date (Rs '000) | Growth %\n" + 
                           "\n".join([" | ".join(row) for row in table_rows])
            })
        
        page = {
            "page_number": i,
            "page_label": f"L-{i}",
            "section": f"Section {(i-1) % 10 + 1}",  # Rotate through 10 sections
            "tables": tables,
            "text_blocks": text_blocks
        }
        pages.append(page)
    
    return {
        "company": "Test Insurance Company",
        "company_code": "TEST_INS",
        "quarter": "Q3",
        "fy": "FY26",
        "period_label": "Q3 FY2025-26",
        "source_file": "TEST_INS_Q3_FY26.pdf",
        "total_pages": num_pages,
        "page_definitions_found": True,
        "pages": pages
    }


@pytest.mark.benchmark
def test_page_wise_chunking_performance_50_pages():
    """
    Test processing time for 50-page PDF with page-wise chunking.
    Requirement 7.4: Process 50-page PDF in less than 5 seconds.
    """
    if not PAGE_WISE_CHUNKING:
        pytest.skip("PAGE_WISE_CHUNKING is disabled")
    
    # Create test document
    parsed_doc = create_large_test_document(num_pages=50)
    
    # Track performance
    metrics = PerformanceMetrics()
    metrics.start()
    
    # Run chunking
    chunks = chunk_document(parsed_doc)
    
    metrics.stop()
    
    # Get performance report
    report = metrics.report()
    
    # Print detailed report
    print("\n" + "="*60)
    print("PAGE-WISE CHUNKING PERFORMANCE (50 pages)")
    print("="*60)
    print(f"Processing Time: {report['elapsed_time_seconds']:.3f} seconds")
    print(f"Memory Delta: {report['memory_delta_mb']:.2f} MB")
    print(f"Peak Memory: {report['peak_memory_mb']:.2f} MB")
    print(f"Avg CPU Usage: {report['avg_cpu_percent']:.1f}%")
    print(f"Total Chunks: {len(chunks)}")
    print(f"Avg Chunk Size: {sum(c['metadata']['char_count'] for c in chunks) / len(chunks):.0f} chars")
    print("="*60)
    
    # Verify performance requirement: < 5 seconds
    assert report['elapsed_time_seconds'] < 5.0, \
        f"Processing took {report['elapsed_time_seconds']:.3f}s, expected < 5.0s"
    
    # Verify chunk count is reasonable (should be ~50 for 50 pages)
    assert 40 <= len(chunks) <= 60, \
        f"Expected ~50 chunks for 50 pages, got {len(chunks)}"


@pytest.mark.benchmark
def test_text_based_chunking_performance_50_pages():
    """
    Test processing time for 50-page PDF with text-based chunking.
    Used as baseline for comparison.
    """
    # Temporarily disable page-wise chunking
    import src.config as config
    original_setting = config.PAGE_WISE_CHUNKING
    config.PAGE_WISE_CHUNKING = False
    
    try:
        # Create test document
        parsed_doc = create_large_test_document(num_pages=50)
        
        # Track performance
        metrics = PerformanceMetrics()
        metrics.start()
        
        # Run chunking
        chunks = chunk_document(parsed_doc)
        
        metrics.stop()
        
        # Get performance report
        report = metrics.report()
        
        # Print detailed report
        print("\n" + "="*60)
        print("TEXT-BASED CHUNKING PERFORMANCE (50 pages)")
        print("="*60)
        print(f"Processing Time: {report['elapsed_time_seconds']:.3f} seconds")
        print(f"Memory Delta: {report['memory_delta_mb']:.2f} MB")
        print(f"Peak Memory: {report['peak_memory_mb']:.2f} MB")
        print(f"Avg CPU Usage: {report['avg_cpu_percent']:.1f}%")
        print(f"Total Chunks: {len(chunks)}")
        print(f"Avg Chunk Size: {sum(c['metadata']['char_count'] for c in chunks) / len(chunks):.0f} chars")
        print("="*60)
        
        # Store for comparison
        return {
            "chunks": len(chunks),
            "time": report['elapsed_time_seconds'],
            "memory": report['memory_delta_mb']
        }
    
    finally:
        # Restore original setting
        config.PAGE_WISE_CHUNKING = original_setting


@pytest.mark.benchmark
def test_chunk_count_reduction():
    """
    Test that page-wise chunking reduces chunk count by at least 75%.
    Requirement 7.3: Reduce total chunk count by at least 75%.
    """
    # Create test document
    parsed_doc = create_large_test_document(num_pages=50)
    
    # Get text-based chunk count
    import src.config as config
    original_setting = config.PAGE_WISE_CHUNKING
    
    # Text-based chunking
    config.PAGE_WISE_CHUNKING = False
    text_chunks = chunk_document(parsed_doc)
    text_chunk_count = len(text_chunks)
    
    # Page-wise chunking
    config.PAGE_WISE_CHUNKING = True
    page_chunks = chunk_document(parsed_doc)
    page_chunk_count = len(page_chunks)
    
    # Restore original setting
    config.PAGE_WISE_CHUNKING = original_setting
    
    # Calculate reduction percentage
    reduction_percent = ((text_chunk_count - page_chunk_count) / text_chunk_count) * 100
    
    # Print comparison
    print("\n" + "="*60)
    print("CHUNK COUNT REDUCTION ANALYSIS")
    print("="*60)
    print(f"Text-based chunks: {text_chunk_count}")
    print(f"Page-wise chunks: {page_chunk_count}")
    print(f"Reduction: {text_chunk_count - page_chunk_count} chunks ({reduction_percent:.1f}%)")
    print("="*60)
    
    # Verify reduction is at least 75%
    assert reduction_percent >= 75.0, \
        f"Chunk reduction is {reduction_percent:.1f}%, expected ≥ 75%"


@pytest.mark.benchmark
def test_performance_comparison():
    """
    Compare page-wise vs text-based chunking performance.
    Generates a comprehensive comparison report.
    """
    # Create test document
    parsed_doc = create_large_test_document(num_pages=50)
    
    import src.config as config
    original_setting = config.PAGE_WISE_CHUNKING
    
    # Test text-based chunking
    config.PAGE_WISE_CHUNKING = False
    text_metrics = PerformanceMetrics()
    text_metrics.start()
    text_chunks = chunk_document(parsed_doc)
    text_metrics.stop()
    text_report = text_metrics.report()
    
    # Test page-wise chunking
    config.PAGE_WISE_CHUNKING = True
    page_metrics = PerformanceMetrics()
    page_metrics.start()
    page_chunks = chunk_document(parsed_doc)
    page_metrics.stop()
    page_report = page_metrics.report()
    
    # Restore original setting
    config.PAGE_WISE_CHUNKING = original_setting
    
    # Calculate improvements
    time_improvement = ((text_report['elapsed_time_seconds'] - page_report['elapsed_time_seconds']) / 
                       text_report['elapsed_time_seconds']) * 100
    chunk_reduction = ((len(text_chunks) - len(page_chunks)) / len(text_chunks)) * 100
    
    # Print comprehensive comparison
    print("\n" + "="*60)
    print("PERFORMANCE COMPARISON: TEXT-BASED vs PAGE-WISE")
    print("="*60)
    print(f"\nDocument: 50 pages")
    print(f"\nTEXT-BASED CHUNKING:")
    print(f"  - Processing Time: {text_report['elapsed_time_seconds']:.3f}s")
    print(f"  - Memory Delta: {text_report['memory_delta_mb']:.2f} MB")
    print(f"  - Total Chunks: {len(text_chunks)}")
    print(f"  - Avg Chunk Size: {sum(c['metadata']['char_count'] for c in text_chunks) / len(text_chunks):.0f} chars")
    print(f"\nPAGE-WISE CHUNKING:")
    print(f"  - Processing Time: {page_report['elapsed_time_seconds']:.3f}s")
    print(f"  - Memory Delta: {page_report['memory_delta_mb']:.2f} MB")
    print(f"  - Total Chunks: {len(page_chunks)}")
    print(f"  - Avg Chunk Size: {sum(c['metadata']['char_count'] for c in page_chunks) / len(page_chunks):.0f} chars")
    print(f"\nIMPROVEMENTS:")
    print(f"  - Time: {time_improvement:+.1f}% {'faster' if time_improvement > 0 else 'slower'}")
    print(f"  - Chunk Reduction: {chunk_reduction:.1f}%")
    print(f"  - Memory: {text_report['memory_delta_mb'] - page_report['memory_delta_mb']:+.2f} MB")
    print("="*60)
    
    # Verify requirements
    assert chunk_reduction >= 75.0, f"Chunk reduction {chunk_reduction:.1f}% < 75%"
    assert page_report['elapsed_time_seconds'] < 5.0, \
        f"Page-wise processing {page_report['elapsed_time_seconds']:.3f}s > 5.0s"


@pytest.mark.benchmark
@pytest.mark.skipif(not find_sample_pdf(), reason="No sample PDF found in data/pdfs/")
def test_real_pdf_performance():
    """
    Test performance with a real PDF file from the data directory.
    This provides real-world performance metrics.
    """
    pdf_path = find_sample_pdf()
    if not pdf_path:
        pytest.skip("No sample PDF found")
    
    print(f"\nTesting with real PDF: {pdf_path}")
    
    # Parse PDF
    parse_metrics = PerformanceMetrics()
    parse_metrics.start()
    parsed_doc = parse_pdf(pdf_path)
    parse_metrics.stop()
    
    if not parsed_doc or "pages" not in parsed_doc:
        pytest.skip("Failed to parse PDF")
    
    num_pages = len(parsed_doc.get("pages", []))
    
    # Chunk with page-wise strategy
    chunk_metrics = PerformanceMetrics()
    chunk_metrics.start()
    chunks = chunk_document(parsed_doc)
    chunk_metrics.stop()
    
    parse_report = parse_metrics.report()
    chunk_report = chunk_metrics.report()
    
    # Print report
    print("\n" + "="*60)
    print("REAL PDF PERFORMANCE TEST")
    print("="*60)
    print(f"PDF: {Path(pdf_path).name}")
    print(f"Pages: {num_pages}")
    print(f"\nPARSING:")
    print(f"  - Time: {parse_report['elapsed_time_seconds']:.3f}s")
    print(f"  - Memory: {parse_report['memory_delta_mb']:.2f} MB")
    print(f"\nCHUNKING:")
    print(f"  - Time: {chunk_report['elapsed_time_seconds']:.3f}s")
    print(f"  - Memory: {chunk_report['memory_delta_mb']:.2f} MB")
    print(f"  - Chunks Created: {len(chunks)}")
    print(f"  - Avg Chunk Size: {sum(c['metadata']['char_count'] for c in chunks) / len(chunks):.0f} chars")
    print(f"\nTOTAL:")
    print(f"  - Time: {parse_report['elapsed_time_seconds'] + chunk_report['elapsed_time_seconds']:.3f}s")
    print(f"  - Chunks per Page: {len(chunks) / num_pages:.2f}")
    print("="*60)
    
    # Verify reasonable performance
    if num_pages >= 50:
        assert chunk_report['elapsed_time_seconds'] < 5.0, \
            f"Chunking {num_pages} pages took {chunk_report['elapsed_time_seconds']:.3f}s, expected < 5.0s"


@pytest.mark.benchmark
def test_memory_efficiency():
    """
    Test memory efficiency of page-wise chunking.
    Ensures memory usage stays within reasonable bounds.
    """
    if not PAGE_WISE_CHUNKING:
        pytest.skip("PAGE_WISE_CHUNKING is disabled")
    
    # Create large test document
    parsed_doc = create_large_test_document(num_pages=100)
    
    # Track memory
    metrics = PerformanceMetrics()
    metrics.start()
    
    chunks = chunk_document(parsed_doc)
    
    metrics.stop()
    report = metrics.report()
    
    print("\n" + "="*60)
    print("MEMORY EFFICIENCY TEST (100 pages)")
    print("="*60)
    print(f"Memory Delta: {report['memory_delta_mb']:.2f} MB")
    print(f"Peak Memory: {report['peak_memory_mb']:.2f} MB")
    print(f"Chunks Created: {len(chunks)}")
    print(f"Memory per Chunk: {report['memory_delta_mb'] / len(chunks):.3f} MB")
    print("="*60)
    
    # Verify memory usage is reasonable (< 100 MB for 100 pages)
    assert report['memory_delta_mb'] < 100.0, \
        f"Memory usage {report['memory_delta_mb']:.2f} MB exceeds 100 MB threshold"


@pytest.mark.benchmark
def test_scalability():
    """
    Test scalability with varying document sizes.
    Verifies linear scaling of processing time.
    """
    if not PAGE_WISE_CHUNKING:
        pytest.skip("PAGE_WISE_CHUNKING is disabled")
    
    page_counts = [10, 25, 50, 100]
    results = []
    
    print("\n" + "="*60)
    print("SCALABILITY TEST")
    print("="*60)
    
    for num_pages in page_counts:
        parsed_doc = create_large_test_document(num_pages=num_pages)
        
        metrics = PerformanceMetrics()
        metrics.start()
        chunks = chunk_document(parsed_doc)
        metrics.stop()
        
        report = metrics.report()
        time_per_page = report['elapsed_time_seconds'] / num_pages
        
        results.append({
            "pages": num_pages,
            "time": report['elapsed_time_seconds'],
            "chunks": len(chunks),
            "time_per_page": time_per_page
        })
        
        print(f"\n{num_pages} pages:")
        print(f"  - Total Time: {report['elapsed_time_seconds']:.3f}s")
        print(f"  - Time per Page: {time_per_page:.4f}s")
        print(f"  - Chunks: {len(chunks)}")
    
    print("="*60)
    
    # Verify roughly linear scaling (time per page should be consistent)
    times_per_page = [r['time_per_page'] for r in results]
    avg_time_per_page = sum(times_per_page) / len(times_per_page)
    max_deviation = max(abs(t - avg_time_per_page) for t in times_per_page)
    
    print(f"\nAvg Time per Page: {avg_time_per_page:.4f}s")
    print(f"Max Deviation: {max_deviation:.4f}s")
    
    # Allow 50% deviation for linear scaling
    assert max_deviation < avg_time_per_page * 0.5, \
        "Processing time does not scale linearly"


if __name__ == "__main__":
    # Run benchmark tests with verbose output
    pytest.main([__file__, "-v", "-s", "-m", "benchmark"])
