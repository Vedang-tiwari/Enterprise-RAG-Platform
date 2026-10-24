"""Asynchronous document ingestion worker pipeline with idempotent chunk upserting."""
import asyncio
import traceback
from typing import Optional
from sqlalchemy import select, update
from backend.app.core.logging import logger, metrics
from backend.app.db.session import async_session_maker
from backend.app.models.document import Document, DocumentVersion, Chunk
from backend.app.models.usage import IngestionJob
from backend.app.services.ingestion.parser import DocumentParser
from backend.app.services.ingestion.chunker import TextChunker
from backend.app.services.embeddings.embedding_service import embedding_service
from backend.app.services.retrieval.retrieval_service import retrieval_service


async def execute_ingestion_pipeline(
    document_id: str,
    file_path: str,
    file_type: str,
    organization_id: str,
    workspace_id: str,
    document_name: str
) -> None:
    """End-to-end ingestion pipeline: Parse -> Chunk -> Embed -> Index -> Ready."""
    logger.info(f"Starting ingestion pipeline for document_id={document_id} ({document_name})")

    async with async_session_maker() as db:
        # Create or update IngestionJob
        job = IngestionJob(
            document_id=document_id,
            status="RUNNING",
            current_step="PARSING"
        )
        db.add(job)

        # Update document status to PROCESSING
        await db.execute(
            update(Document)
            .where(Document.id == document_id)
            .values(status="PROCESSING", error_message="")
        )
        await db.commit()

        try:
            # 1. Parse Document
            logger.info(f"Parsing document {document_name} ({file_type})")
            pages = DocumentParser.parse(file_path, file_type)
            if not pages:
                raise ValueError("No extractable text found in the uploaded document.")

            job.current_step = "CHUNKING"
            await db.commit()

            # 2. Get active DocumentVersion
            v_stmt = select(DocumentVersion).where(
                DocumentVersion.document_id == document_id,
                DocumentVersion.is_active == True
            )
            v_res = await db.execute(v_stmt)
            version = v_res.scalar_one_or_none()
            if not version:
                raise ValueError(f"No active version found for document {document_id}")

            # 3. Chunk Document
            logger.info(f"Chunking document {document_name} ({len(pages)} pages)")
            chunker = TextChunker(chunk_size=500, chunk_overlap=100)
            chunks = chunker.chunk_pages(
                pages=pages,
                document_id=document_id,
                version_id=version.id,
                organization_id=organization_id,
                workspace_id=workspace_id,
                document_name=document_name
            )

            job.total_chunks = len(chunks)
            job.current_step = "EMBEDDING"
            await db.commit()

            # 4. Generate Embeddings
            logger.info(f"Generating embeddings for {len(chunks)} chunks")
            chunk_texts = [c.content for c in chunks]
            vectors = await embedding_service.get_embeddings(chunk_texts)

            job.current_step = "INDEXING"
            await db.commit()

            # 5. Hybrid Retrieval Indexing (Qdrant + In-memory BM25/Vector store)
            logger.info(f"Indexing {len(chunks)} vectors in retrieval store")
            await retrieval_service.upsert_chunks(chunks, vectors)

            # 6. Persist chunks to Relational Database
            for chunk, vec in zip(chunks, vectors):
                # Check if chunk already exists (idempotency)
                existing = await db.get(Chunk, chunk.chunk_id)
                if not existing:
                    db_chunk = Chunk(
                        id=chunk.chunk_id,
                        document_version_id=version.id,
                        chunk_index=chunk.chunk_index,
                        content=chunk.content,
                        token_count=chunk.token_count,
                        page_number=chunk.page_number,
                        section=chunk.section,
                        vector_id=chunk.chunk_id
                    )
                    db.add(db_chunk)

            version.chunk_count = len(chunks)
            job.processed_chunks = len(chunks)
            job.status = "COMPLETED"
            job.current_step = "READY"

            # 7. Mark document as READY
            await db.execute(
                update(Document)
                .where(Document.id == document_id)
                .values(status="READY", error_message="")
            )
            await db.commit()
            metrics.ingestion_jobs_completed += 1
            logger.info(f"Successfully indexed document {document_id} ({len(chunks)} chunks)")

        except Exception as e:
            err = f"{str(e)}\n{traceback.format_exc()}"
            logger.error(f"Ingestion pipeline failed for document {document_id}: {err}")
            job.status = "FAILED"
            job.error_message = str(e)
            await db.execute(
                update(Document)
                .where(Document.id == document_id)
                .values(status="FAILED", error_message=str(e)[:500])
            )
            await db.commit()
            metrics.ingestion_jobs_failed += 1


def enqueue_document_ingestion(
    document_id: str,
    file_path: str,
    file_type: str,
    organization_id: str,
    workspace_id: str,
    document_name: str
) -> None:
    """
    Enqueues ingestion asynchronously.
    Uses Celery if available, otherwise runs an in-process asyncio task for zero-friction local execution.
    """
    try:
        # Check Celery task
        from backend.app.workers.celery_app import celery_app
        celery_app.send_task(
            "backend.app.workers.tasks.celery_ingest_task",
            args=[document_id, file_path, file_type, organization_id, workspace_id, document_name]
        )
        logger.info(f"Dispatched document {document_id} to Celery queue")
    except Exception:
        # Graceful fallback to background asyncio task
        logger.info(f"Celery unavailable; running ingestion task in background asyncio event loop")
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                execute_ingestion_pipeline(
                    document_id, file_path, file_type, organization_id, workspace_id, document_name
                )
            )
        except RuntimeError:
            asyncio.run(
                execute_ingestion_pipeline(
                    document_id, file_path, file_type, organization_id, workspace_id, document_name
                )
            )
