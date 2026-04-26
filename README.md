# Cascade Impact Simulator

> Probabilistic supply chain disruption forecasting with Monte Carlo scenario trees and Dijkstra rerouting.
> Hack2Skill — Smart Supply Chains — April 2026

## What it does

- Models a supply chain as a graph (ports, hubs, warehouses) with stochastic transit times
- Simulates cascade impact of disruptions via Monte Carlo
- Outputs **probabilistic delivery windows** (P10/P50/P90) with scenario trees
- Recommends alternate routes via Dijkstra on the residual graph
- Ingests live disruption triggers from NOAA weather alerts

## Quick start

### Backend
```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

### Demo
```bash
cd backend
python scripts/demo_seed.py
```

## Architecture

```
NOAA Adapter ──▶ FastAPI ◀──▶ Simulation Engine (Monte Carlo + Dijkstra)
                    ▲   │
              WebSocket │
                    │   ▼
                React Flow frontend
```

Four components:
1. **Simulation engine** (`backend/app/simulation/`) — log-normal transit sampling, Monte Carlo, cascade propagation, scenario buckets, Dijkstra rerouting
2. **FastAPI backend** (`backend/app/main.py`) — REST + WebSocket on in-memory state
3. **React frontend** (`frontend/src/`) — React Flow graph, scenario viz, ETA histogram
4. **Data adapters** (`backend/app/data/`) — synthetic generator + NOAA live feed

## Tests

```bash
cd backend
pytest -v
```

## Demo script

1. Load dashboard — calm graph, 100 in-flight shipments
2. Click Rotterdam → set severity 0.85 → Inject
3. Cascade shipments highlight in right rail
4. Click one → scenario tree: "65% Tue · 25% Thu · 10% Fri"
5. Click Recommend reroute → alternate path via Antwerp
6. Optionally: show live NOAA feed creating a second cascade automatically

## License

MIT.
