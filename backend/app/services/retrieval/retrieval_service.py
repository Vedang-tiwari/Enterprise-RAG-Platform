"""Hybrid Retrieval Service combining Dense Vector Search and BM25 with Reciprocal Rank Fusion."""
import re
from typing import Dict, List, Optional, Any
import numpy as np
from rank_bm25 import BM25Okapi
import httpx
from backend.app.core.config import settings
from backend.app.core.logging import logger, metrics
from backend.app.services.embeddings.embedding_service import embedding_service


class ScoredChunk:
    def __init__(
        self,
        chunk_id: str,
        text: str,
        score: float,
        metadata: Dict[str, Any]
    ):
        self.chunk_id = chunk_id
        self.text = text
        self.score = score
        self.metadata = metadata

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "score": round(self.score, 4),
            "metadata": self.metadata
        }


class RetrievalService:
    """Enterprise multi-tenant hybrid retrieval layer."""

    def __init__(self):
        # In-memory vector and metadata store (fallback or primary when standalone)
        # Key: chunk_id -> {"vector": np.array, "payload": dict}
        self._local_vectors: Dict[str, Dict[str, Any]] = {}
        self._qdrant_available: Optional[bool] = None

    async def check_qdrant_connection(self) -> bool:
        if not settings.QDRANT_URL:
            return False
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{settings.QDRANT_URL}/collections")
                self._qdrant_available = (resp.status_code == 200)
                return self._qdrant_available
        except Exception:
            self._qdrant_available = False
            return False

    async def upsert_chunks(self, chunks: List[Any], vectors: List[List[float]]) -> None:
        """Store chunk vectors and payloads idempotently."""
        for chunk, vec in zip(chunks, vectors):
            payload = {
                "chunk_id": chunk.chunk_id,
                "text": chunk.content,
                "document_id": chunk.metadata["document_id"],
                "version_id": chunk.metadata["version_id"],
                "organization_id": chunk.metadata["organization_id"],
                "workspace_id": chunk.metadata["workspace_id"],
                "document_name": chunk.metadata["document_name"],
                "page_number": chunk.page_number,
                "section": chunk.section,
                "token_count": chunk.token_count
            }
            # Always store in memory for fast local hybrid BM25 + vector search
            self._local_vectors[chunk.chunk_id] = {
                "vector": np.array(vec, dtype=np.float32),
                "payload": payload
            }

        # Attempt Qdrant remote upsert if accessible
        if self._qdrant_available is None:
            await self.check_qdrant_connection()

        if self._qdrant_available and settings.QDRANT_URL:
            try:
                points = [
                    {
                        "id": abs(hash(chunk.chunk_id)) % (10**12),
                        "vector": vec,
                        "payload": {
                            "chunk_id": chunk.chunk_id,
                            "text": chunk.content,
                            "organization_id": chunk.metadata["organization_id"],
                            "workspace_id": chunk.metadata["workspace_id"],
                            "document_id": chunk.metadata["document_id"]
                        }
                    }
                    for chunk, vec in zip(chunks, vectors)
                ]
                async with httpx.AsyncClient(timeout=5.0) as client:
                    await client.put(
                        f"{settings.QDRANT_URL}/collections/{settings.QDRANT_COLLECTION}/points",
                        json={"points": points}
                    )
            except Exception as e:
                logger.warning(f"Qdrant upsert error: {e}")

    async def hybrid_search(
        self,
        query: str,
        organization_id: str,
        workspace_id: str,
        top_k: int = 20,
        dense_weight: float = 0.7,
        lexical_weight: float = 0.3
    ) -> List[ScoredChunk]:
        """
        Executes dense vector search and BM25 lexical search,
        then fuses candidate lists via Reciprocal Rank Fusion (RRF).
        """
        # Filter candidate pool strictly by organization_id and workspace_id
        matching_chunks = [
            (cid, item["vector"], item["payload"])
            for cid, item in self._local_vectors.items()
            if item["payload"].get("organization_id") == organization_id
            and item["payload"].get("workspace_id") == workspace_id
        ]

        if not matching_chunks:
            return []

        # 1. Dense Vector Search
        query_vec = await embedding_service.get_embedding(query)
        q_arr = np.array(query_vec, dtype=np.float32)

        dense_scores = []
        for cid, vec, payload in matching_chunks:
            # Cosine similarity (vectors are L2-normalized)
            sim = float(np.dot(q_arr, vec))
            dense_scores.append((cid, sim, payload))

        # Sort descending by similarity
        dense_sorted = sorted(dense_scores, key=lambda x: x[1], reverse=True)
        dense_rank_map = {cid: rank + 1 for rank, (cid, _, _) in enumerate(dense_sorted)}

        # 2. Lexical BM25 Search
        corpus_texts = [payload["text"] for _, _, payload in matching_chunks]
        tokenized_corpus = [re.findall(r"\b\w+\b", t.lower()) for t in corpus_texts]
        tokenized_query = re.findall(r"\b\w+\b", query.lower())

        if tokenized_corpus and any(tokenized_corpus) and tokenized_query:
            bm25 = BM25Okapi(tokenized_corpus)
            bm25_raw = bm25.get_scores(tokenized_query)
            bm25_scores = [
                (matching_chunks[i][0], float(bm25_raw[i]), matching_chunks[i][2])
                for i in range(len(matching_chunks))
            ]
            bm25_sorted = sorted(bm25_scores, key=lambda x: x[1], reverse=True)
            lexical_rank_map = {cid: rank + 1 for rank, (cid, _, _) in enumerate(bm25_sorted)}
        else:
            lexical_rank_map = {cid: 100 for cid, _, _ in matching_chunks}

        # 3. Reciprocal Rank Fusion (RRF)
        # RRF Score = dense_weight / (60 + dense_rank) + lexical_weight / (60 + lexical_rank)
        rrf_results: List[ScoredChunk] = []
        k_const = 60.0

        payload_map = {cid: payload for cid, _, payload in matching_chunks}
        for cid, payload in payload_map.items():
            r_dense = dense_rank_map.get(cid, 999)
            r_lexical = lexical_rank_map.get(cid, 999)

            score = (dense_weight / (k_const + r_dense)) + (lexical_weight / (k_const + r_lexical))
            rrf_results.append(
                ScoredChunk(
                    chunk_id=cid,
                    text=payload["text"],
                    score=score,
                    metadata=payload
                )
            )

        # Sort by RRF score descending
        rrf_results.sort(key=lambda x: x.score, reverse=True)
        return rrf_results[:top_k]

    def delete_document_chunks(self, document_id: str) -> int:
        """Remove all chunks associated with a document."""
        to_del = [
            cid for cid, item in self._local_vectors.items()
            if item["payload"].get("document_id") == document_id
        ]
        for cid in to_del:
            del self._local_vectors[cid]
        return len(to_del)


retrieval_service = RetrievalService()
