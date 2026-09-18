"""FastAPI main application entrypoint."""

from contextlib import asynccontextmanager
import logging
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import config
from app.api.routes import router
from app.llm.interpreter import LLMInterpreter
from app.services.optimize import OptimizationService

# Setup structured logging
logging.basicConfig(
    level=logging.DEBUG if config.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("gridwise")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manages application startup and teardown resources."""
    logger.info(f"Starting GridWise Energy Optimizer (Provider: {config.LLM_PROVIDER})...")
    llm_interpreter = LLMInterpreter()
    app.state.llm_interpreter = llm_interpreter
    app.state.optimization_service = OptimizationService(llm_interpreter=llm_interpreter)
    yield
    logger.info("Shutting down GridWise Energy Optimizer...")
    await llm_interpreter.close()


app = FastAPI(
    title="GridWise LLM Energy Optimizer",
    version="2.0",
    description="Smart Campus Energy Optimization with LLM-Assisted Operator Directive Interpretation",
    lifespan=lifespan,
)

# Allow CORS for public API testability
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Returns HTTP 400 for malformed or structurally invalid requests per challenge spec."""
    logger.warning(f"Request validation error on {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=400,
        content={
            "error": "Malformed or structurally invalid request",
            "details": [
                {
                    "loc": list(err.get("loc", [])),
                    "msg": err.get("msg", ""),
                    "type": err.get("type", ""),
                }
                for err in exc.errors()
            ],
        },
    )


# Register API routes
app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=config.HOST, port=config.PORT, reload=config.DEBUG)
