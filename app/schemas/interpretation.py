"""Schemas for LLM directive interpretation and structured adjustments."""

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, model_validator


class DirectiveType(str, Enum):
    SOLAR_REDUCTION = "solar_reduction"
    MINIMUM_BATTERY_RESERVE = "minimum_battery_reserve"
    NO_CHARGE_WINDOW = "no_charge_window"
    NO_DISCHARGE_WINDOW = "no_discharge_window"
    MAX_GRID_WINDOW = "max_grid_window"
    NO_OP = "no_op"


class SolarReductionAdjustment(BaseModel):
    hours: list[int] = Field(..., description="Affected hours (0-23, ascending)")
    factor: float = Field(..., ge=0.0, le=1.0, description="Usable solar fraction remaining (0.0 - 1.0)")


class MinimumBatteryReserveAdjustment(BaseModel):
    hours: list[int] = Field(..., description="Affected hours (0-23, ascending)")
    minimum_energy_kwh: float = Field(..., ge=0.0, description="Minimum battery energy required in kWh")


class WindowAdjustment(BaseModel):
    hours: list[int] = Field(..., description="Affected hours (0-23, ascending)")


class MaxGridWindowAdjustment(BaseModel):
    hours: list[int] = Field(..., description="Affected hours (0-23, ascending)")
    max_grid_kwh: float = Field(..., ge=0.0, description="Maximum allowable grid import in kWh")


class DirectiveInterpretation(BaseModel):
    note_index: int = Field(..., ge=0, description="Zero-based index of the corresponding operator note")
    applies: bool = Field(..., description="True for applicable directives, False only for no_op")
    directive_type: DirectiveType = Field(..., description="One of the supported directive types")
    structured_adjustment: dict[str, Any] | None = Field(
        default=None,
        description="Structured adjustment object, or null only for no_op",
    )
    explanation: str = Field(..., description="Short explanation of the interpretation")

    @model_validator(mode="after")
    def validate_applies_and_adjustment(self) -> "DirectiveInterpretation":
        if self.directive_type == DirectiveType.NO_OP:
            if self.applies is not False:
                raise ValueError("For directive_type 'no_op', 'applies' must be false")
            if self.structured_adjustment is not None:
                raise ValueError("For directive_type 'no_op', 'structured_adjustment' must be null")
        else:
            if self.applies is not True:
                raise ValueError(f"For directive_type '{self.directive_type.value}', 'applies' must be true")
            if self.structured_adjustment is None:
                raise ValueError(
                    f"For directive_type '{self.directive_type.value}', 'structured_adjustment' cannot be null"
                )
        return self


class LLMInterpretationOutput(BaseModel):
    directive_interpretation: list[DirectiveInterpretation] = Field(
        ...,
        description="List of interpreted directives, exactly one per operator note in note_index order",
    )
