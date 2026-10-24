"""Document and Ingestion schemas."""
import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    filename: str
    file_type: str
    file_size: int
    status: str
    error_message: Optional[str] = ""
    organization_id: str
    workspace_id: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


class DocumentDetailResponse(DocumentResponse):
    chunk_count: int = 0
    versions: List[dict] = []


class IngestionStatusResponse(BaseModel):
    document_id: str
    status: str
    current_step: str
    processed_chunks: int
    total_chunks: int
    error_message: Optional[str] = None
