"""Structured logging and telemetry instrumentation."""
import logging
import sys
import time
from typing import Dict, Any


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger("enterprise_rag")


class PlatformMetrics:
    """Telemetry collector for system metrics, latencies, and token consumption."""
    def __init__(self):
        self.request_count: int = 0
        self.total_errors: int = 0
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.latencies: Dict[str, list] = {
            "retrieval": [],
            "rerank": [],
            "llm": [],
            "total_request": []
        }
        self.ingestion_jobs_completed: int = 0
        self.ingestion_jobs_failed: int = 0

    def record_request(self, duration_ms: float, is_error: bool = False):
        self.request_count += 1
        if is_error:
            self.total_errors += 1
        self.latencies["total_request"].append(duration_ms)
        if len(self.latencies["total_request"]) > 1000:
            self.latencies["total_request"].pop(0)

    def record_rag_latency(self, phase: str, duration_ms: float):
        if phase in self.latencies:
            self.latencies[phase].append(duration_ms)
            if len(self.latencies[phase]) > 500:
                self.latencies[phase].pop(0)

    def record_tokens(self, input_tokens: int, output_tokens: int):
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

    def get_summary(self) -> Dict[str, Any]:
        def avg(lst):
            return round(sum(lst) / len(lst), 2) if lst else 0.0

        return {
            "total_requests": self.request_count,
            "total_errors": self.total_errors,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "estimated_cost_usd": round(
                (self.total_input_tokens * 0.00000015) + (self.total_output_tokens * 0.0000006), 4
            ),
            "average_latency_ms": {
                "total_request": avg(self.latencies["total_request"]),
                "retrieval": avg(self.latencies["retrieval"]),
                "rerank": avg(self.latencies["rerank"]),
                "llm": avg(self.latencies["llm"])
            },
            "ingestion": {
                "completed": self.ingestion_jobs_completed,
                "failed": self.ingestion_jobs_failed
            }
        }


metrics = PlatformMetrics()
