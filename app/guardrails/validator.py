"""Deterministic guardrails for untrusted LLM directive interpretations."""

import math
from typing import Any
from app.schemas.interpretation import DirectiveInterpretation, DirectiveType


class GuardrailValidationError(ValueError):
    """Raised when an LLM directive interpretation fails deterministic guardrails."""
    pass


def validate_hours(hours: Any, directive_type: str) -> list[int]:
    """Validates that hours is a list of unique integers in 0..23 in strictly ascending order."""
    if not isinstance(hours, list):
        raise GuardrailValidationError(f"{directive_type}: 'hours' must be a list, got {type(hours).__name__}")
    if not hours:
        raise GuardrailValidationError(f"{directive_type}: 'hours' list cannot be empty")

    for h in hours:
        if not isinstance(h, int) or isinstance(h, bool):
            raise GuardrailValidationError(f"{directive_type}: hour '{h}' must be an integer")
        if h < 0 or h > 23:
            raise GuardrailValidationError(f"{directive_type}: hour '{h}' out of range [0, 23]")

    if len(hours) != len(set(hours)):
        raise GuardrailValidationError(f"{directive_type}: 'hours' list contains duplicate values: {hours}")

    if hours != sorted(hours):
        raise GuardrailValidationError(f"{directive_type}: 'hours' must be in ascending order, got {hours}")

    return hours


def validate_directives_guardrails(
    interpretations: list[DirectiveInterpretation],
    operator_notes: list[str],
    battery_capacity_kwh: float,
) -> None:
    """Deterministically validates the LLM output against all challenge guardrails."""
    num_notes = len(operator_notes)

    # 1. Note count and order mapping
    if len(interpretations) != num_notes:
        raise GuardrailValidationError(
            f"Expected {num_notes} directive interpretations, got {len(interpretations)}"
        )

    for expected_idx, interp in enumerate(interpretations):
        if interp.note_index != expected_idx:
            raise GuardrailValidationError(
                f"Interpretation at position {expected_idx} has note_index={interp.note_index}; "
                f"must be strictly ordered 0 through {num_notes - 1}"
            )

        if not isinstance(interp.explanation, str) or not interp.explanation.strip():
            raise GuardrailValidationError(f"Note {interp.note_index}: explanation must be a non-empty string")

        dtype = interp.directive_type

        # 2. no_op semantics
        if dtype == DirectiveType.NO_OP:
            if interp.applies is not False:
                raise GuardrailValidationError(f"Note {interp.note_index}: no_op must have applies=false")
            if interp.structured_adjustment is not None:
                raise GuardrailValidationError(
                    f"Note {interp.note_index}: no_op must have structured_adjustment=null"
                )
            continue

        # 3. Applicable directives semantics
        if interp.applies is not True:
            raise GuardrailValidationError(
                f"Note {interp.note_index}: directive '{dtype.value}' must have applies=true"
            )

        adj = interp.structured_adjustment
        if not isinstance(adj, dict):
            raise GuardrailValidationError(
                f"Note {interp.note_index}: directive '{dtype.value}' must have a dictionary structured_adjustment"
            )

        if "hours" not in adj:
            raise GuardrailValidationError(
                f"Note {interp.note_index}: directive '{dtype.value}' adjustment missing required 'hours' key"
            )

        validate_hours(adj["hours"], dtype.value)

        # 4. Directive specific field checks
        if dtype == DirectiveType.SOLAR_REDUCTION:
            if "factor" not in adj:
                raise GuardrailValidationError(f"Note {interp.note_index}: solar_reduction requires 'factor'")
            factor = adj["factor"]
            if not isinstance(factor, (int, float)) or not math.isfinite(factor):
                raise GuardrailValidationError(f"Note {interp.note_index}: factor must be a finite number")
            if factor < 0.0 or factor > 1.0:
                raise GuardrailValidationError(
                    f"Note {interp.note_index}: factor must be between 0.0 and 1.0, got {factor}"
                )

        elif dtype == DirectiveType.MINIMUM_BATTERY_RESERVE:
            if "minimum_energy_kwh" not in adj:
                raise GuardrailValidationError(
                    f"Note {interp.note_index}: minimum_battery_reserve requires 'minimum_energy_kwh'"
                )
            reserve = adj["minimum_energy_kwh"]
            if not isinstance(reserve, (int, float)) or not math.isfinite(reserve):
                raise GuardrailValidationError(
                    f"Note {interp.note_index}: minimum_energy_kwh must be a finite number"
                )
            if reserve < 0.0:
                raise GuardrailValidationError(
                    f"Note {interp.note_index}: minimum_energy_kwh cannot be negative, got {reserve}"
                )
            if reserve > battery_capacity_kwh:
                raise GuardrailValidationError(
                    f"Note {interp.note_index}: minimum_energy_kwh ({reserve}) cannot exceed battery capacity ({battery_capacity_kwh})"
                )

        elif dtype == DirectiveType.MAX_GRID_WINDOW:
            if "max_grid_kwh" not in adj:
                raise GuardrailValidationError(f"Note {interp.note_index}: max_grid_window requires 'max_grid_kwh'")
            max_grid = adj["max_grid_kwh"]
            if not isinstance(max_grid, (int, float)) or not math.isfinite(max_grid):
                raise GuardrailValidationError(f"Note {interp.note_index}: max_grid_kwh must be a finite number")
            if max_grid < 0.0:
                raise GuardrailValidationError(
                    f"Note {interp.note_index}: max_grid_kwh cannot be negative, got {max_grid}"
                )

        elif dtype in (DirectiveType.NO_CHARGE_WINDOW, DirectiveType.NO_DISCHARGE_WINDOW):
            extra_keys = set(adj.keys()) - {"hours"}
            if extra_keys:
                raise GuardrailValidationError(
                    f"Note {interp.note_index}: unexpected keys in {dtype.value}: {extra_keys}"
                )
