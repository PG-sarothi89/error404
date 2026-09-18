"""Unit tests for request and interpretation schema validation."""

import pytest
from pydantic import ValidationError

from app.schemas.interpretation import DirectiveInterpretation, DirectiveType
from app.schemas.request import BatteryInput, HourInput, OptimizeEnergyRequest


def make_valid_hours():
    return [
        HourInput(hour=h, demand_kwh=100.0, solar_kwh=50.0, tariff_bdt_per_kwh=10.0)
        for h in range(24)
    ]


def make_valid_battery():
    return BatteryInput(
        capacity_kwh=200.0,
        initial_energy_kwh=100.0,
        minimum_energy_kwh=40.0,
        max_charge_kwh_per_hour=50.0,
        max_discharge_kwh_per_hour=50.0,
    )


def test_valid_request():
    req = OptimizeEnergyRequest(
        scenario_id="TEST-01",
        operator_notes=["Note 1", "Note 2"],
        hours=make_valid_hours(),
        battery=make_valid_battery(),
    )
    assert req.scenario_id == "TEST-01"
    assert len(req.hours) == 24


def test_reject_empty_scenario_id():
    with pytest.raises(ValidationError):
        OptimizeEnergyRequest(
            scenario_id="   ",
            operator_notes=["Note 1"],
            hours=make_valid_hours(),
            battery=make_valid_battery(),
        )


def test_reject_notes_bounds():
    with pytest.raises(ValidationError):
        OptimizeEnergyRequest(
            scenario_id="TEST-01",
            operator_notes=[],
            hours=make_valid_hours(),
            battery=make_valid_battery(),
        )
    with pytest.raises(ValidationError):
        OptimizeEnergyRequest(
            scenario_id="TEST-01",
            operator_notes=["1", "2", "3", "4"],
            hours=make_valid_hours(),
            battery=make_valid_battery(),
        )
    with pytest.raises(ValidationError):
        OptimizeEnergyRequest(
            scenario_id="TEST-01",
            operator_notes=[""],
            hours=make_valid_hours(),
            battery=make_valid_battery(),
        )


def test_reject_invalid_hours():
    hours = make_valid_hours()[:-1]  # 23 hours
    with pytest.raises(ValidationError):
        OptimizeEnergyRequest(
            scenario_id="TEST-01",
            operator_notes=["Note 1"],
            hours=hours,
            battery=make_valid_battery(),
        )

    # Duplicate hour
    hours_dup = make_valid_hours()
    hours_dup[1].hour = 0
    with pytest.raises(ValidationError):
        OptimizeEnergyRequest(
            scenario_id="TEST-01",
            operator_notes=["Note 1"],
            hours=hours_dup,
            battery=make_valid_battery(),
        )


def test_reject_negative_and_non_finite():
    with pytest.raises(ValidationError):
        HourInput(hour=0, demand_kwh=-10.0, solar_kwh=0, tariff_bdt_per_kwh=5)
    with pytest.raises(ValidationError):
        HourInput(hour=0, demand_kwh=float("nan"), solar_kwh=0, tariff_bdt_per_kwh=5)
    with pytest.raises(ValidationError):
        HourInput(hour=0, demand_kwh=float("inf"), solar_kwh=0, tariff_bdt_per_kwh=5)


def test_reject_invalid_battery():
    with pytest.raises(ValidationError):
        BatteryInput(
            capacity_kwh=0,  # Must be > 0
            initial_energy_kwh=0,
            minimum_energy_kwh=0,
            max_charge_kwh_per_hour=10,
            max_discharge_kwh_per_hour=10,
        )

    with pytest.raises(ValidationError):
        BatteryInput(
            capacity_kwh=100,
            initial_energy_kwh=150,  # Exceeds capacity
            minimum_energy_kwh=20,
            max_charge_kwh_per_hour=10,
            max_discharge_kwh_per_hour=10,
        )


def test_interpretation_schema():
    # Valid no_op
    noop = DirectiveInterpretation(
        note_index=0,
        applies=False,
        directive_type=DirectiveType.NO_OP,
        structured_adjustment=None,
        explanation="Ignored",
    )
    assert noop.applies is False

    # Invalid no_op (applies=True)
    with pytest.raises(ValidationError):
        DirectiveInterpretation(
            note_index=0,
            applies=True,
            directive_type=DirectiveType.NO_OP,
            structured_adjustment=None,
            explanation="Invalid",
        )

    # Invalid solar_reduction (applies=False)
    with pytest.raises(ValidationError):
        DirectiveInterpretation(
            note_index=0,
            applies=False,
            directive_type=DirectiveType.SOLAR_REDUCTION,
            structured_adjustment={"hours": [12, 13], "factor": 0.5},
            explanation="Invalid",
        )
