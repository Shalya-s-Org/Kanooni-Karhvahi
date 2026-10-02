"""
Phase 5 prompt templates — version: phase5-v1

All prompts share a common system instruction that enforces:
  1. Evidence-only responses (no invented facts)
  2. Conservative language (not legal advice)
  3. Explicit uncertainty disclosure
  4. JSON-only structured output

Prompt versioning
-----------------
When any prompt changes materially:
  1. Bump PROMPT_VERSION.
  2. Existing analyses stored with the old version remain valid under
     their old schema — do not retroactively invalidate them.
  3. New generation requests will use the new version and will persist
     the updated PROMPT_VERSION in the analysis record.
"""

from __future__ import annotations

from typing import Any, Dict, List

PROMPT_VERSION = "phase5-v1"

# ---------------------------------------------------------------------------
# Shared system instruction
# ---------------------------------------------------------------------------
# This instruction is prepended to every LLM call.
# It enforces the safety boundary required for a legal-information product.

SYSTEM_INSTRUCTION = """You are Kanooni Karhvahi, an AI legal document companion for India.

CRITICAL RULES — YOU MUST FOLLOW THESE WITHOUT EXCEPTION:

1. SOURCE OF TRUTH: The uploaded document and the evidence provided below are
   the ONLY sources of information. You MUST NOT invent, infer, or fabricate
   any facts, citations, names, dates, amounts, or legal provisions that are
   not explicitly present in the supplied evidence.

2. NOT A LAWYER: You are NOT providing legal advice. You are explaining what
   the document says in plain language. You MUST NOT:
   - Predict whether someone will win or lose in court
   - Declare something "illegal", "void", "invalid", "fraudulent" without
     direct textual support in the evidence
   - Invent legal rights, obligations, or remedies
   - Claim certainty when the evidence is incomplete or ambiguous

3. REQUIRED LANGUAGE: Use phrases such as:
   - "According to the uploaded document..."
   - "The document states..."
   - "This clause appears to..."
   - "This may be important because..."
   - "The document does not provide enough information to determine..."
   - "Consider verifying this with a qualified lawyer or official source."

4. FORBIDDEN LANGUAGE: Do NOT use:
   - "You should definitely..."
   - "You will win..." / "You will lose..."
   - "This guarantees..." / "This is illegal..."
   - "You have a guaranteed right..."
   - "The court will..."

5. EVIDENCE REFERENCES: Every factual claim in your response MUST cite the
   evidence_id of the evidence item it is based on. Do not make claims
   without evidence_refs.

6. UNCERTAINTY: If the evidence is incomplete, say so explicitly in
   uncertainty_notes. Do not fill gaps with assumptions.

7. OUTPUT FORMAT: Respond with ONLY valid JSON conforming to the provided
   schema. No prose, no markdown fences, no explanations outside the JSON.

8. PRIVACY: Do not repeat or log API keys, credentials, or system internals."""


# ---------------------------------------------------------------------------
# Document summary prompt builder
# ---------------------------------------------------------------------------

def build_document_summary_prompt(
    document_filename: str,
    document_type: str,
    evidence_items: List[Dict[str, Any]],
    total_pages: int,
    is_evidence_partial: bool = False,
) -> str:
    """
    Build the user-turn prompt for document summary generation.

    Args:
        document_filename:  Original filename for context.
        document_type:      Classification result (e.g. "CONTRACT").
        evidence_items:     List of evidence dicts from EvidencePackBuilder.
        total_pages:        Total page count of the document.
        is_evidence_partial: True if evidence was truncated due to context limits.

    Returns:
        Formatted prompt string.
    """
    evidence_block = _format_evidence_block(evidence_items)
    partial_note = (
        "\n⚠ NOTE: The evidence below is PARTIAL due to document size. "
        "You must note this in uncertainty_notes."
        if is_evidence_partial
        else ""
    )

    return f"""DOCUMENT ANALYSIS REQUEST

Filename: {document_filename}
Detected document type: {document_type}
Total pages: {total_pages}{partial_note}

EVIDENCE PACK
=============
The following evidence items were extracted from the document.
Each item has a unique evidence_id that you MUST cite in your response.
{evidence_block}

TASK
====
Generate a structured JSON summary of this document using the provided schema.

Requirements:
- Write a 2–4 sentence summary of the document's main purpose and effect.
- List the most important key points (with evidence_refs for each).
- Extract dates, amounts, and parties that are explicitly mentioned.
- List obligations that are clearly stated in the document.
- Generate check_signals for anything that deserves human attention
  (missing information, ambiguous clauses, unusual deadlines, etc.).
- In uncertainty_notes, state anything you could not determine from the evidence.
- Do NOT invent facts not present in the evidence.
- Do NOT provide legal advice or predict outcomes.
- Every key_point must cite at least one evidence_id.
"""


# ---------------------------------------------------------------------------
# Clause explanation prompt builder
# ---------------------------------------------------------------------------

def build_clause_explanation_prompt(
    clause_number: str | None,
    clause_title: str | None,
    clause_text: str,
    page_number: int,
    evidence_items: List[Dict[str, Any]],
    document_type: str = "UNKNOWN",
) -> str:
    """
    Build the user-turn prompt for clause explanation generation.

    Args:
        clause_number:  Clause numbering (e.g. "3", "7.1").
        clause_title:   Clause title/heading if available.
        clause_text:    Original verbatim clause text.
        page_number:    Source page number.
        evidence_items: Supporting evidence from EvidencePackBuilder.
        document_type:  Document classification label.

    Returns:
        Formatted prompt string.
    """
    clause_id_str = f"Clause {clause_number}" if clause_number else "Clause"
    title_str = f' — "{clause_title}"' if clause_title else ""
    evidence_block = _format_evidence_block(evidence_items)

    return f"""CLAUSE EXPLANATION REQUEST

Document type: {document_type}
{clause_id_str}{title_str} (Page {page_number})

ORIGINAL CLAUSE TEXT (verbatim — do NOT modify or paraphrase this)
===================================================================
{clause_text}

SUPPORTING EVIDENCE
===================
{evidence_block}

TASK
====
Explain this clause in plain language using the schema provided.

Requirements:
- plain_meaning: Explain what this clause says in simple language a
  non-lawyer can understand. Start with "According to the document..." or
  "This clause states...".
- why_it_matters: Explain why this clause may be significant (deadlines,
  amounts, obligations, rights). Use "This may be important because...".
- important_terms: Identify any legal/technical terms and explain them simply.
- obligations: List any explicit obligations imposed by this clause.
- dates and amounts: Extract only those explicitly stated in the clause.
- check_signals: Note anything ambiguous, missing, or unusual.
- uncertainty_notes: State clearly what you could not determine.
- evidence_refs: Include the evidence_ids you relied on.
- Do NOT provide legal advice or predict legal outcomes.
- Do NOT invent obligations, rights, or facts not present in the clause text.
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_evidence_block(evidence_items: List[Dict[str, Any]]) -> str:
    """Format evidence items into a numbered, readable block for the prompt."""
    if not evidence_items:
        return "(No evidence items available)"

    lines: List[str] = []
    for item in evidence_items:
        eid = item.get("evidence_id", "unknown")
        source = item.get("source_type", "document")
        page = item.get("page_number", "?")
        clause_num = item.get("clause_number", "")
        text = item.get("source_text", "").strip()

        header = f"[{eid}] Source: {source} | Page: {page}"
        if clause_num:
            header += f" | Clause: {clause_num}"
        lines.append(header)
        # Truncate very long evidence snippets to keep prompt manageable.
        if len(text) > 800:
            text = text[:800] + "... [truncated]"
        lines.append(f"  Text: {text}")
        lines.append("")

    return "\n".join(lines)
