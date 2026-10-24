"""Conversational RAG Chat router with streaming responses and citations."""
import json
import time
from typing import Dict, List, Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sse_starlette.sse import EventSourceResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.api.deps import check_rate_limit, get_current_user, get_tenant_context
from backend.app.db.session import async_session_maker, get_db
from backend.app.models.user import User
from backend.app.models.organization import Organization, Membership
from backend.app.models.workspace import Workspace
from backend.app.models.conversation import Conversation, Message, Citation
from backend.app.schemas.chat import ChatRequest, MessageResponse, CitationResponse
from backend.app.services.retrieval.retrieval_service import retrieval_service
from backend.app.services.reranking.reranker_service import reranker_service
from backend.app.services.llm.llm_service import llm_service
from backend.app.services.citations.citation_service import citation_service
from backend.app.services.usage.usage_service import usage_service

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("", dependencies=[Depends(check_rate_limit)])
async def chat_rag(
    request: Request,
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    tenant: Tuple[Organization, Membership] = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """
    Execute enterprise RAG conversational query.
    Supports token streaming via Server-Sent Events (SSE) or JSON response.
    """
    start_time = time.time()
    org, _ = tenant

    # Verify workspace belongs to organization
    ws = await db.get(Workspace, payload.workspace_id)
    if not ws or ws.organization_id != org.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")

    # 1. Resolve or Create Conversation
    conversation = None
    if payload.conversation_id:
        c_stmt = select(Conversation).where(
            Conversation.id == payload.conversation_id,
            Conversation.workspace_id == ws.id,
            Conversation.user_id == current_user.id
        )
        c_res = await db.execute(c_stmt)
        conversation = c_res.scalar_one_or_none()

    if not conversation:
        title = payload.message[:40] + ("..." if len(payload.message) > 40 else "")
        conversation = Conversation(
            title=title,
            user_id=current_user.id,
            organization_id=org.id,
            workspace_id=ws.id
        )
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)

    # 2. Fetch Conversation History for multi-turn awareness
    hist_stmt = (
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.asc())
    )
    hist_res = await db.execute(hist_stmt)
    history_messages = [
        {"role": m.sender_role, "content": m.content}
        for m in hist_res.scalars().all()
    ]

    # 3. Hybrid Retrieval (Dense Vector + BM25 with RRF)
    retrieval_start = time.time()
    candidate_chunks = await retrieval_service.hybrid_search(
        query=payload.message,
        organization_id=org.id,
        workspace_id=ws.id,
        top_k=payload.top_k * 4
    )
    retrieval_duration_ms = (time.time() - retrieval_start) * 1000

    # 4. Cross-Encoder Reranking
    rerank_start = time.time()
    if payload.enable_rerank and candidate_chunks:
        final_chunks = reranker_service.rerank(payload.message, candidate_chunks, top_k=payload.top_k)
    else:
        final_chunks = candidate_chunks[:payload.top_k]
    rerank_duration_ms = (time.time() - rerank_start) * 1000

    # 5. Extract Citations
    citations_data = citation_service.generate_citations(final_chunks)

    # 6. Stream or Synchronous Response
    if payload.stream:
        async def event_generator():
            full_response = ""
            llm_start = time.time()

            try:
                # Stream initial metadata event
                init_event = {
                    "type": "meta",
                    "conversation_id": conversation.id,
                    "citations": citations_data
                }
                yield {"event": "metadata", "data": json.dumps(init_event)}

                # Stream token-by-token
                async for token in llm_service.generate_stream(
                    query=payload.message,
                    retrieved_chunks=final_chunks,
                    conversation_history=history_messages
                ):
                    full_response += token
                    yield {"event": "token", "data": json.dumps({"token": token})}

                llm_duration_ms = (time.time() - llm_start) * 1000
                total_duration_ms = (time.time() - start_time) * 1000

                # Persist messages and citations asynchronously
                async with async_session_maker() as save_db:
                    # User Message
                    user_msg = Message(
                        conversation_id=conversation.id,
                        sender_role="user",
                        content=payload.message,
                        token_count=max(1, len(payload.message) // 4)
                    )
                    save_db.add(user_msg)

                    # Assistant Message
                    assistant_msg = Message(
                        conversation_id=conversation.id,
                        sender_role="assistant",
                        content=full_response,
                        token_count=max(1, len(full_response) // 4)
                    )
                    save_db.add(assistant_msg)
                    await save_db.flush()

                    # Save Citations
                    for cite in citations_data:
                        c_obj = Citation(
                            message_id=assistant_msg.id,
                            chunk_id=cite["chunk_id"],
                            document_name=cite["document_name"],
                            page_number=cite["page_number"],
                            snippet=cite["snippet"],
                            relevance_score=cite["relevance_score"]
                        )
                        save_db.add(c_obj)

                    await save_db.commit()

                    # Record Usage Event
                    in_tokens = max(1, (len(payload.message) + sum(len(c.text) for c in final_chunks)) // 4)
                    out_tokens = max(1, len(full_response) // 4)
                    await usage_service.record_usage(
                        db=save_db,
                        user_id=current_user.id,
                        organization_id=org.id,
                        model=llm_service.provider,
                        input_tokens=in_tokens,
                        output_tokens=out_tokens,
                        latency_ms=total_duration_ms
                    )

                # Stream Done event
                done_event = {
                    "type": "done",
                    "conversation_id": conversation.id,
                    "latency_ms": round(total_duration_ms, 2)
                }
                yield {"event": "done", "data": json.dumps(done_event)}

            except Exception as e:
                yield {"event": "error", "data": json.dumps({"error": str(e)})}

        return EventSourceResponse(event_generator())

    else:
        # Non-streaming JSON response
        llm_start = time.time()
        full_response = await llm_service.generate(
            query=payload.message,
            retrieved_chunks=final_chunks,
            conversation_history=history_messages
        )
        total_duration_ms = (time.time() - start_time) * 1000

        # Save user message
        user_msg = Message(
            conversation_id=conversation.id,
            sender_role="user",
            content=payload.message,
            token_count=max(1, len(payload.message) // 4)
        )
        db.add(user_msg)

        # Save assistant message
        assistant_msg = Message(
            conversation_id=conversation.id,
            sender_role="assistant",
            content=full_response,
            token_count=max(1, len(full_response) // 4)
        )
        db.add(assistant_msg)
        await db.flush()

        # Save Citations
        saved_citations = []
        for cite in citations_data:
            c_obj = Citation(
                message_id=assistant_msg.id,
                chunk_id=cite["chunk_id"],
                document_name=cite["document_name"],
                page_number=cite["page_number"],
                snippet=cite["snippet"],
                relevance_score=cite["relevance_score"]
            )
            db.add(c_obj)
            saved_citations.append(c_obj)

        await db.commit()

        # Record Usage
        in_tokens = max(1, (len(payload.message) + sum(len(c.text) for c in final_chunks)) // 4)
        out_tokens = max(1, len(full_response) // 4)
        await usage_service.record_usage(
            db=db,
            user_id=current_user.id,
            organization_id=org.id,
            model=llm_service.provider,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            latency_ms=total_duration_ms
        )

        return {
            "conversation_id": conversation.id,
            "message": full_response,
            "citations": citations_data,
            "latency_ms": round(total_duration_ms, 2)
        }
