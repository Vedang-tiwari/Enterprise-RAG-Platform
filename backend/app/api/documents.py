"""Documents API router: upload, ingestion triggering, status polling, and deletion."""
import hashlib
import os
import shutil
from typing import List, Optional, Tuple
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.api.deps import get_tenant_context, require_role
from backend.app.core.config import settings
from backend.app.db.session import get_db
from backend.app.models.organization import Organization, Membership
from backend.app.models.workspace import Workspace
from backend.app.models.document import Document, DocumentVersion, Chunk
from backend.app.models.usage import IngestionJob
from backend.app.schemas.document import DocumentDetailResponse, DocumentResponse, IngestionStatusResponse
from backend.app.services.retrieval.retrieval_service import retrieval_service
from backend.app.workers.tasks import enqueue_document_ingestion

router = APIRouter(prefix="/documents", tags=["Documents"])

ALLOWED_EXTENSIONS = {"pdf", "docx", "doc", "txt", "md", "markdown", "html", "htm"}


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: UploadFile = File(...),
    workspace_id: str = Form(...),
    title: Optional[str] = Form(None),
    tenant: Tuple[Organization, Membership] = Depends(require_role("member")),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload and register a document (PDF, DOCX, TXT, MD, HTML).
    Triggers asynchronous ingestion pipeline in background.
    """
    org, _ = tenant

    # Verify workspace belongs to active organization
    ws = await db.get(Workspace, workspace_id)
    if not ws or ws.organization_id != org.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Specified workspace not found in active organization."
        )

    # Validate file extension
    ext = file.filename.split(".")[-1].lower() if file.filename and "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    # Prepare storage directory
    storage_folder = os.path.join(settings.STORAGE_DIR, org.id, workspace_id)
    os.makedirs(storage_folder, exist_ok=True)
    file_path = os.path.join(storage_folder, file.filename)

    # Stream file to disk and compute SHA256 hash
    hasher = hashlib.sha256()
    size = 0
    with open(file_path, "wb") as buffer:
        while chunk := await file.read(1024 * 64):  # 64KB chunks
            hasher.update(chunk)
            buffer.write(chunk)
            size += len(chunk)

    if size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB."
        )

    file_hash = hasher.hexdigest()
    doc_title = title or file.filename.rsplit(".", 1)[0]

    # Create Document record
    document = Document(
        title=doc_title,
        filename=file.filename,
        file_type=ext,
        file_size=size,
        storage_path=file_path,
        status="UPLOADED",
        organization_id=org.id,
        workspace_id=workspace_id
    )
    db.add(document)
    await db.flush()

    # Create DocumentVersion record
    version = DocumentVersion(
        document_id=document.id,
        version_number=1,
        file_hash=file_hash,
        is_active=True
    )
    db.add(version)
    await db.commit()
    await db.refresh(document)

    # Dispatch asynchronous background ingestion
    enqueue_document_ingestion(
        document_id=document.id,
        file_path=file_path,
        file_type=ext,
        organization_id=org.id,
        workspace_id=workspace_id,
        document_name=document.filename
    )

    return document


@router.get("", response_model=List[DocumentResponse])
async def list_documents(
    workspace_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    tenant: Tuple[Organization, Membership] = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """List documents for active organization, optionally filtered by workspace."""
    org, _ = tenant
    stmt = select(Document).where(Document.organization_id == org.id)
    if workspace_id:
        stmt = stmt.where(Document.workspace_id == workspace_id)
    if status_filter:
        stmt = stmt.where(Document.status == status_filter.upper())

    stmt = stmt.order_by(Document.created_at.desc())
    res = await db.execute(stmt)
    return res.scalars().all()


@router.get("/{document_id}", response_model=DocumentDetailResponse)
async def get_document_details(
    document_id: str,
    tenant: Tuple[Organization, Membership] = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed document information including chunk counts and version history."""
    org, _ = tenant
    stmt = select(Document).where(Document.id == document_id, Document.organization_id == org.id)
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    # Count indexed chunks for active version
    chunk_count_stmt = (
        select(func.count(Chunk.id))
        .join(DocumentVersion, Chunk.document_version_id == DocumentVersion.id)
        .where(DocumentVersion.document_id == doc.id, DocumentVersion.is_active == True)
    )
    chunk_count_res = await db.execute(chunk_count_stmt)
    total_chunks = chunk_count_res.scalar_one() or 0

    return DocumentDetailResponse(
        id=doc.id,
        title=doc.title,
        filename=doc.filename,
        file_type=doc.file_type,
        file_size=doc.file_size,
        status=doc.status,
        error_message=doc.error_message,
        organization_id=doc.organization_id,
        workspace_id=doc.workspace_id,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        chunk_count=total_chunks,
        versions=[]
    )


@router.get("/{document_id}/status", response_model=IngestionStatusResponse)
async def get_ingestion_status(
    document_id: str,
    tenant: Tuple[Organization, Membership] = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """Poll document processing and ingestion progress."""
    org, _ = tenant
    doc = await db.get(Document, document_id)
    if not doc or doc.organization_id != org.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    # Get latest IngestionJob
    job_stmt = (
        select(IngestionJob)
        .where(IngestionJob.document_id == document_id)
        .order_by(IngestionJob.created_at.desc())
    )
    job_res = await db.execute(job_stmt)
    job = job_res.scalars().first()

    return IngestionStatusResponse(
        document_id=doc.id,
        status=doc.status,
        current_step=job.current_step if job else doc.status,
        processed_chunks=job.processed_chunks if job else 0,
        total_chunks=job.total_chunks if job else 0,
        error_message=doc.error_message
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    tenant: Tuple[Organization, Membership] = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db)
):
    """
    Permanently delete a document across all storage layers:
    Relational DB + Local disk / S3 + Vector Store (Qdrant).
    """
    org, _ = tenant
    doc = await db.get(Document, document_id)
    if not doc or doc.organization_id != org.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    # 1. Remove physical file
    if os.path.exists(doc.storage_path):
        try:
            os.remove(doc.storage_path)
        except Exception:
            pass

    # 2. Remove vectors from retrieval index
    retrieval_service.delete_document_chunks(doc.id)

    # 3. Delete from DB (cascades to DocumentVersion, Chunk, IngestionJob)
    await db.delete(doc)
    await db.commit()
    return None
