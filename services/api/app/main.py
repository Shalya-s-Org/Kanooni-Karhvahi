from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import logger, setup_logging
from app.api.routes import api_v1_router
from app.schemas.base import ApiResponse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application startup and shutdown lifecycle management.
    """
    setup_logging()
    logger.info("Starting %s in %s mode (v%s)", settings.APP_NAME, settings.APP_ENV, settings.VERSION)
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    description="Multilingual Legal Document Companion API for India",
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Global unhandled exception handler enforcing standard ApiResponse envelope.
    """
    logger.error("Unhandled exception processing %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    envelope = ApiResponse.fail(
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected error occurred while processing your request.",
        retryable=True,
        details={"path": request.url.path} if settings.DEBUG else None
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=envelope.model_dump()
    )


# Register versioned API router
app.include_router(api_v1_router)


@app.get("/", tags=["Root"])
async def root() -> ApiResponse[dict]:
    """
    Root endpoint verifying service identity and non-lawyer disclaimer.
    """
    return ApiResponse.ok({
        "app": settings.APP_NAME,
        "tagline": "A Multilingual Legal-Document Companion for India",
        "version": settings.VERSION,
        "disclaimer": "Kanooni Karhvahi is an AI legal document companion and not a substitute for professional legal counsel.",
        "health_check": "/api/v1/health",
        "docs": "/docs"
    })
