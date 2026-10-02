"""
Core application configuration and settings management.
"""

from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central settings object loaded from environment variables and .env file.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # General
    APP_ENV: str = "development"
    APP_NAME: str = "Kanooni Karhvahi"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    VERSION: str = "0.1.0"

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/kanooni_karhvahi"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/kanooni_karhvahi"
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    # Redis & Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # AI / LLM Provider Configuration (Gemini, OpenAI, Groq, Ollama, Mock)
    LLM_PROVIDER: str = "mock"
    LLM_API_KEY: Optional[str] = None
    LLM_MODEL: str = "openai/gpt-oss-20b"
    # Base URL for OpenAI-compatible providers (e.g. Groq, Ollama).
    # Leave unset for standard OpenAI; set to https://api.groq.com/openai/v1 for Groq.
    LLM_BASE_URL: Optional[str] = None
    # Phase 5 aliases for AI configuration
    AI_PROVIDER: Optional[str] = None
    AI_API_KEY: Optional[str] = None
    AI_MODEL: Optional[str] = None
    # Generation parameters
    AI_TEMPERATURE: float = 0.1          # Low temperature → conservative, factual responses
    AI_MAX_OUTPUT_TOKENS: int = 4096     # Sufficient for structured legal summaries
    # Prompt versioning — increment when prompts change materially
    AI_PROMPT_VERSION: str = "phase5-v1"

    # Embeddings Configuration
    EMBEDDING_PROVIDER: str = "mock"
    EMBEDDING_API_KEY: Optional[str] = None
    EMBEDDING_MODEL: str = "text-embedding-004"
    # Vector dimension MUST match the model's output.
    # text-embedding-004 (Gemini): 768
    # text-embedding-3-small (OpenAI): 1536
    # all-MiniLM-L6-v2 (HuggingFace): 384
    EMBEDDING_DIMENSION: int = 768
    # Maximum texts sent to the embedding provider in one batch call.
    EMBEDDING_BATCH_SIZE: int = 32

    # Semantic Chunking Configuration
    # Token limits use whitespace-word counting (conservative approximation).
    CHUNK_SIZE_TOKENS: int = 500
    CHUNK_OVERLAP_TOKENS: int = 75

    # OCR Configuration (Tesseract, EasyOCR, Google Vision, Mock)
    OCR_PROVIDER: str = "mock"

    # Storage Configuration (Local, S3, Mock)
    STORAGE_PROVIDER: str = "local"
    STORAGE_LOCAL_DIR: str = "./uploads"

    # Privacy & Document Governance
    DOCUMENT_TTL_HOURS: int = 24
    MAX_FILE_SIZE_MB: int = 25

    # Security
    SECRET_KEY: str = "default_development_secret_key_change_in_production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440


# Global settings singleton
settings = Settings()
