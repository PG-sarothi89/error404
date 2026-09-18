# GridWise LLM Energy Optimizer

> **BUP CSE Fest 2026 · Hackathon · Preliminary Round**  
> Smart Campus Energy Optimization with LLM-Assisted Operator Directive Interpretation

---

## 1. Problem Overview

BUP operates a smart campus microgrid powered by rooftop solar photovoltaic (PV) generation, an on-site Battery Energy Storage System (BESS), and grid power purchases under time-of-use tariffs. Campus demand, forecast solar availability, and grid tariffs fluctuate throughout a 24-hour planning horizon.

In addition to forecast metrics, campus human operators issue short natural-language operating notes describing temporary conditions (e.g., panel washing, maintenance windows, emergency battery reserve mandates, transformer intake limits, or irrelevant announcements). 

The goal of this service is to:
1. Ingest the 24-hour scenario and operator notes.
2. Interpret operator notes into machine-checkable structured directives using an LLM.
3. Validate all extracted directives through strict deterministic guardrails.
4. Compile directives into canonical mathematical constraint vectors.
5. Solve a 24-hour cost-minimization Linear Program (LP) to schedule battery charging, discharging, solar consumption, and grid purchases.
6. Independently replay and validate the resulting schedule.
7. Return the canonical JSON response adhering strictly to the competition contract.

---

## 2. End-to-End Pipeline Architecture

```
Operator Notes (1–3)
         │
         ▼
┌─────────────────────────────────┐
│       LLM Interpreter           │ ── All notes in ONE call; JSON Schema output
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│     Deterministic Guardrails    │ ── Enforces types, hours [0..23], factors, reserves
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│       Directive Compiler        │ ── Builds canonical 24h constraint vectors
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│        HiGHS LP Solver          │ ── Solves min Σ(grid * tariff) with neutrality
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│    Independent Replay Check     │ ── Re-verifies every constraint independently
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│        Response Builder         │ ── Recalculates totals from hourly_plan
└─────────────────────────────────┘
```

---

## 3. LLM Role & Interpretation Architecture

The language model is strictly part of the operator-note interpretation path, directly determining optimization constraints:
- **Single-Turn Batching**: All 1–3 operator notes are processed together in a single prompt to minimize p95 latency.
- **Strict JSON Enforcement**: Driven by structured JSON outputs (`responseMimeType="application/json"` on Gemini, `json_object` on OpenAI/Groq).
- **One-Shot Repair Loop**: If output is malformed or violates schema, exactly one repair attempt is issued with the specific validation error fed back.
- **Resilient Fallback**: A local deterministic NLP parser handles offline testing or provider outages without crashing or silently altering constraints.

---

## 4. Supported Directives & Semantic Rules

| Directive Type | Description | Required `structured_adjustment` |
|---|---|---|
| `solar_reduction` | Curtails usable solar generation in specific hours | `{"hours": [int, ...], "factor": float}` (factor $\in [0.0, 1.0]$) |
| `minimum_battery_reserve` | Raises battery floor in specific hours | `{"hours": [int, ...], "minimum_energy_kwh": float}` |
| `no_charge_window` | Prohibits battery charging | `{"hours": [int, ...]}` |
| `no_discharge_window` | Prohibits battery discharging | `{"hours": [int, ...]}` |
| `max_grid_window` | Caps grid import (transformer/feeder limit) | `{"hours": [int, ...], "max_grid_kwh": float}` |
| `no_op` | Irrelevant distractor note (no schedule impact) | `null` (`applies: false`) |

### Key Semantic Rules:
1. **Whole-Hour Intervals**: Start inclusive, end exclusive. Example: *1 PM to 3 PM* $\rightarrow$ `[13, 14]`.
2. **Solar Factor**: Remaining usable fraction. Example: *"80% reduction"* $\rightarrow$ `factor = 0.20`. *"Drops to 20%"* $\rightarrow$ `factor = 0.20`.
3. **Reserve Percentage**: Converted against scenario battery capacity: *"50% reserve on 200 kWh battery"* $\rightarrow$ `100.0 kWh`.
4. **Applies Semantics**: `applies = false` and `structured_adjustment = null` **only** for `no_op`. For all other directives, `applies = true`.

---

## 5. Deterministic Guardrails

Before any LLM output touches the optimization model, it passes through `app/guardrails/validator.py`:
- Verified directive types against supported whitelist.
- Verified exact 1-to-1 note mapping: `note_index` strictly ordered `0 .. N-1`.
- Verified hours: unique integers, $0 \le h \le 23$, in ascending order.
- Verified bounds: solar factor $\in [0, 1]$, reserve $\le \text{capacity}$, non-negative numbers, finite floats.
- Prohibited constraint invention: demand, solar forecast, tariffs, and battery capacity cannot be modified by the LLM.

---

## 6. Optimization Formulation

Formulated as a Linear Program (LP) solved with SciPy HiGHS:

### Decision Variables (per hour $h \in \{0 \dots 23\}$):
- $g_h \ge 0$: Grid power import
- $s_h \ge 0$: Solar power consumed on-site
- $\delta_h \in [-\text{max\_discharge}_h, \text{max\_charge}_h]$: Signed battery power delta ($\delta_h > 0 \implies \text{charge}$, $\delta_h < 0 \implies \text{discharge}$)

### Constraints:
1. **Hourly Energy Balance**:
   $$\forall h: \quad g_h + s_h - \delta_h = \text{demand}_h$$
   $$(g_h + s_h + \text{discharge}_h = \text{demand}_h + \text{charge}_h)$$
2. **Solar Availability**:
   $$0 \le s_h \le \text{effective\_solar}_h$$
3. **Grid Import Bounds**:
   $$0 \le g_h \le (\text{max\_grid}_h \text{ if set else } \infty)$$
4. **Battery Energy Dynamics & Bounds**:
   $$E_h = E_{\text{initial}} + \sum_{i=0}^h \delta_i$$
   $$\text{minimum\_battery}_h \le E_h \le \text{capacity}$$
5. **End-of-Day Neutrality**:
   $$E_{23} = E_{\text{initial}} \iff \sum_{h=0}^{23} \delta_h = 0$$

### Objective:
$$\min \sum_{h=0}^{23} \left( g_h \cdot \text{tariff}_h - 10^{-7} \cdot s_h \right)$$

---

## 7. Clean-Machine Quickstart

### Prerequisites
- Python 3.11+ (or 3.13)
- `pip` or virtual environment

### 1. Clone / Enter Repository
```bash
cd gridwise
```

### 2. Create and Activate Virtual Environment
```bash
# Linux / macOS:
python3 -m venv .venv
source .venv/bin/activate

# Windows (PowerShell):
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment
```bash
cp .env.example .env
# Edit .env to set your GEMINI_API_KEY or OPENAI_API_KEY (optional for local fallback mode)
```

### 5. Start Service
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## 8. Environment Variables

| Variable | Default | Description |
|---|---|---|
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `8000` | Port number |
| `LLM_PROVIDER` | `gemini` | Model provider: `gemini`, `openai`, `groq`, or `fallback` |
| `GEMINI_API_KEY` | `""` | Google Gemini API key |
| `GEMINI_MODEL` | `gemini-3-flash-preview` | Gemini model name |
| `OPENAI_API_KEY` | `""` | OpenAI API key |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible endpoint |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model name |
| `GROQ_API_KEY` | `""` | Groq Cloud API key |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model name |
| `LLM_TIMEOUT_SECONDS` | `12.0` | Per-call LLM timeout |

---

## 9. API Examples

### GET /health
```bash
curl -X GET http://localhost:8000/health
```
**Response (200 OK):**
```json
{
  "status": "ok"
}
```

### POST /optimize-energy
```bash
curl -X POST http://localhost:8000/optimize-energy \
  -H "Content-Type: application/json" \
  -d '{
    "scenario_id": "DEMO-01",
    "operator_notes": [
      "Facilities will wash the rooftop solar panels from noon until 2 PM. During cleaning, usable solar should be treated as roughly 25% of the forecast.",
      "The sports office moved next month registration deadline."
    ],
    "hours": [
      {"hour": 0, "demand_kwh": 90, "solar_kwh": 0, "tariff_bdt_per_kwh": 6},
      {"hour": 1, "demand_kwh": 85, "solar_kwh": 0, "tariff_bdt_per_kwh": 6},
      {"hour": 2, "demand_kwh": 80, "solar_kwh": 0, "tariff_bdt_per_kwh": 5},
      {"hour": 3, "demand_kwh": 80, "solar_kwh": 0, "tariff_bdt_per_kwh": 5},
      {"hour": 4, "demand_kwh": 85, "solar_kwh": 0, "tariff_bdt_per_kwh": 5},
      {"hour": 5, "demand_kwh": 95, "solar_kwh": 0, "tariff_bdt_per_kwh": 6},
      {"hour": 6, "demand_kwh": 110, "solar_kwh": 5, "tariff_bdt_per_kwh": 8},
      {"hour": 7, "demand_kwh": 130, "solar_kwh": 20, "tariff_bdt_per_kwh": 10},
      {"hour": 8, "demand_kwh": 150, "solar_kwh": 50, "tariff_bdt_per_kwh": 12},
      {"hour": 9, "demand_kwh": 165, "solar_kwh": 90, "tariff_bdt_per_kwh": 14},
      {"hour": 10, "demand_kwh": 175, "solar_kwh": 130, "tariff_bdt_per_kwh": 16},
      {"hour": 11, "demand_kwh": 180, "solar_kwh": 160, "tariff_bdt_per_kwh": 16},
      {"hour": 12, "demand_kwh": 185, "solar_kwh": 180, "tariff_bdt_per_kwh": 15},
      {"hour": 13, "demand_kwh": 180, "solar_kwh": 170, "tariff_bdt_per_kwh": 14},
      {"hour": 14, "demand_kwh": 170, "solar_kwh": 140, "tariff_bdt_per_kwh": 13},
      {"hour": 15, "demand_kwh": 165, "solar_kwh": 90, "tariff_bdt_per_kwh": 14},
      {"hour": 16, "demand_kwh": 170, "solar_kwh": 45, "tariff_bdt_per_kwh": 18},
      {"hour": 17, "demand_kwh": 185, "solar_kwh": 10, "tariff_bdt_per_kwh": 22},
      {"hour": 18, "demand_kwh": 205, "solar_kwh": 0, "tariff_bdt_per_kwh": 28},
      {"hour": 19, "demand_kwh": 215, "solar_kwh": 0, "tariff_bdt_per_kwh": 30},
      {"hour": 20, "demand_kwh": 205, "solar_kwh": 0, "tariff_bdt_per_kwh": 26},
      {"hour": 21, "demand_kwh": 175, "solar_kwh": 0, "tariff_bdt_per_kwh": 18},
      {"hour": 22, "demand_kwh": 135, "solar_kwh": 0, "tariff_bdt_per_kwh": 10},
      {"hour": 23, "demand_kwh": 105, "solar_kwh": 0, "tariff_bdt_per_kwh": 7}
    ],
    "battery": {
      "capacity_kwh": 220,
      "initial_energy_kwh": 110,
      "minimum_energy_kwh": 40,
      "max_charge_kwh_per_hour": 50,
      "max_discharge_kwh_per_hour": 50
    }
  }'
```

**Response (200 OK):**
```json
{
  "scenario_id": "DEMO-01",
  "directive_interpretation": [
    {
      "note_index": 0,
      "applies": true,
      "directive_type": "solar_reduction",
      "structured_adjustment": {
        "hours": [12, 13],
        "factor": 0.25
      },
      "explanation": "Solar availability is reduced to 25% during the panel-cleaning window."
    },
    {
      "note_index": 1,
      "applies": false,
      "directive_type": "no_op",
      "structured_adjustment": null,
      "explanation": "This note does not affect today's 24-hour energy schedule."
    }
  ],
  "hourly_plan": [
    {
      "hour": 0,
      "grid_kwh": 90.0,
      "solar_used_kwh": 0.0,
      "battery_action": "idle",
      "battery_kwh": 0.0,
      "battery_energy_after_kwh": 110.0
    },
    {
      "hour": 1,
      "grid_kwh": 45.0,
      "solar_used_kwh": 0.0,
      "battery_action": "discharge",
      "battery_kwh": 40.0,
      "battery_energy_after_kwh": 70.0
    }
  ],
  "total_grid_kwh": 2692.5,
  "total_cost_bdt": 38365.0,
  "peak_grid_kwh": 175.0,
  "plan_summary": "Optimized 24-hour schedule incorporates reduced solar availability, shifts battery energy to avoid peak tariffs, and restores end-of-day battery neutrality."
}
```

---

## 10. Public Case Testing

Run all 10 public sample cases, unit tests, and performance benchmarks with pytest:

```bash
pytest -v
```

All 10 sample cases are automatically validated for:
1. Exact directive interpretation & note mapping.
2. Hourly energy balance ($g_h + s_h + d_h = \text{demand}_h + c_h$).
3. Battery storage capacity & rate limits.
4. End-of-day battery neutrality ($E_{23} = E_0$).
5. Optimization quality matching reference cost within tolerance.

---

## 11. Docker Instructions

### Build Docker Image
```bash
docker build -t gridwise-optimizer:latest .
```

### Run Docker Container
```bash
docker run -d --name gridwise -p 8000:8000 \
  -e LLM_PROVIDER=gemini \
  -e GEMINI_API_KEY="your-api-key-here" \
  gridwise-optimizer:latest
```

### Docker Compose
```bash
docker-compose up -d --build
```

---

## 12. Solvers & External Libraries

- **HiGHS (via `scipy.optimize.linprog(method='highs')`)**: High-performance open-source linear programming solver.
- **FastAPI**: Modern asynchronous web framework.
- **Pydantic v2**: High-performance data validation.
- **HTTPX**: Connection-pooled asynchronous HTTP client.
- **NumPy**: Matrix representation and vector operations.

---

## 13. Known Limitations

- **Whole-hour resolution**: Assumes directives apply to whole hour intervals ($h \in \{0 \dots 23\}$).
- **Grid Export**: Grid feed-in / solar export is curtailed (not compensated in this challenge model).
- **Contradictory Directives**: Two conflicting solar reduction directives on the same hour will trigger a controlled failure (HTTP 500) rather than an arbitrary heuristic.

---

## 14. License & Credits

Built for the **BUP CSE Fest 2026 Hackathon**.  
Uses open-source components from the FastAPI, SciPy, HiGHS, and Pydantic communities.
