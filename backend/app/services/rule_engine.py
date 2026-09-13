"""
Rule-Based Strategy Engine

Deterministically selects the best data cleaning strategy for each detected issue
using strict rules based on profiler statistics. No LLM calls needed.

Rules:
- MISSING + String/Categorical → IMPUTE_MODE
- MISSING + Numeric + Outliers  → IMPUTE_MEDIAN  
- MISSING + Numeric + Normal    → IMPUTE_MEAN
- SKEWED_OUTLIERS               → WINSORIZE
- WHITESPACE_PADDING            → TRIM_WHITESPACE
- EXACT_DUPLICATES              → DROP_ROWS_EXACT_DUPLICATE
- POTENTIAL_ID_OR_TEXT           → KEEP (IDs should not be modified)
- CONSTANT_VALUE                → FLAG
"""

from typing import Dict, Any, List, Optional
from app.models.ir import TransformationIR, AllowedOperation, Scope, Constraints


def _build_ir(
    issue_id: str,
    target_column: str,
    operation: str,
    rationale: str,
    risk_level: str = "LOW",
    confidence: str = "HIGH",
    parameters: Optional[Dict[str, Any]] = None,
    scope: Optional[Dict[str, Any]] = None,
    preserve_row_count: bool = True,
) -> TransformationIR:
    return TransformationIR(
        issue_id=issue_id,
        target_column=target_column,
        operation=AllowedOperation(operation),
        rationale=rationale,
        risk_level=risk_level,
        agent_confidence=confidence,
        parameters=parameters or {},
        scope=Scope(**(scope or {})),
        constraints=Constraints(preserve_row_count=preserve_row_count),
    )


class RuleBasedStrategyEngine:
    """
    Picks the optimal cleaning strategy using deterministic rules.
    Instant, free, and 100% reliable — no LLM needed.
    """

    @staticmethod
    def resolve(
        issue_id: str,
        issue_column: str,
        issue_type: str,
        issue_evidence: Dict[str, Any],
        profiler_output: Dict[str, Any],
    ) -> List[TransformationIR]:
        """Returns a list of candidate IRs for the given issue, ranked best-first."""

        dtype = issue_evidence.get("dtype", "Unknown")
        is_numeric = dtype in ("Int64", "Float64", "Int32", "Float32")
        is_string = dtype in ("String", "Utf8", "Unknown")
        has_outliers = issue_evidence.get("has_outliers", False)
        null_pct = issue_evidence.get("null_pct", 0)

        # ── MISSING VALUES ─────────────────────────────────────────────
        if issue_type in ("MISSING_LOW", "MISSING_HIGH"):
            if is_string:
                return [
                    _build_ir(
                        issue_id, issue_column, "IMPUTE_MODE",
                        f"Column '{issue_column}' is categorical/string (dtype={dtype}) with {null_pct}% missing. "
                        f"Filling with the most frequent value (mode) preserves the distribution.",
                    ),
                    _build_ir(
                        issue_id, issue_column, "IMPUTE_CONSTANT",
                        f"Fallback: fill missing strings in '{issue_column}' with 'UNKNOWN' placeholder.",
                        risk_level="LOW", confidence="MEDIUM",
                        parameters={"value": "UNKNOWN"},
                    ),
                ]
            elif is_numeric and has_outliers:
                return [
                    _build_ir(
                        issue_id, issue_column, "IMPUTE_MEDIAN",
                        f"Column '{issue_column}' is numeric with outliers detected. "
                        f"Median imputation is robust to skewed distributions.",
                    ),
                ]
            elif is_numeric:
                return [
                    _build_ir(
                        issue_id, issue_column, "IMPUTE_MEAN",
                        f"Column '{issue_column}' is numeric without significant outliers. "
                        f"Mean imputation is appropriate for normally distributed data.",
                    ),
                ]
            # Fallback for unknown dtype
            return [
                _build_ir(
                    issue_id, issue_column, "IMPUTE_CONSTANT",
                    f"Column '{issue_column}' has unknown dtype. Filling with 'UNKNOWN' as safe fallback.",
                    parameters={"value": "UNKNOWN"},
                ),
            ]

        # ── OUTLIERS ───────────────────────────────────────────────────
        if issue_type == "SKEWED_OUTLIERS":
            return [
                _build_ir(
                    issue_id, issue_column, "WINSORIZE",
                    f"Column '{issue_column}' has skewed outliers. "
                    f"Winsorizing caps extreme values at the 5th/95th percentiles without dropping rows.",
                    risk_level="MEDIUM",
                ),
            ]

        # ── WHITESPACE ─────────────────────────────────────────────────
        if issue_type == "WHITESPACE_PADDING":
            return [
                _build_ir(
                    issue_id, issue_column, "TRIM_WHITESPACE",
                    f"Column '{issue_column}' has leading/trailing whitespace. Trimming for consistency.",
                ),
            ]

        # ── EXACT DUPLICATES ───────────────────────────────────────────
        if issue_type == "EXACT_DUPLICATES":
            dup_count = issue_evidence.get("duplicate_count", 0)
            return [
                _build_ir(
                    issue_id, issue_column, "DROP_ROWS_EXACT_DUPLICATE",
                    f"Dataset has {dup_count} exact duplicate rows. Removing to ensure data integrity.",
                    preserve_row_count=False,
                ),
            ]

        # ── CONSTANT VALUE ─────────────────────────────────────────────
        if issue_type == "CONSTANT_VALUE":
            return [
                _build_ir(
                    issue_id, issue_column, "FLAG",
                    f"Column '{issue_column}' contains a single constant value. Flagging for review.",
                ),
            ]

        # ── TYPE MISMATCH ──────────────────────────────────────────────
        if issue_type == "TYPE_MISMATCH":
            inferred_type = issue_evidence.get("inferred_type", "Float64")
            castability = issue_evidence.get("castability_pct", 0)
            return [
                _build_ir(
                    issue_id, issue_column, "CAST_TYPE",
                    f"Column '{issue_column}' is a string but {castability}% of values look like {inferred_type}. Casting to appropriate type.",
                    risk_level="MEDIUM",
                    parameters={"target_type": inferred_type},
                ),
            ]

        # ── INCONSISTENT CASING ────────────────────────────────────────
        if issue_type == "INCONSISTENT_CASING":
            return [
                _build_ir(
                    issue_id, issue_column, "TEXT_STANDARDIZE",
                    f"Column '{issue_column}' contains inconsistent casing and padding. Converting to Title Case and trimming whitespace.",
                    risk_level="LOW"
                ),
            ]
            
        # ── INVALID LOGICAL VALUE ──────────────────────────────────────
        if issue_type == "INVALID_LOGICAL_VALUE":
            return [
                _build_ir(
                    issue_id, issue_column, "NULLIFY_NEGATIVE",
                    f"Column '{issue_column}' contains negative values which is logically invalid for this metric. Replacing with null.",
                    risk_level="MEDIUM"
                ),
            ]

        # ── POTENTIAL ID / HIGH-CARDINALITY TEXT ───────────────────────
        if issue_type in ("POTENTIAL_ID_OR_TEXT", "SINGLE_DOMINANT_CATEGORY"):
            return [
                _build_ir(
                    issue_id, issue_column, "KEEP",
                    f"Column '{issue_column}' appears to be an ID or high-cardinality text field. "
                    f"No transformation needed.",
                ),
            ]

        # ── DEFAULT FALLBACK ───────────────────────────────────────────
        return [
            _build_ir(
                issue_id, issue_column, "KEEP",
                f"No matching rule for issue type '{issue_type}' on column '{issue_column}'. Keeping original.",
            ),
        ]
