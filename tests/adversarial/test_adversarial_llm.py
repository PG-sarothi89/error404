"""Adversarial and paraphrase tests for LLM interpretation and metamorphic properties."""

import pytest
from app.llm.fallback import fallback_parse_note
from app.schemas.interpretation import DirectiveType
from app.services.optimize import OptimizationService
from app.schemas.request import OptimizeEnergyRequest, HourInput, BatteryInput


def test_adversarial_solar_paraphrases():
    variations = [
        "PV production will drop to about 20% between 13:00 and 15:00.",
        "Panel washing from one until three will leave roughly one-fifth of normal solar output.",
        "Expect an 80% reduction in rooftop solar during the 1-3 PM maintenance window.",
    ]

    for note in variations:
        interp = fallback_parse_note(note, note_index=0, battery_capacity_kwh=200.0)
        assert interp.directive_type == DirectiveType.SOLAR_REDUCTION
        assert interp.applies is True
        assert interp.structured_adjustment["hours"] == [13, 14]
        assert abs(interp.structured_adjustment["factor"] - 0.20) < 0.01


@pytest.mark.asyncio
async def test_metamorphic_no_charge_property():
    """Metamorphic test: in a no_charge_window, no hour should perform charging."""
    service = OptimizationService()
    hours = [
        HourInput(hour=h, demand_kwh=100.0, solar_kwh=0.0, tariff_bdt_per_kwh=5.0)
        for h in range(24)
    ]
    battery = BatteryInput(
        capacity_kwh=200.0,
        initial_energy_kwh=100.0,
        minimum_energy_kwh=30.0,
        max_charge_kwh_per_hour=50.0,
        max_discharge_kwh_per_hour=50.0,
    )
    req = OptimizeEnergyRequest(
        scenario_id="META-NO-CHARGE",
        operator_notes=["The charger is isolated from 2 AM until 6 AM."],
        hours=hours,
        battery=battery,
    )
    resp = await service.optimize(req)

    for h in [2, 3, 4, 5]:
        entry = resp.hourly_plan[h]
        assert entry.battery_action != "charge"
        assert entry.battery_kwh == 0.0 or entry.battery_action == "discharge"


@pytest.mark.asyncio
async def test_metamorphic_grid_cap_property():
    """Metamorphic test: in a max_grid_window, grid import must be <= cap."""
    service = OptimizationService()
    hours = [
        HourInput(hour=h, demand_kwh=120.0, solar_kwh=0.0, tariff_bdt_per_kwh=10.0)
        for h in range(24)
    ]
    battery = BatteryInput(
        capacity_kwh=300.0,
        initial_energy_kwh=150.0,
        minimum_energy_kwh=30.0,
        max_charge_kwh_per_hour=60.0,
        max_discharge_kwh_per_hour=60.0,
    )
    cap = 100.0
    req = OptimizeEnergyRequest(
        scenario_id="META-GRID-CAP",
        operator_notes=[f"Campus grid intake must not exceed {cap:.0f} kWh from 6 PM until 8 PM."],
        hours=hours,
        battery=battery,
    )
    resp = await service.optimize(req)

    for h in [18, 19]:
        assert resp.hourly_plan[h].grid_kwh <= cap + 0.01
