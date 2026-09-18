"""End-to-end optimization service pipeline."""

import logging
from app.directives.compiler import compile_directives
from app.guardrails.validator import validate_directives_guardrails
from app.llm.interpreter import LLMInterpreter
from app.optimizer.solver import solve_schedule
from app.schemas.interpretation import DirectiveType
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

        # Stage 7: Exact Response Building (contextual strategy summary)
        summary_parts: list[str] = []
        for interp in interpretations:
            if interp.applies and interp.directive_type != DirectiveType.NO_OP:
                if interp.directive_type == DirectiveType.SOLAR_REDUCTION:
                    summary_parts.append("incorporates reduced solar availability")
                elif interp.directive_type == DirectiveType.MINIMUM_BATTERY_RESERVE:
                    summary_parts.append("maintains mandated emergency battery reserve")
                elif interp.directive_type == DirectiveType.NO_CHARGE_WINDOW:
                    summary_parts.append("observes restricted charging window")
                elif interp.directive_type == DirectiveType.NO_DISCHARGE_WINDOW:
                    summary_parts.append("observes restricted discharging window")
                elif interp.directive_type == DirectiveType.MAX_GRID_WINDOW:
                    summary_parts.append("strictly adheres to peak grid intake limits")

        if summary_parts:
            plan_summary = (
                f"Optimized 24-hour schedule {', '.join(summary_parts)}, "
                f"shifts battery energy to avoid peak tariffs, and restores end-of-day battery neutrality."
            )
        else:
            plan_summary = (
                "Schedule prioritizes available solar, shifts battery energy toward higher-tariff periods, "
                "and maintains end-of-day battery neutrality."
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
