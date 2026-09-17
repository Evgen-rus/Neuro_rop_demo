"""Top-level incremental PATCH merge for deal analysis.

The model returns only changed top-level blocks. Backend replaces those
blocks wholesale on a deepcopy of the trusted FULL analysis. Nested fields
are never deep-merged, so a block cannot be left internally inconsistent.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from openai_api.config import COMMUNICATION_QUALITY_AUDIT_ENABLED
from openai_api.llm.validation import (
    AnalysisValidationError,
    DEAL_REQUIRED_FIELDS,
    normalize_analysis_for_validation,
    validate_deal_analysis,
)


OUTPUT_KIND_FULL = "full_analysis"
OUTPUT_KIND_PATCH = "incremental_patch"
OUTPUT_KIND_PATCH_NO_CHANGE = "incremental_patch_no_change"
OUTPUT_KIND_PATCH_FALLBACK_FULL = "incremental_patch_fallback_full"

IMMUTABLE_TOP_LEVEL_FIELDS = frozenset({"deal_id"})
LIST_TOP_LEVEL_BLOCKS = frozenset({"what_changed"})
OPTIONAL_PATCHABLE_BLOCKS = frozenset({"recommendation_feedback"})
PATCH_OBJECT_KEYS = frozenset({"no_change", "updates"})


class IncrementalPatchError(ValueError):
    """PATCH JSON cannot be applied; caller must run FULL fallback."""

    def __init__(self, message: str, *, reason: str = "incremental_patch_invalid") -> None:
        super().__init__(message)
        self.reason = reason


def patchable_top_level_blocks() -> frozenset[str]:
    """Allowed `updates` keys from the current FULL schema, never identity fields."""
    blocks = set(DEAL_REQUIRED_FIELDS) - IMMUTABLE_TOP_LEVEL_FIELDS
    blocks.update(OPTIONAL_PATCHABLE_BLOCKS)
    if COMMUNICATION_QUALITY_AUDIT_ENABLED:
        blocks.add("communication_quality_audit")
    return frozenset(blocks)


def expected_update_type(key: str) -> type:
    return list if key in LIST_TOP_LEVEL_BLOCKS else dict


def validate_incremental_analysis_patch(patch: Any) -> None:
    if not isinstance(patch, dict):
        raise IncrementalPatchError("PATCH must be a JSON object")
    extra_keys = set(patch) - PATCH_OBJECT_KEYS
    if extra_keys:
        raise IncrementalPatchError(
            "PATCH has unknown top-level keys: " + ", ".join(sorted(extra_keys))
        )
    missing = PATCH_OBJECT_KEYS - set(patch)
    if missing:
        raise IncrementalPatchError(
            "PATCH is missing required keys: " + ", ".join(sorted(missing))
        )
    no_change = patch.get("no_change")
    if not isinstance(no_change, bool):
        raise IncrementalPatchError("PATCH no_change must be a boolean")
    updates = patch.get("updates")
    if not isinstance(updates, dict):
        raise IncrementalPatchError("PATCH updates must be an object")
    if no_change and updates:
        raise IncrementalPatchError("PATCH no_change=true requires empty updates")
    if not no_change and not updates:
        raise IncrementalPatchError("PATCH no_change=false requires non-empty updates")
    allowed = patchable_top_level_blocks()
    for key, value in updates.items():
        if key in IMMUTABLE_TOP_LEVEL_FIELDS or key not in allowed:
            raise IncrementalPatchError(f"PATCH updates contain a forbidden block: {key}")
        expected = expected_update_type(key)
        if not isinstance(value, expected):
            raise IncrementalPatchError(
                f"PATCH updates.{key} must be a {expected.__name__}, got {type(value).__name__}"
            )


def merge_incremental_analysis_patch(
    previous_analysis: Any,
    patch: Any,
) -> dict[str, Any]:
    """Replace listed top-level blocks on a deepcopy of the trusted analysis."""
    validate_incremental_analysis_patch(patch)
    if not isinstance(previous_analysis, dict):
        raise IncrementalPatchError("trusted baseline analysis must be an object")
    merged = deepcopy(previous_analysis)
    for key, value in patch["updates"].items():
        merged[key] = deepcopy(value)
    if merged.get("deal_id") != previous_analysis.get("deal_id"):
        raise IncrementalPatchError("deal_id must stay immutable")
    return merged


def apply_incremental_analysis_patch(
    previous_analysis: Any,
    patch: Any,
) -> tuple[dict[str, Any], str]:
    """Merge PATCH onto trusted FULL analysis and run the existing FULL validator."""
    merged = merge_incremental_analysis_patch(previous_analysis, patch)
    if patch.get("no_change") is True:
        return merged, OUTPUT_KIND_PATCH_NO_CHANGE
    try:
        normalize_analysis_for_validation(merged)
        validate_deal_analysis(merged)
    except (AnalysisValidationError, TypeError, ValueError) as error:
        raise IncrementalPatchError(
            f"merged analysis failed FULL validation: {error}"
        ) from error
    return merged, OUTPUT_KIND_PATCH
