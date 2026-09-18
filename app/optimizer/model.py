"""Linear program model formulation matrices for 24-hour energy scheduling."""

from dataclasses import dataclass
import numpy as np
from app.directives.compiler import CompiledConstraints
from app.schemas.request import BatteryInput, HourInput


@dataclass
class LPModel:
    c: np.ndarray
    A_ub: np.ndarray
    b_ub: np.ndarray
    A_eq: np.ndarray
    b_eq: np.ndarray
    bounds: list[tuple[float, float]]


def build_lp_model(
    hours: list[HourInput],
    battery: BatteryInput,
    constraints: CompiledConstraints,
) -> LPModel:
    """Builds the objective vector, constraint matrices, and variable bounds for HiGHS LP solver.

    Variables: 72 total
      x[0..23]:  grid[h] >= 0
      x[24..47]: solar_used[h] >= 0
      x[48..71]: delta[h] in [-max_discharge, max_charge]
    """
    n_hours = 24
    n_vars = 3 * n_hours  # 72

    # Objective: minimize sum(grid[h] * tariff[h] - 1e-7 * solar_used[h])
    c = np.zeros(n_vars, dtype=float)
    for h in range(n_hours):
        c[h] = hours[h].tariff_bdt_per_kwh
        c[n_hours + h] = -1e-7  # tiny tie-breaker preferring solar usage over curtailment

    # Variable bounds
    bounds: list[tuple[float, float]] = []

    # 1. Grid import: [0, max_grid[h] or inf]
    for h in range(n_hours):
        up = constraints.max_grid[h] if constraints.max_grid[h] is not None else float("inf")
        bounds.append((0.0, up))

    # 2. Solar used: [0, effective_solar[h]]
    for h in range(n_hours):
        bounds.append((0.0, float(constraints.effective_solar[h])))

    # 3. Battery delta: [-max_discharge, max_charge]
    for h in range(n_hours):
        lower = -float(battery.max_discharge_kwh_per_hour) if constraints.discharge_allowed[h] else 0.0
        upper = float(battery.max_charge_kwh_per_hour) if constraints.charge_allowed[h] else 0.0
        bounds.append((lower, upper))

    # Equality constraints:
    # (a) Energy balance for each hour: grid[h] + solar_used[h] - delta[h] = demand[h]  (24 constraints)
    # (b) End-of-day battery neutrality: sum(delta[h] for h=0..23) = 0                  (1 constraint)
    n_eq = n_hours + 1
    A_eq = np.zeros((n_eq, n_vars), dtype=float)
    b_eq = np.zeros(n_eq, dtype=float)

    for h in range(n_hours):
        A_eq[h, h] = 1.0                # grid[h]
        A_eq[h, n_hours + h] = 1.0      # solar_used[h]
        A_eq[h, 2 * n_hours + h] = -1.0 # -delta[h]
        b_eq[h] = float(hours[h].demand_kwh)

    # Neutrality constraint
    for h in range(n_hours):
        A_eq[n_hours, 2 * n_hours + h] = 1.0
    b_eq[n_hours] = 0.0

    # Inequality constraints (A_ub * x <= b_ub):
    # Battery storage after hour h: E_after[h] = E_init + sum_{i=0..h} delta[i]
    # 1) E_after[h] <= capacity_kwh  ==>  sum_{i=0..h} delta[i] <= capacity_kwh - E_init
    # 2) E_after[h] >= minimum_battery[h] ==> -sum_{i=0..h} delta[i] <= E_init - minimum_battery[h]
    n_ub = 2 * n_hours  # 48 constraints
    A_ub = np.zeros((n_ub, n_vars), dtype=float)
    b_ub = np.zeros(n_ub, dtype=float)

    for h in range(n_hours):
        # Upper bound: sum_{i=0..h} delta[i] <= capacity - E_init
        for i in range(h + 1):
            A_ub[h, 2 * n_hours + i] = 1.0
        b_ub[h] = float(battery.capacity_kwh - battery.initial_energy_kwh)

        # Lower bound: -sum_{i=0..h} delta[i] <= E_init - minimum_battery[h]
        row_min = n_hours + h
        for i in range(h + 1):
            A_ub[row_min, 2 * n_hours + i] = -1.0
        b_ub[row_min] = float(battery.initial_energy_kwh - constraints.minimum_battery[h])

    return LPModel(c=c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bounds)
