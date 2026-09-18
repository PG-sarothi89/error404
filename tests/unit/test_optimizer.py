"""Unit tests for HiGHS linear programming optimizer and replay validator."""

from app.directives.compiler import compile_directives
from app.optimizer.solver import solve_schedule
from app.schemas.interpretation import DirectiveInterpretation, DirectiveType
from app.schemas.request import BatteryInput, HourInput
from app.validation.replay import replay_and_validate_plan


def test_optimizer_synthetic_flow():
    hours = [
        HourInput(
            hour=h,
            demand_kwh=100.0,
            solar_kwh=50.0 if 8 <= h <= 16 else 0.0,
            tariff_bdt_per_kwh=15.0 if 17 <= h <= 21 else 5.0,
        )
        for h in range(24)
    ]
    battery = BatteryInput(
        capacity_kwh=200.0,
        initial_energy_kwh=100.0,
        minimum_energy_kwh=30.0,
        max_charge_kwh_per_hour=50.0,
        max_discharge_kwh_per_hour=50.0,
    )
    interps = [
        DirectiveInterpretation(
            note_index=0,
            applies=False,
            directive_type=DirectiveType.NO_OP,
            structured_adjustment=None,
            explanation="No change",
        )
    ]

    constraints = compile_directives(hours, battery, interps)
    plan = solve_schedule(hours, battery, constraints)

    assert len(plan) == 24
    # Replay validator must pass
    replay_and_validate_plan(hours, battery, constraints, plan)

    # End of day neutrality
    assert abs(plan[23].battery_energy_after_kwh - battery.initial_energy_kwh) < 0.01

    # Battery discharges during peak tariff hours (17-21) and charges during cheap hours
    peak_discharges = [p.battery_action for p in plan if 17 <= p.hour <= 21]
    assert "discharge" in peak_discharges
