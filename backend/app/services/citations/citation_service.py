"""Citation Service linking grounded responses to source chunks."""
from typing import List, Dict, Any
from backend.app.services.retrieval.retrieval_service import ScoredChunk


class CitationService:
    @staticmethod
    def generate_citations(retrieved_chunks: List[ScoredChunk], max_citations: int = 5) -> List[Dict[str, Any]]:
        citations: List[Dict[str, Any]] = []

        for idx, chunk in enumerate(retrieved_chunks[:max_citations]):
            doc_name = chunk.metadata.get("document_name", "Document")
            page = chunk.metadata.get("page_number", 1)
            # Create a clean concise snippet of up to 250 characters
            snippet = chunk.text[:250].strip()
            if len(chunk.text) > 250:
                snippet += "..."

            citations.append({
                "chunk_id": chunk.chunk_id,
                "document_name": doc_name,
                "page_number": page,
                "snippet": snippet,
                "relevance_score": round(chunk.score, 4),
                "source_index": idx + 1
            })

        return citations


citation_service = CitationService()
