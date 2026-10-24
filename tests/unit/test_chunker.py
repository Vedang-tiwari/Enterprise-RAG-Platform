"""Unit tests for text chunker and deterministic ID generation."""
from backend.app.services.ingestion.parser import ParsedPage
from backend.app.services.ingestion.chunker import TextChunker


def test_chunker_splits_and_metadata():
    pages = [
        ParsedPage(page_number=1, text="Employees are permitted to work remotely for up to three working days per week. This policy applies to all full-time employees in good standing."),
        ParsedPage(page_number=2, text="For hardware expense reimbursement, submit receipts via the finance portal within thirty days of purchase.")
    ]

    chunker = TextChunker(chunk_size=50, chunk_overlap=10)
    chunks = chunker.chunk_pages(
        pages=pages,
        document_id="doc-1",
        version_id="ver-1",
        organization_id="org-1",
        workspace_id="ws-1",
        document_name="Policy.pdf"
    )

    assert len(chunks) >= 2
    for chunk in chunks:
        assert chunk.chunk_id is not None
        assert len(chunk.chunk_id) == 32
        assert chunk.metadata["document_id"] == "doc-1"
        assert chunk.metadata["organization_id"] == "org-1"
        assert chunk.metadata["workspace_id"] == "ws-1"
        assert chunk.page_number in [1, 2]


def test_chunker_idempotent_ids():
    pages = [ParsedPage(page_number=1, text="Consistent text for hashing test.")]
    chunker = TextChunker()

    run1 = chunker.chunk_pages(pages, "doc-1", "ver-1", "org-1", "ws-1", "test.txt")
    run2 = chunker.chunk_pages(pages, "doc-1", "ver-1", "org-1", "ws-1", "test.txt")

    assert run1[0].chunk_id == run2[0].chunk_id
