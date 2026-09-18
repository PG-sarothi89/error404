"""Independent Replay Validator: Verifies the resulting schedule against all GridWise and directive rules."""

import logging
from app.directives.compiler import CompiledConstraints
from app.schemas.request import BatteryInput, HourInput
from app.schemas.response import BatteryAction, HourlyPlanEntry

logger = logging.getLogger("gridwise.replay")

TOLERANCE = 0.01  # Official judge tolerance (0.01 kWh / 0.01 BDT)


class ReplayValidationError(ValueError):
    """Raised when an hourly plan violates GridWise energy balance, battery, or directive constraints."""
    pass


def replay_and_validate_plan(
    hours: list[HourInput],
    battery: BatteryInput,
    constraints: CompiledConstraints,
    hourly_plan: list[HourlyPlanEntry],
) -> None:
    """Independently re-simulates and validates the 24-hour schedule hour by hour."""
    # 1. Plan structure check
    if len(hourly_plan) != 24:
        raise ReplayValidationError(f"Expected exactly 24 hours in hourly_plan, got {len(hourly_plan)}")

    current_battery = float(battery.initial_energy_kwh)

    for h, entry in enumerate(hourly_plan):
        if entry.hour != h:
            raise ReplayValidationError(f"Expected hour index {h}, got {entry.hour}")

        g = entry.grid_kwh
        s = entry.solar_used_kwh
        action = entry.battery_action
        b_kwh = entry.battery_kwh
        e_after = entry.battery_energy_after_kwh
        demand = hours[h].demand_kwh
        eff_solar = constraints.effective_solar[h]

        # 2. Non-negativity
        if g < -TOLERANCE or s < -TOLERANCE or b_kwh < -TOLERANCE or e_after < -TOLERANCE:
            raise ReplayValidationError(
                f"Hour {h}: negative energy values detected (grid={g}, solar={s}, battery={b_kwh}, after={e_after})"
            )

        # 3. Solar usage bound
        if s > eff_solar + TOLERANCE:
            raise ReplayValidationError(
                f"Hour {h}: solar_used ({s}) exceeds effective solar availability ({eff_solar})"
            )

        # 4. Battery actions and rate limits
        c_kwh = 0.0
        d_kwh = 0.0

        if action == BatteryAction.CHARGE:
            c_kwh = b_kwh
            if not constraints.charge_allowed[h]:
                raise ReplayValidationError(f"Hour {h}: charging performed during active no_charge_window")
            if c_kwh > battery.max_charge_kwh_per_hour + TOLERANCE:
                raise ReplayValidationError(
                    f"Hour {h}: charge amount {c_kwh} exceeds max charge rate {battery.max_charge_kwh_per_hour}"
                )
            expected_after = current_battery + c_kwh

        elif action == BatteryAction.DISCHARGE:
            d_kwh = b_kwh
            if not constraints.discharge_allowed[h]:
                raise ReplayValidationError(f"Hour {h}: discharging performed during active no_discharge_window")
            if d_kwh > battery.max_discharge_kwh_per_hour + TOLERANCE:
                raise ReplayValidationError(
                    f"Hour {h}: discharge amount {d_kwh} exceeds max discharge rate {battery.max_discharge_kwh_per_hour}"
                )
            expected_after = current_battery - d_kwh

        else:  # IDLE
            if abs(b_kwh) > TOLERANCE:
                raise ReplayValidationError(f"Hour {h}: battery_kwh must be 0 for idle action, got {b_kwh}")
            expected_after = current_battery

        # Verify state transition
        if abs(e_after - expected_after) > TOLERANCE:
            raise ReplayValidationError(
                f"Hour {h}: battery state transition mismatch: expected {expected_after:.3f}, got {e_after:.3f}"
            )

        # 5. Battery capacity and minimum bounds
        min_allowed = constraints.minimum_battery[h]
        if e_after < min_allowed - TOLERANCE:
            raise ReplayValidationError(
                f"Hour {h}: battery energy ({e_after:.3f}) fell below minimum required ({min_allowed:.3f})"
            )
        if e_after > battery.capacity_kwh + TOLERANCE:
            raise ReplayValidationError(
                f"Hour {h}: battery energy ({e_after:.3f}) exceeded capacity ({battery.capacity_kwh:.3f})"
            )

        # 6. Grid cap directive check
        if constraints.max_grid[h] is not None:
            grid_cap = constraints.max_grid[h]
            if g > grid_cap + TOLERANCE:
                raise ReplayValidationError(
                    f"Hour {h}: grid import ({g:.3f}) exceeded active max_grid cap ({grid_cap:.3f})"
                )

        # 7. Energy balance check: grid + solar_used + discharge = demand + charge
        supply = g + s + d_kwh
        consumption = demand + c_kwh
        if abs(supply - consumption) > TOLERANCE:
            raise ReplayValidationError(
                f"Hour {h}: energy balance violated: supply={supply:.3f} != demand+charge={consumption:.3f} (diff={abs(supply - consumption):.4f})"
            )

        current_battery = e_after

    # 8. End-of-day battery neutrality
    if abs(current_battery - battery.initial_energy_kwh) > TOLERANCE:
        raise ReplayValidationError(
            f"End-of-day battery neutrality failed: final energy {current_battery:.3f} != initial {battery.initial_energy_kwh:.3f}"
        )

    logger.debug("Independent replay validation passed successfully.")
