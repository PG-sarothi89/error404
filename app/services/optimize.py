"""End-to-end optimization service pipeline."""

import logging
from app.directives.compiler import compile_directives
from app.guardrails.validator import validate_directives_guardrails
from app.llm.interpreter import LLMInterpreter
from app.optimizer.solver import solve_schedule
from app.schemas.request import OptimizeEnergyRequest
from app.schemas.response import OptimizeEnergyResponse
from app.validation.replay import replay_and_validate_plan

logger = logging.getLogger("gridwise.service")


class OptimizationService:
    """Orchestrates LLM interpretation, guardrails, compilation, LP solving, and validation."""

    def __init__(self, llm_interpreter: LLMInterpreter | None = None) -> None:
        self.llm_interpreter = llm_interpreter or LLMInterpreter()

    async def optimize(self, request: OptimizeEnergyRequest) -> OptimizeEnergyResponse:
        """Executes the complete 7-stage optimization pipeline for a 24-hour scenario."""
        logger.info(f"Processing scenario '{request.scenario_id}' with {len(request.operator_notes)} notes.")

        # Stage 1: LLM Directive Interpretation (all notes in 1 call)
        interpretations = await self.llm_interpreter.interpret_notes(
            scenario_id=request.scenario_id,
            operator_notes=request.operator_notes,
            battery_capacity_kwh=request.battery.capacity_kwh,
        )

        # Stage 2: Deterministic Guardrails Validation
        validate_directives_guardrails(
            interpretations=interpretations,
            operator_notes=request.operator_notes,
            battery_capacity_kwh=request.battery.capacity_kwh,
        )

        # Stage 3: Directive Compilation
        compiled_constraints = compile_directives(
            hours=request.hours,
            battery=request.battery,
            interpretations=interpretations,
        )

        # Stage 4: Linear Programming Optimization (HiGHS)
        hourly_plan = solve_schedule(
            hours=request.hours,
            battery=request.battery,
            constraints=compiled_constraints,
        )

        # Stage 5: Independent Replay Validation
        replay_and_validate_plan(
            hours=request.hours,
            battery=request.battery,
            constraints=compiled_constraints,
            hourly_plan=hourly_plan,
        )

        # Stage 6: Recalculate totals directly from hourly_plan (Source of Truth)
        total_grid = sum(entry.grid_kwh for entry in hourly_plan)
        total_cost = sum(entry.grid_kwh * request.hours[entry.hour].tariff_bdt_per_kwh for entry in hourly_plan)
        peak_grid = max(entry.grid_kwh for entry in hourly_plan)

        # Stage 7: Exact Response Building
        plan_summary = (
            "Schedule prioritizes available solar, shifts battery energy toward higher-tariff periods, "
            "and respects all operator constraints."
        )

        return OptimizeEnergyResponse(
            scenario_id=request.scenario_id,
            directive_interpretation=interpretations,
            hourly_plan=hourly_plan,
            total_grid_kwh=round(total_grid, 4),
            total_cost_bdt=round(total_cost, 4),
            peak_grid_kwh=round(peak_grid, 4),
            plan_summary=plan_summary,
        )
