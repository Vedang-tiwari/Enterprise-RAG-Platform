"""Usage analytics and tracking API router."""
from typing import Dict, List, Tuple
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.api.deps import get_tenant_context
from backend.app.db.session import get_db
from backend.app.models.organization import Organization, Membership
from backend.app.models.usage import UsageEvent
from backend.app.schemas.usage import UsageEventResponse, UsageSummaryResponse

router = APIRouter(prefix="/usage", tags=["Usage"])


@router.get("", response_model=UsageSummaryResponse)
async def get_usage_summary(
    tenant: Tuple[Organization, Membership] = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve usage analytics, token consumption, and cost estimates for active organization."""
    org, _ = tenant

    # Aggregate totals
    agg_stmt = (
        select(
            func.count(UsageEvent.id),
            func.coalesce(func.sum(UsageEvent.input_tokens), 0),
            func.coalesce(func.sum(UsageEvent.output_tokens), 0),
            func.coalesce(func.sum(UsageEvent.estimated_cost), 0.0),
            func.coalesce(func.avg(UsageEvent.latency_ms), 0.0)
        )
        .where(UsageEvent.organization_id == org.id)
    )
    agg_res = await db.execute(agg_stmt)
    count, total_in, total_out, total_cost, avg_lat = agg_res.one()

    # Model Breakdown
    model_stmt = (
        select(UsageEvent.model, func.count(UsageEvent.id))
        .where(UsageEvent.organization_id == org.id)
        .group_by(UsageEvent.model)
    )
    model_res = await db.execute(model_stmt)
    model_breakdown = {model: m_count for model, m_count in model_res.all()}

    # Recent events
    recent_stmt = (
        select(UsageEvent)
        .where(UsageEvent.organization_id == org.id)
        .order_by(UsageEvent.created_at.desc())
        .limit(20)
    )
    recent_res = await db.execute(recent_stmt)
    recent_events = recent_res.scalars().all()

    return UsageSummaryResponse(
        total_requests=count,
        total_input_tokens=total_in,
        total_output_tokens=total_out,
        total_tokens=total_in + total_out,
        total_estimated_cost_usd=round(total_cost, 4),
        average_latency_ms=round(avg_lat, 2),
        model_breakdown=model_breakdown,
        recent_events=[
            UsageEventResponse(
                id=ev.id,
                model=ev.model,
                input_tokens=ev.input_tokens,
                output_tokens=ev.output_tokens,
                latency_ms=round(ev.latency_ms, 2),
                estimated_cost=round(ev.estimated_cost, 6),
                created_at=ev.created_at
            )
            for ev in recent_events
        ]
    )
