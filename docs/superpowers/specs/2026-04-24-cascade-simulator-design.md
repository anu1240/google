# Cascade Impact Simulator — Design Spec

**Date:** 2026-04-24
**Hackathon:** Hack2Skill — Smart Supply Chains
**Submission deadline:** 2026-04-27
**Team:** 4 members (ML/data, backend/APIs, frontend/viz, generalist)
**Build window:** 1–2 days + 1 day buffer

---

## 1. Problem

Modern supply chains detect transit disruptions only after delivery timelines are compromised. Existing industry tools (FourKites, project44, Blue Yonder, Everstream) predict per-shipment lateness in isolation. They do **not** simulate how a single disruption cascades through the network to affect downstream shipments, warehouses, and customer orders, and they report single-point ETAs rather than probabilistic delivery windows.

## 2. Goal

Build a demo-able system that:

1. Models a supply chain as a directed graph with stochastic transit times.
2. Simulates cascade impact of disruptions via Monte Carlo sampling.
3. Outputs probabilistic delivery windows (P10 / P50 / P90) with scenario trees.
4. Recommends alternate routes when SLA risk is elevated.
5. Accepts real-world disruption triggers from NOAA weather data (live).

## 3. Non-Goals (explicit YAGNI)

- Authentication or multi-tenant support
- Persistent database (in-memory state only; restart wipes state — acceptable for demo)
- Historical replay or model training
- ML-learned transit-time distributions (fixed log-normal)
- Reinforcement learning for rerouting (use Dijkstra)
- Multi-objective Pareto optimization
- Mobile-responsive UI
- Production security hardening

## 4. Architecture

Four components, one primary owner each:

### 4.1 Simulation Engine — ML/Data owner

- **Language:** Python 3.11+
- **Libs:** `networkx`, `numpy`, `scipy.stats`
- **Packaging:** Python library imported by the Backend API in the same process
- **Responsibilities:**
  - Sample stochastic transit times per edge
  - Run N = 500–1000 Monte Carlo trajectories per shipment
  - Apply cascade-propagation rules when disruptions are active
  - Return probabilistic ETA distributions + list of cascade-affected shipments

### 4.2 Backend API — Backend/APIs owner

- **Language:** Python 3.11+ with FastAPI + Uvicorn
- **State:** In-memory graph, shipment, and disruption stores (Python dicts)
- **Endpoints:**
  - `GET /graph` — current graph + shipment state
  - `POST /disruptions` — inject a disruption (manual or adapter-fed)
  - `DELETE /disruptions/{id}` — clear a disruption
  - `POST /simulate` — run Monte Carlo, return probabilistic ETAs
  - `POST /reroute/{shipment_id}` — compute recommended alternate path
  - `WS /live` — WebSocket stream of state changes
- **CORS:** fully open for hackathon

### 4.3 Frontend — Frontend/Viz owner

- **Stack:** React 18 + Vite + TypeScript
- **Graph library:** React Flow (default) — fallback: Cytoscape.js if React Flow physics are insufficient
- **Views:**
  - Main graph view with animated cascade ripple
  - Shipment detail panel with scenario tree
  - Disruption-inject modal (click node → severity slider)
  - Probabilistic ETA widget (histogram or violin)
  - Weather feed panel surfacing live NOAA triggers

### 4.4 Data Adapters — Generalist owner

- **Synthetic graph generator:** ~30–50 nodes across 3 continents, realistic topology (major ports + inland hubs + warehouses)
- **Synthetic shipment generator:** ~100 in-flight shipments with varying priorities and SLA deadlines
- **NOAA weather adapter:** polls NWS public API; maps severe-weather alerts to port-node disruptions
- **(Stretch) News/OSINT adapter:** RSS scrape + LLM classifier for strike/unrest signals

## 5. Data Model

```python
Node:
  id: str
  type: Literal["port", "warehouse", "hub"]
  location: { lat: float, lon: float, name: str, country: str }
  capacity: int
  current_load: int
  status: Literal["normal", "degraded", "offline"]

Edge:
  id: str
  source_node_id: str
  target_node_id: str
  mode: Literal["sea", "rail", "truck", "air"]
  base_transit_mean_hours: float
  base_transit_sigma: float      # log-normal sigma
  cost_per_unit: float
  status: Literal["normal", "degraded", "offline"]

Shipment:
  id: str
  source_node_id: str
  destination_node_id: str
  path: list[str]                 # node ids in order
  current_node_id: str
  priority: Literal["standard", "express", "critical"]
  sla_deadline: datetime
  volume: int

Disruption:
  id: str
  target_type: Literal["node", "edge"]
  target_id: str
  severity: float                 # 0.0 – 1.0
  expected_duration_mean_hours: float
  expected_duration_sigma_hours: float
  source: Literal["manual", "weather", "news"]
  created_at: datetime

ETAForecast:
  shipment_id: str
  percentiles: { p10: datetime, p50: datetime, p90: datetime }
  scenarios: list[{ label: str, probability: float, eta: datetime }]
  cascade_impact_ids: list[str]   # other shipments affected by the same root cause
```

## 6. Core Algorithms

### 6.1 Stochastic transit sampling

Each edge samples transit time from `LogNormal(mu, sigma)` where `mu = log(base_transit_mean_hours)` and `sigma = base_transit_sigma`. Sigma defaults to 0.15 for calibrated edges (reasonable logistics variance).

### 6.2 Monte Carlo ETA

For each shipment and N trajectories:

1. Starting from `current_node_id`, walk remaining `path`.
2. For each remaining edge, sample transit time from its log-normal.
3. If any active disruption targets that edge/node, multiply the sampled time by `(1 + severity * DISRUPTION_FACTOR)` where `DISRUPTION_FACTOR = 3.0` (severity 1.0 triples transit time).
4. Sum trajectory total → candidate ETA.

Aggregate N trajectories → empirical CDF → percentiles (P10 / P50 / P90).

### 6.3 Cascade propagation

When disruption `D` is injected on target `T` at time `t`:

1. Identify shipments whose remaining path contains `T`.
2. Mark them as cascade-affected.
3. Their Monte Carlo resamples now include the disruption multiplier on transit through `T`.

### 6.4 Scenario tree generation

Partition N trajectories into terciles by total ETA:

- **Optimistic:** P10 value, probability ≈ 0.33 (lowest tercile)
- **Expected:** P50 value, probability ≈ 0.34 (middle tercile)
- **Pessimistic:** P90 value, probability ≈ 0.33 (highest tercile)

MVP uses fixed terciles; post-hackathon version can use disruption-conditional scenarios.

### 6.5 Rerouting

Given a disrupted shipment:

1. Remove disrupted nodes/edges (status ≠ "normal") from graph.
2. Run Dijkstra from `current_node_id` → `destination_node_id` with edge weight `expected_transit_hours + cost_weight * cost_per_unit`, where `cost_weight = 0.1`.
3. Return alternate path with recomputed ETA.
4. UI surfaces tradeoff: hours saved vs. cost delta.

## 7. Data Flow

```
[NOAA Adapter] --poll--> [Backend API] --import--> [Sim Engine]
      |                     ^   |                        |
      v                     |   v                        v
  disruption          [WebSocket]                  Monte Carlo
      |                     |                            |
      v                     v                            v
POST /disruptions       [Frontend] <-------- probabilistic ETAs
                            |
                      user click inject
```

## 8. Testing Strategy

Minimal for 1–2 day window:

- **Simulation engine:** 3–5 pytest unit tests on transit sampling, cascade propagation, and scenario-tree bucketing.
- **Backend:** one smoke test per endpoint via FastAPI TestClient.
- **Frontend:** manual validation; no formal tests.
- **End-to-end:** scripted demo walkthrough run twice before recording.

## 9. Demo Script (submission video)

1. Open dashboard — calm graph, ~100 in-flight shipments, all green.
2. Manually inject severe disruption at Rotterdam port → cascade ripple animates across European routes; affected shipments glow red.
3. Click one affected shipment → scenario tree reveals "65% by Tue, 25% by Thu if congestion persists, 10% Fri."
4. Click "Reroute" → alternate path via Antwerp displays with new ETA and cost delta.
5. Show the live NOAA feed triggering a second disruption automatically.
6. Close with tagline: *"Weather forecasts have probabilistic storms. Supply chains deserve probabilistic deliveries."*

## 10. Stretch Goals (only if Day 2 finishes early)

- News/RSS scraper + LLM classifier → OSINT weak-signal detection
- Animated ETA distribution (recharts)
- Compound multi-disruption effects
- Explainability overlay: "why this reroute was chosen"

## 11. Open Risks

- **NOAA API rate limits** — mitigation: cache responses, fall back to canned weather event for demo recording.
- **React Flow performance on 50+ nodes with animations** — mitigation: throttle state updates, fall back to Cytoscape.js.
- **Monte Carlo latency** — N = 1000 × 100 shipments must finish in < 1 s on a laptop; if not, reduce to N = 300 or parallelize with `numpy` vectorization.
- **Integration slippage on Day 1 PM** — mitigation: agree API contract on Day 1 AM before coding; use OpenAPI schema.
