"""Request models and validation for POST /optimize-energy."""

import math
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _check_finite_non_negative(v: float, name: str) -> float:
    if not isinstance(v, (int, float)):
        raise ValueError(f"{name} must be a numeric value")
    if not math.isfinite(v):
        raise ValueError(f"{name} must be a finite number, got {v}")
    if v < 0:
        raise ValueError(f"{name} must be non-negative, got {v}")
    return float(v)


class HourInput(BaseModel):
    hour: int = Field(..., ge=0, le=23, description="Hour of the day (0-23)")
    demand_kwh: float = Field(..., description="Campus electrical demand in kWh")
    solar_kwh: float = Field(..., description="Base solar generation available in kWh")
    tariff_bdt_per_kwh: float = Field(..., description="Grid electricity price in BDT/kWh")

    @field_validator("demand_kwh")
    @classmethod
    def validate_demand(cls, v: float) -> float:
        return _check_finite_non_negative(v, "demand_kwh")

    @field_validator("solar_kwh")
    @classmethod
    def validate_solar(cls, v: float) -> float:
        return _check_finite_non_negative(v, "solar_kwh")

    @field_validator("tariff_bdt_per_kwh")
    @classmethod
    def validate_tariff(cls, v: float) -> float:
        return _check_finite_non_negative(v, "tariff_bdt_per_kwh")


class BatteryInput(BaseModel):
    capacity_kwh: float = Field(..., description="Maximum storage capacity in kWh")
    initial_energy_kwh: float = Field(..., description="Starting energy level at hour 0 in kWh")
    minimum_energy_kwh: float = Field(..., description="Base reserve level in kWh")
    max_charge_kwh_per_hour: float = Field(..., description="Maximum charging rate per hour in kWh")
    max_discharge_kwh_per_hour: float = Field(..., description="Maximum discharging rate per hour in kWh")

    @field_validator("capacity_kwh")
    @classmethod
    def validate_capacity(cls, v: float) -> float:
        val = _check_finite_non_negative(v, "capacity_kwh")
        if val <= 0:
            raise ValueError(f"capacity_kwh must be strictly positive, got {val}")
        return val

    @field_validator("initial_energy_kwh")
    @classmethod
    def validate_initial(cls, v: float) -> float:
        return _check_finite_non_negative(v, "initial_energy_kwh")

    @field_validator("minimum_energy_kwh")
    @classmethod
    def validate_minimum(cls, v: float) -> float:
        return _check_finite_non_negative(v, "minimum_energy_kwh")

    @field_validator("max_charge_kwh_per_hour")
    @classmethod
    def validate_max_charge(cls, v: float) -> float:
        return _check_finite_non_negative(v, "max_charge_kwh_per_hour")

    @field_validator("max_discharge_kwh_per_hour")
    @classmethod
    def validate_max_discharge(cls, v: float) -> float:
        return _check_finite_non_negative(v, "max_discharge_kwh_per_hour")

    @model_validator(mode="after")
    def validate_bounds(self) -> "BatteryInput":
        if self.initial_energy_kwh > self.capacity_kwh:
            raise ValueError(
                f"initial_energy_kwh ({self.initial_energy_kwh}) cannot exceed capacity_kwh ({self.capacity_kwh})"
            )
        if self.minimum_energy_kwh > self.capacity_kwh:
            raise ValueError(
                f"minimum_energy_kwh ({self.minimum_energy_kwh}) cannot exceed capacity_kwh ({self.capacity_kwh})"
            )
        return self


class OptimizeEnergyRequest(BaseModel):
    scenario_id: str = Field(..., min_length=1, description="Unique scenario identifier")
    operator_notes: list[str] = Field(
        ...,
        min_length=1,
        max_length=3,
        description="Array of 1 to 3 non-empty natural-language strings",
    )
    hours: list[HourInput] = Field(
        ...,
        min_length=24,
        max_length=24,
        description="Array of exactly 24 hourly energy readings",
    )
    battery: BatteryInput = Field(..., description="Battery storage configuration")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "scenario_id": "SAMPLE-01",
                "operator_notes": [
                    "Facilities will wash the rooftop solar panels from noon until 2 PM. During cleaning, usable solar should be treated as roughly 25% of the forecast.",
                    "The sports office moved next month registration deadline."
                ],
                "hours": [
                    {"hour": 0, "demand_kwh": 90.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 6.0},
                    {"hour": 1, "demand_kwh": 85.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 6.0},
                    {"hour": 2, "demand_kwh": 80.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 5.0},
                    {"hour": 3, "demand_kwh": 80.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 5.0},
                    {"hour": 4, "demand_kwh": 85.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 5.0},
                    {"hour": 5, "demand_kwh": 95.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 6.0},
                    {"hour": 6, "demand_kwh": 110.0, "solar_kwh": 5.0, "tariff_bdt_per_kwh": 8.0},
                    {"hour": 7, "demand_kwh": 130.0, "solar_kwh": 20.0, "tariff_bdt_per_kwh": 10.0},
                    {"hour": 8, "demand_kwh": 150.0, "solar_kwh": 50.0, "tariff_bdt_per_kwh": 12.0},
                    {"hour": 9, "demand_kwh": 165.0, "solar_kwh": 90.0, "tariff_bdt_per_kwh": 14.0},
                    {"hour": 10, "demand_kwh": 175.0, "solar_kwh": 130.0, "tariff_bdt_per_kwh": 16.0},
                    {"hour": 11, "demand_kwh": 180.0, "solar_kwh": 160.0, "tariff_bdt_per_kwh": 16.0},
                    {"hour": 12, "demand_kwh": 185.0, "solar_kwh": 180.0, "tariff_bdt_per_kwh": 15.0},
                    {"hour": 13, "demand_kwh": 180.0, "solar_kwh": 170.0, "tariff_bdt_per_kwh": 14.0},
                    {"hour": 14, "demand_kwh": 170.0, "solar_kwh": 140.0, "tariff_bdt_per_kwh": 13.0},
                    {"hour": 15, "demand_kwh": 165.0, "solar_kwh": 90.0, "tariff_bdt_per_kwh": 14.0},
                    {"hour": 16, "demand_kwh": 170.0, "solar_kwh": 45.0, "tariff_bdt_per_kwh": 18.0},
                    {"hour": 17, "demand_kwh": 185.0, "solar_kwh": 10.0, "tariff_bdt_per_kwh": 22.0},
                    {"hour": 18, "demand_kwh": 205.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 28.0},
                    {"hour": 19, "demand_kwh": 215.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 30.0},
                    {"hour": 20, "demand_kwh": 205.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 26.0},
                    {"hour": 21, "demand_kwh": 175.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 18.0},
                    {"hour": 22, "demand_kwh": 135.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 10.0},
                    {"hour": 23, "demand_kwh": 105.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 7.0},
                ],
                "battery": {
                    "capacity_kwh": 220.0,
                    "initial_energy_kwh": 110.0,
                    "minimum_energy_kwh": 40.0,
                    "max_charge_kwh_per_hour": 50.0,
                    "max_discharge_kwh_per_hour": 50.0,
                },
            }
        }
    )

    @field_validator("scenario_id")
    @classmethod
    def validate_scenario_id(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("scenario_id cannot be empty or whitespace")
        return s

    @field_validator("operator_notes")
    @classmethod
    def validate_operator_notes(cls, v: list[str]) -> list[str]:
        if not (1 <= len(v) <= 3):
            raise ValueError(f"operator_notes must contain between 1 and 3 items, got {len(v)}")
        cleaned = []
        for idx, note in enumerate(v):
            if not isinstance(note, str) or not note.strip():
                raise ValueError(f"operator_notes[{idx}] must be a non-empty string")
            cleaned.append(note.strip())
        return cleaned

    @field_validator("hours")
    @classmethod
    def validate_hours(cls, v: list[HourInput]) -> list[HourInput]:
        if len(v) != 24:
            raise ValueError(f"hours array must have exactly 24 items, got {len(v)}")
        hour_numbers = [item.hour for item in v]
        if len(set(hour_numbers)) != 24:
            raise ValueError("hours array contains duplicate hour values")
        if hour_numbers != list(range(24)):
            raise ValueError(f"hours array must contain hours 0 through 23 in ascending order, got {hour_numbers}")
        return v
