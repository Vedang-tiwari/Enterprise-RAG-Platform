"""Unit tests for Hybrid Retrieval (Vector + BM25 with RRF) and Reranker."""
import pytest
from backend.app.services.ingestion.parser import ParsedPage
from backend.app.services.ingestion.chunker import TextChunker
from backend.app.services.embeddings.embedding_service import embedding_service
from backend.app.services.retrieval.retrieval_service import retrieval_service
from backend.app.services.reranking.reranker_service import reranker_service


@pytest.mark.asyncio
async def test_hybrid_search_and_rrf():
    pages = [
        ParsedPage(page_number=1, text="Employees are permitted to work remotely up to three working days per week."),
        ParsedPage(page_number=2, text="Database error code E1047 indicates connection pool exhaustion under heavy traffic.")
    ]
    chunker = TextChunker()
    chunks = chunker.chunk_pages(pages, "doc-test", "v1", "org-test", "ws-test", "manual.pdf")

    texts = [c.content for c in chunks]
    vectors = await embedding_service.get_embeddings(texts)
    await retrieval_service.upsert_chunks(chunks, vectors)

    # 1. Test semantic query
    results_semantic = await retrieval_service.hybrid_search(
        query="How many days can I telecommute from home?",
        organization_id="org-test",
        workspace_id="ws-test",
        top_k=2
    )
    assert len(results_semantic) > 0
    assert "remotely" in results_semantic[0].text.lower()

    # 2. Test exact keyword code query (BM25 advantage)
    results_keyword = await retrieval_service.hybrid_search(
        query="E1047",
        organization_id="org-test",
        workspace_id="ws-test",
        top_k=2
    )
    assert len(results_keyword) > 0
    assert "E1047" in results_keyword[0].text

    # 3. Test multi-tenancy isolation
    results_other_org = await retrieval_service.hybrid_search(
        query="remotely",
        organization_id="unauthorized-org",
        workspace_id="ws-test",
        top_k=2
    )
    assert len(results_other_org) == 0


def test_reranker():
    from backend.app.services.retrieval.retrieval_service import ScoredChunk

    candidates = [
        ScoredChunk("c1", "Lunch cafeteria menu options on Tuesdays.", 0.2, {}),
        ScoredChunk("c2", "Full remote work policy: Employees may work remotely up to 3 days per week.", 0.5, {})
    ]

    reranked = reranker_service.rerank("What is the remote work policy?", candidates, top_k=2)
    assert len(reranked) == 2
    assert reranked[0].chunk_id == "c2"
    assert reranked[0].score > reranked[1].score
