"""
Setup verification script - checks if everything is configured correctly.
Run this after initial setup to verify the installation.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def check_python_version():
    """Check Python version."""
    print("Checking Python version...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 10:
        print(f"  ✓ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"  ✗ Python {version.major}.{version.minor}.{version.micro} (requires 3.10+)")
        return False


def check_dependencies():
    """Check if all required packages are installed."""
    print("\nChecking dependencies...")
    
    required = [
        'pdfplumber',
        'anthropic',
        'sentence_transformers',
        'chromadb',
        'dotenv',
        'streamlit',
        'pandas',
        'tqdm'
    ]
    
    missing = []
    
    for package in required:
        try:
            if package == 'dotenv':
                __import__('dotenv')
            elif package == 'sentence_transformers':
                __import__('sentence_transformers')
            else:
                __import__(package)
            print(f"  ✓ {package}")
        except ImportError:
            print(f"  ✗ {package} (not installed)")
            missing.append(package)
    
    if missing:
        print(f"\n  Missing packages: {', '.join(missing)}")
        print(f"  Install with: pip install -r requirements.txt")
        return False
    
    return True


def check_config():
    """Check configuration."""
    print("\nChecking configuration...")
    
    try:
        from src.config import (
            ANTHROPIC_API_KEY,
            CLAUDE_MODEL,
            CHROMA_DB_PATH,
            PDF_INPUT_DIR,
            PROCESSED_OUTPUT_DIR
        )
        
        # Check API key
        if ANTHROPIC_API_KEY:
            print(f"  ✓ ANTHROPIC_API_KEY is set")
        else:
            print(f"  ✗ ANTHROPIC_API_KEY is not set")
            print(f"    Please add your API key to .env file")
            return False
        
        # Check model
        print(f"  ✓ Claude Model: {CLAUDE_MODEL}")
        
        # Check directories
        if Path(PDF_INPUT_DIR).exists():
            print(f"  ✓ PDF input directory exists: {PDF_INPUT_DIR}")
        else:
            print(f"  ✗ PDF input directory not found: {PDF_INPUT_DIR}")
            return False
        
        if Path(PROCESSED_OUTPUT_DIR).exists():
            print(f"  ✓ Processed output directory exists: {PROCESSED_OUTPUT_DIR}")
        else:
            print(f"  ✗ Processed output directory not found: {PROCESSED_OUTPUT_DIR}")
            return False
        
        return True
    
    except Exception as e:
        print(f"  ✗ Configuration error: {e}")
        return False


def check_directories():
    """Check project directory structure."""
    print("\nChecking directory structure...")
    
    required_dirs = [
        'src',
        'app',
        'scripts',
        'data',
        'data/pdfs',
        'data/processed'
    ]
    
    all_exist = True
    
    for dir_path in required_dirs:
        if Path(dir_path).exists():
            print(f"  ✓ {dir_path}/")
        else:
            print(f"  ✗ {dir_path}/ (missing)")
            all_exist = False
    
    return all_exist


def check_pdf_files():
    """Check for PDF files."""
    print("\nChecking for PDF files...")
    
    from src.config import PDF_INPUT_DIR
    
    pdf_files = list(Path(PDF_INPUT_DIR).glob("*.pdf"))
    
    if pdf_files:
        print(f"  ✓ Found {len(pdf_files)} PDF file(s)")
        for pdf in pdf_files[:5]:  # Show first 5
            print(f"    - {pdf.name}")
        if len(pdf_files) > 5:
            print(f"    ... and {len(pdf_files) - 5} more")
    else:
        print(f"  ⚠ No PDF files found in {PDF_INPUT_DIR}")
        print(f"    Add PDF files to start ingestion")
    
    return True


def check_chromadb():
    """Check ChromaDB status."""
    print("\nChecking ChromaDB...")
    
    try:
        from src.embedder import get_collection_stats
        
        stats = get_collection_stats()
        
        print(f"  ✓ ChromaDB accessible")
        print(f"    Total Chunks: {stats['total_chunks']}")
        print(f"    Unique Files: {stats['unique_files']}")
        
        if stats['chunks_by_company']:
            print(f"    Indexed Companies:")
            for company, count in list(stats['chunks_by_company'].items())[:5]:
                print(f"      - {company}: {count} chunks")
        
        return True
    
    except Exception as e:
        print(f"  ✗ ChromaDB error: {e}")
        return False


def main():
    """Run all checks."""
    print("=" * 80)
    print("INSURANCE PD REPORT ANALYZER - SETUP VERIFICATION")
    print("=" * 80)
    print()
    
    checks = [
        ("Python Version", check_python_version),
        ("Dependencies", check_dependencies),
        ("Configuration", check_config),
        ("Directory Structure", check_directories),
        ("PDF Files", check_pdf_files),
        ("ChromaDB", check_chromadb)
    ]
    
    results = []
    
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ Error during {name} check: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    all_passed = True
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:10} {name}")
        if not result:
            all_passed = False
    
    print()
    
    if all_passed:
        print("✓ All checks passed! Your setup is ready.")
        print("\nNext steps:")
        print("  1. Add PDF files to data/pdfs/")
        print("  2. Run: python scripts/ingest_all.py")
        print("  3. Test: python scripts/test_query.py --q \"your question\"")
        print("  4. Launch UI: streamlit run app/streamlit_app.py")
    else:
        print("✗ Some checks failed. Please fix the issues above.")
        print("\nCommon fixes:")
        print("  - Install dependencies: pip install -r requirements.txt")
        print("  - Create .env file: copy .env.example .env")
        print("  - Add ANTHROPIC_API_KEY to .env file")
    
    print()


if __name__ == "__main__":
    main()
