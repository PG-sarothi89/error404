"""Response schemas for GET /health and POST /optimize-energy."""

from enum import Enum
from pydantic import BaseModel, Field
from app.schemas.interpretation import DirectiveInterpretation


class BatteryAction(str, Enum):
    CHARGE = "charge"
    DISCHARGE = "discharge"
    IDLE = "idle"


class HourlyPlanEntry(BaseModel):
    hour: int = Field(..., ge=0, le=23, description="Hour from 0 to 23")
    grid_kwh: float = Field(..., ge=0.0, description="Grid energy purchased in this hour")
    solar_used_kwh: float = Field(..., ge=0.0, description="Solar energy used in this hour")
    battery_action: BatteryAction = Field(..., description="Action taken: charge, discharge, or idle")
    battery_kwh: float = Field(..., ge=0.0, description="Energy charged or discharged (0 if idle)")
    battery_energy_after_kwh: float = Field(
        ...,
        ge=0.0,
        description="Battery energy stored after this hour's action",
    )


class OptimizeEnergyResponse(BaseModel):
    scenario_id: str = Field(..., description="Echoes the request scenario_id")
    directive_interpretation: list[DirectiveInterpretation] = Field(
        ...,
        description="Interpreted directives for each operator note",
    )
    hourly_plan: list[HourlyPlanEntry] = Field(
        ...,
        min_length=24,
        max_length=24,
        description="24-hour optimized schedule",
    )
    total_grid_kwh: float = Field(..., ge=0.0, description="Total grid energy purchased across 24 hours")
    total_cost_bdt: float = Field(..., ge=0.0, description="Total cost in BDT of purchased grid energy")
    peak_grid_kwh: float = Field(..., ge=0.0, description="Peak hourly grid import")
    plan_summary: str = Field(..., description="Short human-readable summary of the plan")


class HealthResponse(BaseModel):
    status: str = Field(default="ok", description="Service readiness status")
