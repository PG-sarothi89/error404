"""HiGHS Linear Programming solver for 24-hour dispatch optimization."""

import logging
from scipy.optimize import linprog

from app.directives.compiler import CompiledConstraints
from app.optimizer.model import build_lp_model
from app.schemas.request import BatteryInput, HourInput
from app.schemas.response import BatteryAction, HourlyPlanEntry

logger = logging.getLogger("gridwise.solver")

EPS = 1e-7


class SolverError(RuntimeError):
    """Raised when the optimization problem cannot be solved to optimality."""
    pass


def solve_schedule(
    hours: list[HourInput],
    battery: BatteryInput,
    constraints: CompiledConstraints,
) -> list[HourlyPlanEntry]:
    """Solves the 24-hour cost minimization LP and decodes the hourly plan."""
    lp_model = build_lp_model(hours, battery, constraints)

    # HiGHS LP solver via SciPy
    res = linprog(
        c=lp_model.c,
        A_ub=lp_model.A_ub,
        b_ub=lp_model.b_ub,
        A_eq=lp_model.A_eq,
        b_eq=lp_model.b_eq,
        bounds=lp_model.bounds,
        method="highs",
    )

    if not res.success or res.status != 0:
        logger.error(f"Solver failed: status={res.status}, message='{res.message}'")
        raise SolverError(f"Optimization solver failed: {res.message}")

    x = res.x
    n_hours = 24
    grid_raw = x[0:n_hours]
    solar_raw = x[n_hours : 2 * n_hours]
    delta_raw = x[2 * n_hours : 3 * n_hours]

    hourly_plan: list[HourlyPlanEntry] = []
    current_energy = float(battery.initial_energy_kwh)

    for h in range(n_hours):
        g = float(max(0.0, grid_raw[h]))
        s = float(max(0.0, min(solar_raw[h], constraints.effective_solar[h])))
        d = float(delta_raw[h])

        # State transition
        current_energy += d

        # Classify battery action using strictly calibrated EPS = 1e-7
        if d > EPS:
            action = BatteryAction.CHARGE
            b_kwh = d
        elif d < -EPS:
            action = BatteryAction.DISCHARGE
            b_kwh = -d
        else:
            action = BatteryAction.IDLE
            b_kwh = 0.0

        hourly_plan.append(
            HourlyPlanEntry(
                hour=h,
                grid_kwh=round(g, 6),
                solar_used_kwh=round(s, 6),
                battery_action=action,
                battery_kwh=round(b_kwh, 6),
                battery_energy_after_kwh=round(current_energy, 6),
            )
        )

    return hourly_plan
