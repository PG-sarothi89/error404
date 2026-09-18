"""Performance benchmark and latency evaluation suite."""

import time
import pytest
from app.schemas.request import OptimizeEnergyRequest
from app.services.optimize import OptimizationService


@pytest.mark.asyncio
async def test_repeated_request_stability_and_latency(public_cases_data):
    """Measures latency percentiles across 50 repeated requests and ensures 0% failure rate."""
    service = OptimizationService()
    sample_input = public_cases_data["cases"][0]["input"]
    req = OptimizeEnergyRequest.model_validate(sample_input)

    latencies = []
    num_requests = 50

    for i in range(num_requests):
        # Modify scenario_id slightly to test per-request isolation
        req_copy = req.model_copy(update={"scenario_id": f"PERF-{i}"})

        start = time.perf_counter()
        resp = await service.optimize(req_copy)
        dur = time.perf_counter() - start

        latencies.append(dur)
        assert resp.scenario_id == f"PERF-{i}"
        assert len(resp.hourly_plan) == 24

    latencies.sort()
    min_lat = latencies[0]
    med_lat = latencies[len(latencies) // 2]
    p90_lat = latencies[int(len(latencies) * 0.90)]
    p95_lat = latencies[int(len(latencies) * 0.95)]
    max_lat = latencies[-1]

    print(f"\n--- LATENCY BENCHMARK ({num_requests} requests) ---")
    print(f"Min:    {min_lat*1000:.2f} ms")
    print(f"Median: {med_lat*1000:.2f} ms")
    print(f"p90:    {p90_lat*1000:.2f} ms")
    print(f"p95:    {p95_lat*1000:.2f} ms")
    print(f"Max:    {max_lat*1000:.2f} ms")

    # Local optimization pipeline should execute within milliseconds
    assert p95_lat < 1.0, f"p95 latency exceeded 1.0s: {p95_lat}s"
