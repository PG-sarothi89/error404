"""Directive Compiler: Transforms validated directives into canonical 24-hour mathematical constraints."""

from dataclasses import dataclass
from app.schemas.interpretation import DirectiveInterpretation, DirectiveType
from app.schemas.request import BatteryInput, HourInput


class DirectiveCompilationError(ValueError):
    """Raised when directives contain ambiguous or contradictory configurations."""
    pass


@dataclass
class CompiledConstraints:
    effective_solar: list[float]
    minimum_battery: list[float]
    charge_allowed: list[bool]
    discharge_allowed: list[bool]
    max_grid: list[float | None]


def compile_directives(
    hours: list[HourInput],
    battery: BatteryInput,
    interpretations: list[DirectiveInterpretation],
) -> CompiledConstraints:
    """Compiles scenario base parameters and active directives into 24-hour constraint arrays."""
    # Base canonical arrays for 24 hours
    effective_solar = [h.solar_kwh for h in hours]
    minimum_battery = [battery.minimum_energy_kwh for _ in range(24)]
    charge_allowed = [True for _ in range(24)]
    discharge_allowed = [True for _ in range(24)]
    max_grid: list[float | None] = [None for _ in range(24)]

    # Track overlapping directives to detect ambiguous combinations (Section 22)
    solar_directive_hours: dict[int, float] = {}

    for interp in interpretations:
        if not interp.applies or interp.directive_type == DirectiveType.NO_OP:
            continue

        adj = interp.structured_adjustment
        if adj is None:
            continue

        affected_hours = adj.get("hours", [])
        dtype = interp.directive_type

        # 1. Solar reduction
        if dtype == DirectiveType.SOLAR_REDUCTION:
            factor = float(adj["factor"])
            for h in affected_hours:
                if h in solar_directive_hours and solar_directive_hours[h] != factor:
                    raise DirectiveCompilationError(
                        f"Hour {h} has multiple conflicting solar reduction factors: "
                        f"{solar_directive_hours[h]} vs {factor}"
                    )
                solar_directive_hours[h] = factor
                effective_solar[h] = hours[h].solar_kwh * factor

        # 2. Minimum battery reserve
        elif dtype == DirectiveType.MINIMUM_BATTERY_RESERVE:
            min_kwh = float(adj["minimum_energy_kwh"])
            for h in affected_hours:
                # Official rule: max(base_minimum, directive_minimum)
                minimum_battery[h] = max(minimum_battery[h], min_kwh)

        # 3. No charge window
        elif dtype == DirectiveType.NO_CHARGE_WINDOW:
            for h in affected_hours:
                charge_allowed[h] = False

        # 4. No discharge window
        elif dtype == DirectiveType.NO_DISCHARGE_WINDOW:
            for h in affected_hours:
                discharge_allowed[h] = False

        # 5. Max grid window
        elif dtype == DirectiveType.MAX_GRID_WINDOW:
            cap_kwh = float(adj["max_grid_kwh"])
            for h in affected_hours:
                if max_grid[h] is not None:
                    max_grid[h] = min(max_grid[h], cap_kwh)
                else:
                    max_grid[h] = cap_kwh

    return CompiledConstraints(
        effective_solar=effective_solar,
        minimum_battery=minimum_battery,
        charge_allowed=charge_allowed,
        discharge_allowed=discharge_allowed,
        max_grid=max_grid,
    )
