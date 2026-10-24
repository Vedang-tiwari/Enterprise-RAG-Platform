"""Conversations API router for retrieving message histories and citations."""
from typing import List, Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.api.deps import get_current_user, get_tenant_context
from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.models.organization import Organization, Membership
from backend.app.models.conversation import Conversation, Message, Citation
from backend.app.schemas.chat import ConversationDetailResponse, ConversationResponse, MessageResponse, CitationResponse

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.get("", response_model=List[ConversationResponse])
async def list_conversations(
    workspace_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    tenant: Tuple[Organization, Membership] = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """List all conversations for current user in active organization/workspace."""
    org, _ = tenant
    stmt = (
        select(Conversation)
        .where(
            Conversation.user_id == current_user.id,
            Conversation.organization_id == org.id
        )
    )
    if workspace_id:
        stmt = stmt.where(Conversation.workspace_id == workspace_id)

    stmt = stmt.order_by(Conversation.updated_at.desc())
    res = await db.execute(stmt)
    convs = res.scalars().all()

    results = []
    for c in convs:
        # Count messages
        m_count = await db.scalar(
            select(func.count(Message.id)).where(Message.conversation_id == c.id)
        )
        results.append(
            ConversationResponse(
                id=c.id,
                title=c.title,
                workspace_id=c.workspace_id,
                created_at=c.created_at,
                updated_at=c.updated_at,
                message_count=m_count or 0
            )
        )
    return results


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    tenant: Tuple[Organization, Membership] = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve full conversation history with messages and citations."""
    org, _ = tenant
    stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.organization_id == org.id,
        Conversation.user_id == current_user.id
    )
    res = await db.execute(stmt)
    conv = res.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

    # Get messages
    m_stmt = (
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at.asc())
    )
    m_res = await db.execute(m_stmt)
    messages = m_res.scalars().all()

    msg_responses = []
    for msg in messages:
        # Get citations
        c_stmt = select(Citation).where(Citation.message_id == msg.id)
        c_res = await db.execute(c_stmt)
        citations = c_res.scalars().all()

        cite_responses = [
            CitationResponse(
                id=c.id,
                chunk_id=c.chunk_id,
                document_name=c.document_name,
                page_number=c.page_number,
                snippet=c.snippet,
                relevance_score=c.relevance_score
            )
            for c in citations
        ]

        msg_responses.append(
            MessageResponse(
                id=msg.id,
                conversation_id=msg.conversation_id,
                sender_role=msg.sender_role,
                content=msg.content,
                token_count=msg.token_count,
                created_at=msg.created_at,
                citations=cite_responses
            )
        )

    return ConversationDetailResponse(
        id=conv.id,
        title=conv.title,
        workspace_id=conv.workspace_id,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=len(messages),
        messages=msg_responses
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    tenant: Tuple[Organization, Membership] = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """Delete a conversation."""
    org, _ = tenant
    stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.organization_id == org.id,
        Conversation.user_id == current_user.id
    )
    res = await db.execute(stmt)
    conv = res.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

    await db.delete(conv)
    await db.commit()
    return None
