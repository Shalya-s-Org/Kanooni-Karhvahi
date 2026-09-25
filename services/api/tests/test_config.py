from app.core.config import Settings


def test_settings_defaults():
    """
    Verifies that settings load with production-safe defaults.
    """
    settings = Settings(
        DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/test",
        REDIS_URL="redis://localhost:6379/0",
    )
    assert settings.APP_NAME == "Kanooni Karhvahi"
    assert settings.DOCUMENT_TTL_HOURS == 24
    assert settings.MAX_FILE_SIZE_MB == 25
    assert settings.LLM_PROVIDER in ["gemini", "mock", "openai", "anthropic"]
