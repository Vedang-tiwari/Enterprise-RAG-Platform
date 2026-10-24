"""Semantic & Recursive Character Chunker with deterministic chunk IDs."""
import hashlib
import re
from typing import List, Dict, Any
from backend.app.services.ingestion.parser import ParsedPage


class TextChunk:
    def __init__(
        self,
        chunk_id: str,
        chunk_index: int,
        content: str,
        token_count: int,
        page_number: int,
        section: str,
        metadata: Dict[str, Any]
    ):
        self.chunk_id = chunk_id
        self.chunk_index = chunk_index
        self.content = content
        self.token_count = token_count
        self.page_number = page_number
        self.section = section
        self.metadata = metadata


class TextChunker:
    """Splits text into semantically coherent overlapping chunks with rich metadata."""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 100):
        # 1 token ≈ 4 characters
        self.chunk_char_size = chunk_size * 4
        self.chunk_char_overlap = chunk_overlap * 4
        self.separators = ["\n\n", "\n", ". ", "? ", "! ", "; ", " ", ""]

    def chunk_pages(
        self,
        pages: List[ParsedPage],
        document_id: str,
        version_id: str,
        organization_id: str,
        workspace_id: str,
        document_name: str
    ) -> List[TextChunk]:
        all_chunks: List[TextChunk] = []
        global_chunk_idx = 0

        for page in pages:
            text = page.text
            if not text:
                continue

            raw_splits = self._recursive_split(text, self.chunk_char_size, self.chunk_char_overlap)

            for split_text in raw_splits:
                cleaned = split_text.strip()
                if len(cleaned) < 30:  # Ignore trivial snippets
                    continue

                # Generate deterministic chunk ID based on document, version and index
                raw_key = f"{document_id}:{version_id}:{global_chunk_idx}"
                chunk_id = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:32]
                approx_tokens = max(1, len(cleaned) // 4)

                meta = {
                    "document_id": document_id,
                    "version_id": version_id,
                    "organization_id": organization_id,
                    "workspace_id": workspace_id,
                    "document_name": document_name,
                    "page_number": page.page_number,
                    "section": page.section,
                    "chunk_index": global_chunk_idx,
                    "token_count": approx_tokens
                }

                chunk = TextChunk(
                    chunk_id=chunk_id,
                    chunk_index=global_chunk_idx,
                    content=cleaned,
                    token_count=approx_tokens,
                    page_number=page.page_number,
                    section=page.section,
                    metadata=meta
                )
                all_chunks.append(chunk)
                global_chunk_idx += 1

        return all_chunks

    def _recursive_split(self, text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
        if len(text) <= chunk_size:
            return [text]

        splits: List[str] = []
        # Find appropriate separator
        chosen_sep = ""
        for sep in self.separators:
            if sep in text:
                chosen_sep = sep
                break

        if chosen_sep:
            parts = text.split(chosen_sep)
        else:
            parts = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size - chunk_overlap)]
            return parts

        current_chunk = ""
        for part in parts:
            candidate = f"{current_chunk}{chosen_sep}{part}" if current_chunk else part
            if len(candidate) <= chunk_size:
                current_chunk = candidate
            else:
                if current_chunk:
                    splits.append(current_chunk)
                    # Create overlap from end of current_chunk
                    overlap_len = min(len(current_chunk), chunk_overlap)
                    overlap_prefix = current_chunk[-overlap_len:] if overlap_len > 0 else ""
                    current_chunk = f"{overlap_prefix}{chosen_sep}{part}" if overlap_prefix else part
                else:
                    splits.append(part)
                    current_chunk = ""

        if current_chunk:
            splits.append(current_chunk)

        return splits
