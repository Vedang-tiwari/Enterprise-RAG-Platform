"""RAG Evaluation Harness: Recall@K, MRR, Faithfulness, and Citation Correctness."""
import pytest
from backend.app.services.ingestion.parser import ParsedPage
from backend.app.services.ingestion.chunker import TextChunker
from backend.app.services.embeddings.embedding_service import embedding_service
from backend.app.services.retrieval.retrieval_service import retrieval_service
from backend.app.services.reranking.reranker_service import reranker_service
from backend.app.services.llm.llm_service import llm_service
from backend.app.services.citations.citation_service import citation_service


EVALUATION_DATASET = [
    {
        "question": "How many days are employees permitted to work remotely each week?",
        "expected_answer_keywords": ["three", "3", "remotely"],
        "expected_doc": "Employee_Handbook.pdf",
        "expected_page": 17
    },
    {
        "question": "What is the policy for defective product refunds?",
        "expected_answer_keywords": ["refund", "30 days", "defective"],
        "expected_doc": "Return_Policy.pdf",
        "expected_page": 4
    }
]


@pytest.mark.asyncio
async def test_rag_benchmark_metrics():
    # 1. Setup benchmark documents in retrieval index
    docs = [
        (
            "Employee_Handbook.pdf",
            [
                ParsedPage(17, "Employees are permitted to work from an alternative location or remotely for a maximum of three working days per week."),
                ParsedPage(18, "Annual leave accrual rate is 1.66 days per calendar month.")
            ]
        ),
        (
            "Return_Policy.pdf",
            [
                ParsedPage(4, "For defective products, customers can request a full refund within 30 days of receiving the item."),
                ParsedPage(5, "Shipping fees for returns are non-refundable unless verified as manufacturer defect.")
            ]
        )
    ]

    chunker = TextChunker()
    org_id = "eval-org"
    ws_id = "eval-ws"

    for doc_name, pages in docs:
        chunks = chunker.chunk_pages(pages, f"doc-{doc_name}", "v1", org_id, ws_id, doc_name)
        vectors = await embedding_service.get_embeddings([c.content for c in chunks])
        await retrieval_service.upsert_chunks(chunks, vectors)

    recalls_at_5 = []
    reciprocal_ranks = []
    faithfulness_scores = []
    citation_accuracies = []

    for item in EVALUATION_DATASET:
        query = item["question"]

        # Retrieval & Rerank
        candidates = await retrieval_service.hybrid_search(query, org_id, ws_id, top_k=20)
        reranked = reranker_service.rerank(query, candidates, top_k=5)
        print(f"\n[DEBUG] Query: {query}")
        for idx, c in enumerate(reranked):
            print(f"  [{idx+1}] doc={c.metadata.get('document_name')} page={c.metadata.get('page_number')} score={c.score} text={c.text[:50]}")

        # 1. Compute Recall@5 & MRR
        rank = None
        for i, chunk in enumerate(reranked):
            if chunk.metadata.get("document_name") == item["expected_doc"]:
                rank = i + 1
                break

        if rank is not None and rank <= 5:
            recalls_at_5.append(1.0)
            reciprocal_ranks.append(1.0 / rank)
        else:
            recalls_at_5.append(0.0)
            reciprocal_ranks.append(0.0)

        # 2. LLM Generation
        answer = await llm_service.generate(query, reranked)

        # 3. Faithfulness: check if expected keywords appear in answer
        matched_kw = sum(1 for kw in item["expected_answer_keywords"] if kw.lower() in answer.lower())
        faithfulness = matched_kw / len(item["expected_answer_keywords"])
        faithfulness_scores.append(faithfulness)

        # 4. Citation Correctness
        citations = citation_service.generate_citations(reranked)
        has_correct_citation = any(
            c["document_name"] == item["expected_doc"] and c["page_number"] == item["expected_page"]
            for c in citations
        )
        citation_accuracies.append(1.0 if has_correct_citation else 0.0)

    # Compute overall benchmark averages
    avg_recall = sum(recalls_at_5) / len(recalls_at_5)
    avg_mrr = sum(reciprocal_ranks) / len(reciprocal_ranks)
    avg_faithfulness = sum(faithfulness_scores) / len(faithfulness_scores)
    avg_citation_acc = sum(citation_accuracies) / len(citation_accuracies)

    print(f"\n--- RAG EVALUATION BENCHMARK RESULTS ---")
    print(f"Recall@5:            {avg_recall * 100:.1f}%")
    print(f"Mean Reciprocal Rank: {avg_mrr:.3f}")
    print(f"Faithfulness Score:  {avg_faithfulness * 100:.1f}%")
    print(f"Citation Accuracy:   {avg_citation_acc * 100:.1f}%")

    assert avg_recall >= 0.8, f"Recall@5 was too low: {avg_recall}"
    assert avg_mrr >= 0.5, f"MRR was too low: {avg_mrr}"
    assert avg_faithfulness >= 0.6, f"Faithfulness was too low: {avg_faithfulness}"
    assert avg_citation_acc >= 0.8, f"Citation accuracy was too low: {avg_citation_acc}"
