"""Application configuration settings."""
import os
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    APP_ENV: str = "development"
    APP_NAME: str = "Enterprise-RAG-Platform"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # Security
    SECRET_KEY: str = "dev_secret_jwt_key_enterprise_rag_platform_must_be_long_enough"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["*"]

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./enterprise_rag.db"

    # Redis (Optional in local dev, fallback gracefully to in-memory)
    REDIS_URL: Optional[str] = "redis://localhost:6379/0"

    # Qdrant Vector Store
    QDRANT_URL: Optional[str] = "http://localhost:6333"
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_COLLECTION: str = "enterprise_knowledge"

    # RabbitMQ / Celery
    RABBITMQ_URL: Optional[str] = "amqp://guest:guest@localhost:5672/"

    # Storage
    STORAGE_TYPE: str = "local"  # local or s3
    STORAGE_DIR: str = "./storage_data"
    S3_ENDPOINT: Optional[str] = "http://localhost:9000"
    S3_ACCESS_KEY: Optional[str] = "minioadmin"
    S3_SECRET_KEY: Optional[str] = "minioadmin"
    S3_BUCKET: str = "enterprise-documents"

    # LLM Settings
    LLM_PROVIDER: str = "mock"  # mock, openai, anthropic, groq, ollama
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    ANTHROPIC_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # Embeddings
    EMBEDDING_PROVIDER: str = "local"  # local, openai
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 384

    # RAG Tuning Parameters
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 100
    RETRIEVAL_TOP_K: int = 20
    RERANK_TOP_K: int = 5
    SIMILARITY_THRESHOLD: float = 0.35

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 120
    MAX_UPLOAD_SIZE_MB: int = 50


settings = Settings()
