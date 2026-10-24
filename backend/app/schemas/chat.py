"""Chat, Conversation, and Citation schemas."""
import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    workspace_id: str
    conversation_id: Optional[str] = None
    stream: bool = True
    top_k: int = 5
    enable_rerank: bool = True


class CitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    chunk_id: Optional[str] = None
    document_name: str
    page_number: int
    snippet: str
    relevance_score: float


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    sender_role: str
    content: str
    token_count: int
    created_at: datetime.datetime
    citations: List[CitationResponse] = []


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    workspace_id: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    message_count: int = 0


class ConversationDetailResponse(ConversationResponse):
    messages: List[MessageResponse] = []
