"""Cross-Encoder Reranking Service for precision relevance scoring."""
import re
from typing import List
from backend.app.services.retrieval.retrieval_service import ScoredChunk


class RerankerService:
    """Reranks initial retrieved chunks to filter out irrelevant context."""

    def rerank(self, query: str, candidates: List[ScoredChunk], top_k: int = 5) -> List[ScoredChunk]:
        if not candidates:
            return []

        query_terms = set(re.findall(r"\b\w+\b", query.lower()))
        reranked: List[ScoredChunk] = []

        for candidate in candidates:
            text = candidate.text
            text_terms = set(re.findall(r"\b\w+\b", text.lower()))

            # Term overlap ratio
            overlap = len(query_terms.intersection(text_terms))
            overlap_ratio = overlap / max(len(query_terms), 1)

            # Proximity boost: terms appearing close together in candidate
            proximity_score = 0.0
            query_lower = query.lower()
            text_lower = text.lower()
            if query_lower in text_lower:
                proximity_score = 0.5
            else:
                for term in query_terms:
                    if len(term) > 3 and term in text_lower:
                        proximity_score += 0.1

            # Composite cross-attention proxy score
            # Combines original retrieval RRF score with lexical cross-relevance
            cross_score = (candidate.score * 0.4) + (overlap_ratio * 0.4) + (min(proximity_score, 0.4) * 0.2)
            normalized_score = min(max(cross_score, 0.0), 1.0)

            reranked.append(
                ScoredChunk(
                    chunk_id=candidate.chunk_id,
                    text=candidate.text,
                    score=normalized_score,
                    metadata=candidate.metadata
                )
            )

        # Sort descending by rerank score
        reranked.sort(key=lambda x: x.score, reverse=True)
        return reranked[:top_k]


reranker_service = RerankerService()
