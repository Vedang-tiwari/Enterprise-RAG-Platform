"""Usage and Analytics schemas."""
import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict


class UsageEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    estimated_cost: float
    created_at: datetime.datetime


class UsageSummaryResponse(BaseModel):
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_estimated_cost_usd: float
    average_latency_ms: float
    model_breakdown: Dict[str, int] = {}
    recent_events: List[UsageEventResponse] = []


class AdminMetricsResponse(BaseModel):
    users_count: int
    organizations_count: int
    workspaces_count: int
    documents_count: int
    ready_documents_count: int
    failed_documents_count: int
    indexed_chunks_count: int
    total_questions_asked: int
    telemetry: Dict[str, object] = {}
