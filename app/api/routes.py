"""FastAPI HTTP routes for /health and /optimize-energy."""

import logging
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.guardrails.validator import GuardrailValidationError
from app.optimizer.solver import SolverError
from app.schemas.request import OptimizeEnergyRequest
from app.schemas.response import HealthResponse, OptimizeEnergyResponse
from app.validation.replay import ReplayValidationError

logger = logging.getLogger("gridwise.api")
router = APIRouter()


@router.get("/health", response_model=HealthResponse, status_code=200)
async def health_check() -> HealthResponse:
    """Readiness endpoint for the competition judging harness."""
    return HealthResponse(status="ok")


@router.post("/optimize-energy", response_model=OptimizeEnergyResponse, status_code=200)
async def optimize_energy(request: OptimizeEnergyRequest, req: Request) -> OptimizeEnergyResponse:
    """Accepts a 24-hour scenario and returns structured interpretation and optimized schedule."""
    service = req.app.state.optimization_service
    try:
        response = await service.optimize(request)
        return response
    except (GuardrailValidationError, SolverError, ReplayValidationError) as err:
        logger.error(f"Controlled pipeline error for scenario '{request.scenario_id}': {err}")
        raise HTTPException(
            status_code=500,
            detail=f"Optimization pipeline error: {type(err).__name__}",
        )
    except Exception as exc:
        logger.error(f"Unexpected error processing scenario '{request.scenario_id}': {exc}")
        # Never leak secrets or raw tracebacks
        raise HTTPException(
            status_code=500,
            detail="Controlled internal server error",
        )
