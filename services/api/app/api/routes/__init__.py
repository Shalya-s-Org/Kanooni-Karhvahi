from fastapi import APIRouter
from app.api.routes.health import router as health_router
from app.api.routes.documents import router as documents_router
from app.api.routes.analysis import router as analysis_router
from app.api.routes.chat import router as chat_router
from app.api.routes.reports import router as reports_router
from app.api.routes.sources import router as sources_router
from app.api.routes.translation import router as translation_router
from app.api.routes.translation import doc_translation_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(health_router)
api_v1_router.include_router(documents_router)
api_v1_router.include_router(analysis_router)
api_v1_router.include_router(chat_router)
api_v1_router.include_router(reports_router)
api_v1_router.include_router(sources_router)
# Phase 7: Multilingual translation
api_v1_router.include_router(translation_router)
api_v1_router.include_router(doc_translation_router)

__all__ = ["api_v1_router"]
