"""Unit tests for Directive Compiler."""

import pytest
from app.directives.compiler import DirectiveCompilationError, compile_directives
from app.schemas.interpretation import DirectiveInterpretation, DirectiveType
from app.schemas.request import BatteryInput, HourInput


def get_base_inputs():
    hours = [
        HourInput(hour=h, demand_kwh=100.0, solar_kwh=100.0, tariff_bdt_per_kwh=10.0)
        for h in range(24)
    ]
    battery = BatteryInput(
        capacity_kwh=200.0,
        initial_energy_kwh=100.0,
        minimum_energy_kwh=40.0,
        max_charge_kwh_per_hour=50.0,
        max_discharge_kwh_per_hour=50.0,
    )
    return hours, battery


def test_compile_solar_reduction():
    hours, battery = get_base_inputs()
    interps = [
        DirectiveInterpretation(
            note_index=0,
            applies=True,
            directive_type=DirectiveType.SOLAR_REDUCTION,
            structured_adjustment={"hours": [12, 13], "factor": 0.25},
            explanation="Washing",
        )
    ]
    c = compile_directives(hours, battery, interps)
    assert c.effective_solar[12] == 25.0
    assert c.effective_solar[13] == 25.0
    assert c.effective_solar[11] == 100.0  # Unaffected


def test_compile_battery_reserve():
    hours, battery = get_base_inputs()
    interps = [
        DirectiveInterpretation(
            note_index=0,
            applies=True,
            directive_type=DirectiveType.MINIMUM_BATTERY_RESERVE,
            structured_adjustment={"hours": [18, 19], "minimum_energy_kwh": 90.0},
            explanation="Emergency",
        )
    ]
    c = compile_directives(hours, battery, interps)
    assert c.minimum_battery[18] == 90.0
    assert c.minimum_battery[19] == 90.0
    assert c.minimum_battery[17] == 40.0  # Base minimum


def test_compile_charge_discharge_windows():
    hours, battery = get_base_inputs()
    interps = [
        DirectiveInterpretation(
            note_index=0,
            applies=True,
            directive_type=DirectiveType.NO_CHARGE_WINDOW,
            structured_adjustment={"hours": [2, 3]},
            explanation="Charger maintenance",
        ),
        DirectiveInterpretation(
            note_index=1,
            applies=True,
            directive_type=DirectiveType.NO_DISCHARGE_WINDOW,
            structured_adjustment={"hours": [18, 19]},
            explanation="Relay testing",
        ),
    ]
    c = compile_directives(hours, battery, interps)
    assert c.charge_allowed[2] is False
    assert c.charge_allowed[3] is False
    assert c.charge_allowed[4] is True

    assert c.discharge_allowed[18] is False
    assert c.discharge_allowed[19] is False
    assert c.discharge_allowed[20] is True


def test_compile_conflicting_solar_detection():
    hours, battery = get_base_inputs()
    interps = [
        DirectiveInterpretation(
            note_index=0,
            applies=True,
            directive_type=DirectiveType.SOLAR_REDUCTION,
            structured_adjustment={"hours": [12, 13], "factor": 0.2},
            explanation="Note 1",
        ),
        DirectiveInterpretation(
            note_index=1,
            applies=True,
            directive_type=DirectiveType.SOLAR_REDUCTION,
            structured_adjustment={"hours": [13, 14], "factor": 0.5},
            explanation="Note 2 conflicting at hour 13",
        ),
    ]
    with pytest.raises(DirectiveCompilationError):
        compile_directives(hours, battery, interps)
