"""
Phase 5 — Versioned prompt templates for AI legal document analysis.

Prompts are centralised here so they can be updated independently of
business logic.  The ``PROMPT_VERSION`` constant must be incremented
whenever a prompt changes materially (adds/removes fields, changes
safety instructions, etc.).

Import:
    from app.ai.prompts import (
        PROMPT_VERSION,
        build_document_summary_prompt,
        build_clause_explanation_prompt,
        SYSTEM_INSTRUCTION,
    )
"""

from app.ai.prompts.templates import (
    PROMPT_VERSION,
    SYSTEM_INSTRUCTION,
    build_document_summary_prompt,
    build_clause_explanation_prompt,
)

__all__ = [
    "PROMPT_VERSION",
    "SYSTEM_INSTRUCTION",
    "build_document_summary_prompt",
    "build_clause_explanation_prompt",
]
