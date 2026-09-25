"""
Backward-compatibility shim.

The canonical embedding factory lives in app.rag.embeddings.factory.
"""
from app.rag.embeddings.factory import get_embedding_provider  # noqa: F401

__all__ = ["get_embedding_provider"]
