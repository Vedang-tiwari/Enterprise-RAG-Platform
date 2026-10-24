"""Enterprise RAG Platform - Master FastAPI Application."""
import os
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from backend.app.core.config import settings
from backend.app.core.logging import logger, metrics
from backend.app.db.session import init_db
from backend.app.api.auth import router as auth_router
from backend.app.api.organizations import router as orgs_router
from backend.app.api.workspaces import router as workspaces_router
from backend.app.api.documents import router as docs_router
from backend.app.api.chat import router as chat_router
from backend.app.api.conversations import router as conversations_router
from backend.app.api.usage import router as usage_router
from backend.app.api.admin import router as admin_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle handler."""
    logger.info(f"Initializing {settings.APP_NAME} in [{settings.APP_ENV}] mode...")
    # Initialize relational database schemas
    await init_db()
    logger.info("Database schemas initialized.")
    os.makedirs(settings.STORAGE_DIR, exist_ok=True)
    yield
    logger.info("Enterprise RAG Platform shutting down.")


app = FastAPI(
    title=settings.APP_NAME,
    description="Production-Grade Multi-Tenant Enterprise AI Knowledge Platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global telemetry middleware
@app.middleware("http")
async def telemetry_middleware(request: Request, call_next):
    start = time.time()
    try:
        response = await call_next(request)
        duration_ms = (time.time() - start) * 1000
        metrics.record_request(duration_ms, is_error=(response.status_code >= 500))
        response.headers["X-Process-Time-Ms"] = str(round(duration_ms, 2))
        return response
    except Exception as e:
        duration_ms = (time.time() - start) * 1000
        metrics.record_request(duration_ms, is_error=True)
        logger.error(f"Unhandled exception on {request.method} {request.url}: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error."}
        )


# Mount API V1 Routers
api_v1 = settings.API_V1_PREFIX
app.include_router(auth_router, prefix=api_v1)
app.include_router(orgs_router, prefix=api_v1)
app.include_router(workspaces_router, prefix=api_v1)
app.include_router(docs_router, prefix=api_v1)
app.include_router(chat_router, prefix=api_v1)
app.include_router(conversations_router, prefix=api_v1)
app.include_router(usage_router, prefix=api_v1)
app.include_router(admin_router, prefix=api_v1)


@app.get("/metrics", tags=["Observability"])
async def get_metrics():
    """Prometheus-style telemetry metrics."""
    return metrics.get_summary()


# Mount Frontend if built/available
frontend_dist = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "public")
if os.path.exists(frontend_dist):
    app.mount("/static", StaticFiles(directory=frontend_dist), name="static")

    @app.get("/")
    async def serve_index():
        index_file = os.path.join(frontend_dist, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {
            "name": settings.APP_NAME,
            "status": "online",
            "docs": "/docs",
            "metrics": "/metrics"
        }
else:
    @app.get("/")
    async def root():
        return {
            "name": settings.APP_NAME,
            "status": "online",
            "docs": "/docs",
            "metrics": "/metrics"
        }
