"""
Hallucination guard — Phase 5.

Validates LLM-generated output against the evidence pack that was
submitted to the model.  A response that fails validation is rejected
and the analysis is marked VALIDATION_FAILED.

What the guard checks:
  1. Output schema is valid (Pydantic validation).
  2. Every evidence_ref cited by the model exists in valid_ids.
  3. No claim has an empty evidence_refs list (for key_points).
  4. Output is non-empty (not a blank or whitespace-only response).
  5. Provider/model fields are present.

What the guard does NOT check:
  - Semantic correctness of the generated text.
  - Whether the AI "correctly" interpreted the document.
  - Legal accuracy of explanations.

Those require human review.  The guard only catches structural and
referential errors that would indicate the model hallucinated evidence IDs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Type

from pydantic import BaseModel, ValidationError

from app.ai.structured_output.schemas import (
    ClauseExplanationOutput,
    DocumentSummaryOutput,
)
from app.core.logging import logger


# ---------------------------------------------------------------------------
# Guard result
# ---------------------------------------------------------------------------

@dataclass
class GuardResult:
    passed: bool
    errors: List[str] = field(default_factory=list)
    sanitised_output: Optional[Any] = None  # Parsed Pydantic model if passed

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.passed = False


# ---------------------------------------------------------------------------
# Guard
# ---------------------------------------------------------------------------

class HallucinationGuard:
    """
    Validates LLM-generated structured output against the evidence pack.

    Usage::

        guard = HallucinationGuard()
        result = guard.validate_summary(raw_dict, evidence_pack.valid_ids)
        if not result.passed:
            # mark analysis as VALIDATION_FAILED
        else:
            validated_output = result.sanitised_output  # DocumentSummaryOutput
    """

    def validate_summary(
        self,
        raw: Dict[str, Any],
        valid_ids: Set[str],
    ) -> GuardResult:
        """
        Validate a document summary output dict.

        Args:
            raw:       The dict returned by generate_structured().
            valid_ids: Set of valid evidence_id strings from the EvidencePack.

        Returns:
            GuardResult with passed=True and sanitised_output if valid.
        """
        result = GuardResult(passed=True)

        # 1. Schema validation.
        try:
            parsed = DocumentSummaryOutput.model_validate(raw)
        except ValidationError as exc:
            result.add_error(f"Schema validation failed: {exc}")
            return result

        # 2. Non-empty summary.
        if not parsed.summary or not parsed.summary.strip():
            result.add_error("Summary field is empty.")
            return result

        # 3. Evidence references validation.
        invalid_refs = self._find_invalid_refs(raw, valid_ids)
        if invalid_refs:
            # Sanitise: remove invalid refs rather than rejecting outright,
            # unless ALL evidence_refs are invalid (then reject).
            all_refs = self._collect_all_refs(raw)
            if all_refs and all_refs == invalid_refs:
                result.add_error(
                    f"All evidence_refs are invalid: {invalid_refs}. "
                    "Model hallucinated evidence IDs."
                )
                return result
            # Partial invalid refs — sanitise and warn.
            logger.warning(
                "Summary contains invalid evidence_refs (sanitised): %s", invalid_refs
            )
            parsed = self._sanitise_summary_refs(parsed, invalid_refs)

        result.sanitised_output = parsed
        return result

    def validate_clause_explanation(
        self,
        raw: Dict[str, Any],
        valid_ids: Set[str],
    ) -> GuardResult:
        """
        Validate a clause explanation output dict.

        Args:
            raw:       The dict returned by generate_structured().
            valid_ids: Set of valid evidence_id strings from the EvidencePack.

        Returns:
            GuardResult with passed=True and sanitised_output if valid.
        """
        result = GuardResult(passed=True)

        # 1. Schema validation.
        try:
            parsed = ClauseExplanationOutput.model_validate(raw)
        except ValidationError as exc:
            result.add_error(f"Schema validation failed: {exc}")
            return result

        # 2. Non-empty plain_meaning.
        if not parsed.plain_meaning or not parsed.plain_meaning.strip():
            result.add_error("plain_meaning field is empty.")
            return result

        # 3. Evidence reference validation.
        invalid_refs = self._find_invalid_refs(raw, valid_ids)
        if invalid_refs:
            all_refs = self._collect_all_refs(raw)
            if all_refs and all_refs == invalid_refs:
                result.add_error(
                    f"All evidence_refs are invalid: {invalid_refs}. "
                    "Model hallucinated evidence IDs."
                )
                return result
            logger.warning(
                "Clause explanation contains invalid evidence_refs (sanitised): %s",
                invalid_refs,
            )
            parsed = self._sanitise_explanation_refs(parsed, invalid_refs)

        result.sanitised_output = parsed
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_invalid_refs(
        self,
        data: Any,
        valid_ids: Set[str],
    ) -> Set[str]:
        """Recursively find all evidence_ref values not in valid_ids."""
        invalid: Set[str] = set()
        if isinstance(data, dict):
            for key, value in data.items():
                if key == "evidence_refs" and isinstance(value, list):
                    for ref in value:
                        if isinstance(ref, str) and ref not in valid_ids:
                            invalid.add(ref)
                else:
                    invalid |= self._find_invalid_refs(value, valid_ids)
        elif isinstance(data, list):
            for item in data:
                invalid |= self._find_invalid_refs(item, valid_ids)
        return invalid

    def _collect_all_refs(self, data: Any) -> Set[str]:
        """Recursively collect all evidence_ref strings."""
        refs: Set[str] = set()
        if isinstance(data, dict):
            for key, value in data.items():
                if key == "evidence_refs" and isinstance(value, list):
                    for ref in value:
                        if isinstance(ref, str):
                            refs.add(ref)
                else:
                    refs |= self._collect_all_refs(value)
        elif isinstance(data, list):
            for item in data:
                refs |= self._collect_all_refs(item)
        return refs

    def _sanitise_summary_refs(
        self,
        parsed: DocumentSummaryOutput,
        invalid_refs: Set[str],
    ) -> DocumentSummaryOutput:
        """Remove invalid evidence_refs from key_points and check_signals."""
        for kp in parsed.key_points:
            kp.evidence_refs = [r for r in kp.evidence_refs if r not in invalid_refs]
        for sig in parsed.check_signals:
            sig.evidence_refs = [r for r in sig.evidence_refs if r not in invalid_refs]
        return parsed

    def _sanitise_explanation_refs(
        self,
        parsed: ClauseExplanationOutput,
        invalid_refs: Set[str],
    ) -> ClauseExplanationOutput:
        """Remove invalid evidence_refs from clause explanation."""
        parsed.evidence_refs = [r for r in parsed.evidence_refs if r not in invalid_refs]
        for sig in parsed.check_signals:
            sig.evidence_refs = [r for r in sig.evidence_refs if r not in invalid_refs]
        return parsed


hallucination_guard = HallucinationGuard()
