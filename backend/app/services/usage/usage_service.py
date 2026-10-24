"""Usage Tracking and Cost Estimation Service."""
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.config import settings
from backend.app.core.logging import metrics
from backend.app.models.usage import UsageEvent


class UsageService:
    # Model pricing per 1M tokens
    RATES = {
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4o": {"input": 5.00, "output": 15.00},
        "mock": {"input": 0.05, "output": 0.15},
    }

    @classmethod
    def estimate_cost(cls, model: str, input_tokens: int, output_tokens: int) -> float:
        rate = cls.RATES.get(model, cls.RATES["mock"])
        cost = (input_tokens / 1_000_000 * rate["input"]) + (output_tokens / 1_000_000 * rate["output"])
        return round(cost, 6)

    @classmethod
    async def record_usage(
        cls,
        db: AsyncSession,
        user_id: str,
        organization_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float
    ) -> UsageEvent:
        cost = cls.estimate_cost(model, input_tokens, output_tokens)

        # Record to in-memory telemetry
        metrics.record_tokens(input_tokens, output_tokens)
        metrics.record_request(latency_ms)

        # Persist event to DB
        event = UsageEvent(
            user_id=user_id,
            organization_id=organization_id,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            estimated_cost=cost
        )
        db.add(event)
        await db.commit()
        await db.refresh(event)
        return event


usage_service = UsageService()
