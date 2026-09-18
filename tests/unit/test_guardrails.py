"""Unit tests for deterministic guardrail validator."""

import pytest
from app.guardrails.validator import (
    GuardrailValidationError,
    validate_directives_guardrails,
    validate_hours,
)
from app.schemas.interpretation import DirectiveInterpretation, DirectiveType


def test_validate_hours_logic():
    assert validate_hours([1, 2, 3], "test") == [1, 2, 3]

    with pytest.raises(GuardrailValidationError):
        validate_hours([], "test")

    with pytest.raises(GuardrailValidationError):
        validate_hours([3, 2, 1], "test")  # Not ascending

    with pytest.raises(GuardrailValidationError):
        validate_hours([1, 1, 2], "test")  # Duplicate

    with pytest.raises(GuardrailValidationError):
        validate_hours([24], "test")  # Out of range 0-23


def test_guardrails_order_and_count():
    notes = ["Note 1", "Note 2"]
    valid_interps = [
        DirectiveInterpretation(
            note_index=0,
            applies=True,
            directive_type=DirectiveType.NO_CHARGE_WINDOW,
            structured_adjustment={"hours": [1, 2]},
            explanation="Valid",
        ),
        DirectiveInterpretation(
            note_index=1,
            applies=False,
            directive_type=DirectiveType.NO_OP,
            structured_adjustment=None,
            explanation="No op",
        ),
    ]
    # Passes without exception
    validate_directives_guardrails(valid_interps, notes, battery_capacity_kwh=200.0)

    # Missing note 1 (length mismatch)
    with pytest.raises(GuardrailValidationError):
        validate_directives_guardrails(valid_interps[:1], notes, battery_capacity_kwh=200.0)

    # Out of order indices
    bad_order = [valid_interps[1], valid_interps[0]]
    bad_order[0].note_index = 1
    bad_order[1].note_index = 0
    with pytest.raises(GuardrailValidationError):
        validate_directives_guardrails(bad_order, notes, battery_capacity_kwh=200.0)


def test_guardrails_factor_and_reserve_bounds():
    notes = ["Note 1"]

    # Factor > 1.0
    bad_factor = [
        DirectiveInterpretation(
            note_index=0,
            applies=True,
            directive_type=DirectiveType.SOLAR_REDUCTION,
            structured_adjustment={"hours": [12, 13], "factor": 1.5},
            explanation="Invalid",
        )
    ]
    with pytest.raises(GuardrailValidationError):
        validate_directives_guardrails(bad_factor, notes, battery_capacity_kwh=200.0)

    # Reserve > battery capacity
    bad_reserve = [
        DirectiveInterpretation(
            note_index=0,
            applies=True,
            directive_type=DirectiveType.MINIMUM_BATTERY_RESERVE,
            structured_adjustment={"hours": [18, 19], "minimum_energy_kwh": 300.0},
            explanation="Invalid",
        )
    ]
    with pytest.raises(GuardrailValidationError):
        validate_directives_guardrails(bad_reserve, notes, battery_capacity_kwh=200.0)
