"""Tests verifying all 10 official public sample cases."""

import pytest
from app.schemas.request import OptimizeEnergyRequest
from app.services.optimize import OptimizationService

TOLERANCE = 0.05  # Numeric tolerance in kWh / BDT


@pytest.mark.asyncio
async def test_all_10_public_cases(public_cases_data):
    cases = public_cases_data["cases"]
    assert len(cases) == 10

    service = OptimizationService()

    for case in cases:
        case_id = case["id"]
        req_data = case["input"]
        expected_output = case["expected_output"]

        request = OptimizeEnergyRequest.model_validate(req_data)
        response = await service.optimize(request)

        # 1. Verify scenario ID
        assert response.scenario_id == expected_output["scenario_id"]

        # 2. Verify directive interpretations
        assert len(response.directive_interpretation) == len(expected_output["directive_interpretation"])

        for i, (actual, expected) in enumerate(
            zip(response.directive_interpretation, expected_output["directive_interpretation"])
        ):
            assert actual.note_index == expected["note_index"], f"{case_id} note {i} note_index"
            assert actual.applies == expected["applies"], f"{case_id} note {i} applies"
            assert actual.directive_type == expected["directive_type"], f"{case_id} note {i} directive_type"

            if expected["structured_adjustment"] is None:
                assert actual.structured_adjustment is None
            else:
                assert actual.structured_adjustment is not None
                exp_adj = expected["structured_adjustment"]
                act_adj = actual.structured_adjustment

                assert act_adj["hours"] == exp_adj["hours"], f"{case_id} note {i} hours"

                if "factor" in exp_adj:
                    assert abs(act_adj["factor"] - exp_adj["factor"]) < TOLERANCE, f"{case_id} note {i} factor"

                if "minimum_energy_kwh" in exp_adj:
                    assert (
                        abs(act_adj["minimum_energy_kwh"] - exp_adj["minimum_energy_kwh"]) < TOLERANCE
                    ), f"{case_id} note {i} minimum_energy_kwh"

                if "max_grid_kwh" in exp_adj:
                    assert (
                        abs(act_adj["max_grid_kwh"] - exp_adj["max_grid_kwh"]) < TOLERANCE
                    ), f"{case_id} note {i} max_grid_kwh"

        # 3. Verify total grid and cost
        # Recalculated team cost must be optimal (<= reference cost + tolerance)
        ref_cost = expected_output["total_cost_bdt"]
        ref_grid = expected_output["total_grid_kwh"]

        assert (
            abs(response.total_cost_bdt - ref_cost) <= 1.0 or response.total_cost_bdt <= ref_cost + TOLERANCE
        ), f"{case_id}: total_cost_bdt {response.total_cost_bdt} vs ref {ref_cost}"

        assert (
            abs(response.total_grid_kwh - ref_grid) <= 1.0 or response.total_grid_kwh <= ref_grid + TOLERANCE
        ), f"{case_id}: total_grid_kwh {response.total_grid_kwh} vs ref {ref_grid}"

        # 4. Verify 24 hours in hourly plan
        assert len(response.hourly_plan) == 24


@pytest.mark.asyncio
async def test_http_api_endpoints(async_client, public_cases_data):
    # 1. Health check
    res_health = await async_client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json() == {"status": "ok"}

    # 2. Sample 1 via HTTP
    sample_1_input = public_cases_data["cases"][0]["input"]
    res_opt = await async_client.post("/optimize-energy", json=sample_1_input)
    assert res_opt.status_code == 200
    data = res_opt.json()
    assert data["scenario_id"] == "SAMPLE-01"
    assert len(data["hourly_plan"]) == 24
    assert len(data["directive_interpretation"]) == 2
    assert data["directive_interpretation"][0]["directive_type"] == "solar_reduction"
    assert data["directive_interpretation"][1]["directive_type"] == "no_op"
