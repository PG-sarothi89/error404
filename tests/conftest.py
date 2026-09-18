"""Shared pytest fixtures."""

import json
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from app.llm.interpreter import LLMInterpreter
from app.main import app
from app.services.optimize import OptimizationService


@pytest.fixture
def public_cases_data() -> dict:
    """Loads public sample cases JSON."""
    data_path = Path(__file__).resolve().parent.parent / "data" / "public_cases.json"
    with open(data_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
async def async_client():
    """Async HTTP client for testing FastAPI application with initialized services."""
    llm = LLMInterpreter()
    app.state.llm_interpreter = llm
    app.state.optimization_service = OptimizationService(llm_interpreter=llm)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    await llm.close()
