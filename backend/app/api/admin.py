"""Admin and Telemetry API router."""
from typing import Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.api.deps import require_role
from backend.app.core.logging import metrics
from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.models.organization import Organization
from backend.app.models.workspace import Workspace
from backend.app.models.document import Document, Chunk
from backend.app.models.conversation import Message
from backend.app.schemas.usage import AdminMetricsResponse
from backend.app.services.retrieval.retrieval_service import retrieval_service

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/stats", response_model=AdminMetricsResponse, dependencies=[Depends(require_role("admin"))])
async def get_admin_stats(db: AsyncSession = Depends(get_db)):
    """Retrieve platform-wide operational statistics and resource counters."""
    users_count = await db.scalar(select(func.count(User.id))) or 0
    orgs_count = await db.scalar(select(func.count(Organization.id))) or 0
    workspaces_count = await db.scalar(select(func.count(Workspace.id))) or 0

    docs_count = await db.scalar(select(func.count(Document.id))) or 0
    ready_docs = await db.scalar(select(func.count(Document.id)).where(Document.status == "READY")) or 0
    failed_docs = await db.scalar(select(func.count(Document.id)).where(Document.status == "FAILED")) or 0

    chunks_count = await db.scalar(select(func.count(Chunk.id))) or 0
    questions_count = await db.scalar(
        select(func.count(Message.id)).where(Message.sender_role == "user")
    ) or 0

    return AdminMetricsResponse(
        users_count=users_count,
        organizations_count=orgs_count,
        workspaces_count=workspaces_count,
        documents_count=docs_count,
        ready_documents_count=ready_docs,
        failed_documents_count=failed_docs,
        indexed_chunks_count=chunks_count,
        total_questions_asked=questions_count,
        telemetry=metrics.get_summary()
    )


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Service health and connectivity probe."""
    db_healthy = False
    try:
        await db.execute(text("SELECT 1"))
        db_healthy = True
    except Exception:
        pass

    qdrant_status = await retrieval_service.check_qdrant_connection()

    return {
        "status": "healthy" if db_healthy else "degraded",
        "components": {
            "database": "connected" if db_healthy else "disconnected",
            "qdrant_vector_store": "connected" if qdrant_status else "in_memory_fallback",
            "background_worker": "active",
        },
        "telemetry": metrics.get_summary()
    }
