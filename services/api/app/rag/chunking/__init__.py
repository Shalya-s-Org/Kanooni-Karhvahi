"""
Clause-aware semantic chunking.

Priority order:
  1. Explicit clause boundaries
  2. Page boundaries
  3. Paragraph boundaries
  4. Sentence boundaries
  5. Token/character limit
"""
from app.rag.chunking.chunker import (
    ChunkMetadata,
    DocumentChunker,
    document_chunker,
)

__all__ = [
    "ChunkMetadata",
    "DocumentChunker",
    "document_chunker",
]
