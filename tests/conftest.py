from datetime import datetime
from unittest.mock import patch, MagicMock
import pytest

_TEST_CHUNKS = [
    {"text": "Gross Written Premium | 8432.15 | 7891.23\nNew Business Premium | 3241.50 | 2987.10", "metadata": {"chunk_id": "HDFC_Life_Q1_FY25_page3_chunk1", "company": "HDFC Life", "company_code": "HDFC_Life", "quarter": "Q1", "fy": "FY25", "period_label": "Q1 FY2024-25", "source_file": "HDFC_Life_Q1_FY25.pdf", "page_number": 3, "page_label": "L-1", "section": "Revenue Account", "content_type": "table", "char_count": 82, "ingested_at": datetime.now().isoformat()}},
    {"text": "Claim Settlement Ratio: 98.2%\nClaims Paid: 1245.30 Cr", "metadata": {"chunk_id": "SBI_Life_Q1_FY25_page5_chunk1", "company": "SBI Life", "company_code": "SBI_Life", "quarter": "Q1", "fy": "FY25", "period_label": "Q1 FY2024-25", "source_file": "SBI_Life_Q1_FY25.pdf", "page_number": 5, "page_label": "L-3", "section": "Claims", "content_type": "table", "char_count": 55, "ingested_at": datetime.now().isoformat()}},
    {"text": "Key Highlights: LIC achieved a Gross Written Premium of 20,456 Cr in Q1 FY2024-25.", "metadata": {"chunk_id": "LIC_Q1_FY25_page1_chunk1", "company": "LIC", "company_code": "LIC", "quarter": "Q1", "fy": "FY25", "period_label": "Q1 FY2024-25", "source_file": "LIC_Q1_FY25.pdf", "page_number": 1, "page_label": "", "section": "unknown", "content_type": "summary", "char_count": 85, "ingested_at": datetime.now().isoformat()}},
    {"text": "Persistency Ratio 13th month: 85.4%\nPersistency Ratio 25th month: 72.1%", "metadata": {"chunk_id": "ICICI_Pru_Q1_FY25_page7_chunk1", "company": "ICICI Pru", "company_code": "ICICI_Pru", "quarter": "Q1", "fy": "FY25", "period_label": "Q1 FY2024-25", "source_file": "ICICI_Pru_Q1_FY25.pdf", "page_number": 7, "page_label": "L-7", "section": "Persistency", "content_type": "table", "char_count": 70, "ingested_at": datetime.now().isoformat()}},
]

def _make_fake_embedding(text: str, dim: int = 1536):
    import hashlib
    h = hashlib.sha256(text.encode()).digest()
    return [((b % 200) - 100) / 100.0 for b in (h * (dim // len(h) + 1))[:dim]]

@pytest.fixture(scope="session")
def model():
    return None

@pytest.fixture
def temp_chroma(tmp_path):
    import chromadb
    from chromadb.config import Settings
    db_path = str(tmp_path / "test_chroma")
    client = chromadb.PersistentClient(path=db_path, settings=Settings(anonymized_telemetry=False, allow_reset=True))
    collection = client.get_or_create_collection("test_collection", metadata={"hnsw:space": "cosine"})
    texts = [c["text"] for c in _TEST_CHUNKS]
    ids = [c["metadata"]["chunk_id"] for c in _TEST_CHUNKS]
    metadatas = [c["metadata"] for c in _TEST_CHUNKS]
    embeddings = [_make_fake_embedding(t) for t in texts]
    collection.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
    with patch("src.embedder.CHROMA_DB_PATH", db_path), \
         patch("src.embedder.CHROMA_COLLECTION_NAME", "test_collection"):
        yield collection
