# Cascade Impact Simulator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a probabilistic supply chain disruption cascade simulator with Monte Carlo ETAs, scenario trees, and Dijkstra rerouting, deployable within 1–2 days for the Hack2Skill Smart Supply Chains hackathon (submission 2026-04-27).

**Architecture:** Monorepo with a Python backend (FastAPI + in-process simulation library using `networkx` + `numpy`) and a React Flow frontend. All state is in-memory. Edge transit times are log-normal. Disruptions inflate transit samples, cascading through the graph to all shipments traversing the disrupted node or edge. Probabilistic ETAs are emitted as P10/P50/P90 percentiles with a 3-bucket scenario tree. Alternate routes come from Dijkstra on a residual graph that excludes disrupted elements. A NOAA weather adapter creates disruptions automatically, streamed to the UI via WebSocket.

**Tech Stack:** Python 3.11 · FastAPI · uvicorn · networkx · numpy · scipy · httpx · pytest · React 18 · Vite · TypeScript · React Flow · Zustand · NOAA NWS API

---

## File Structure

**Backend (`backend/`):**
- `pyproject.toml` — project metadata and deps
- `app/__init__.py`
- `app/main.py` — FastAPI app, routes, startup/shutdown lifespan
- `app/models.py` — Pydantic models (Node, Edge, Shipment, Disruption, ETAForecast, ScenarioBucket, NodeType, EdgeMode, Status, Priority, DisruptionSource)
- `app/state.py` — in-memory `AppState` holding nodes/edges/shipments/disruptions plus an asyncio lock
- `app/simulation/__init__.py`
- `app/simulation/sampling.py` — log-normal edge transit sampling with disruption inflation
- `app/simulation/engine.py` — Monte Carlo orchestration, produces per-shipment ETA distributions
- `app/simulation/cascade.py` — identifies cascade-affected shipments for a given disruption
- `app/simulation/scenarios.py` — tercile bucketing into scenario tree
- `app/simulation/routing.py` — Dijkstra rerouting on residual graph
- `app/data/__init__.py`
- `app/data/synthetic.py` — synthetic graph and shipment generator
- `app/data/weather.py` — NOAA NWS adapter
- `app/websocket.py` — WebSocket connection manager + broadcast
- `tests/test_synthetic.py`, `test_sampling.py`, `test_engine.py`, `test_cascade.py`, `test_scenarios.py`, `test_routing.py`, `test_api.py`, `test_weather.py`

**Frontend (`frontend/`):**
- `package.json`, `vite.config.ts`, `tsconfig.json`, `index.html`
- `src/main.tsx` — entry
- `src/App.tsx` — layout (graph canvas + right-rail panels)
- `src/types.ts` — TypeScript mirrors of backend models
- `src/api/client.ts` — fetch wrapper
- `src/api/websocket.ts` — WebSocket client with reconnect
- `src/state/store.ts` — Zustand store
- `src/components/GraphView.tsx` — React Flow canvas with animated cascade
- `src/components/DisruptionModal.tsx` — click-a-node severity injector
- `src/components/ShipmentPanel.tsx` — selected shipment scenario tree + ETAs
- `src/components/ScenarioTree.tsx` — 3-bucket tree viz
- `src/components/ETAHistogram.tsx` — trajectory histogram
- `src/components/WeatherFeed.tsx` — live disruption feed
- `src/utils/format.ts` — date + duration formatting

**Top-level:**
- `README.md`, `docker-compose.yml` (optional for demo), `.gitignore`

---

## Phase A — Foundation

### Task 1: Repo scaffold

**Files:**
- Create: `.gitignore`, `backend/pyproject.toml`, `backend/app/__init__.py`, `backend/tests/__init__.py`, `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/index.html`, `frontend/src/main.tsx`, `frontend/src/App.tsx`

- [ ] **Step 1: Initialize git and write `.gitignore`**

```bash
cd A:/google
git init
```

Create `.gitignore`:

```gitignore
# Python
__pycache__/
*.pyc
.venv/
.pytest_cache/
*.egg-info/

# Node
node_modules/
dist/
.vite/

# OS/editor
.DS_Store
.idea/
.vscode/
```

- [ ] **Step 2: Create backend `pyproject.toml`**

`backend/pyproject.toml`:

```toml
[project]
name = "cascade-backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.110",
  "uvicorn[standard]>=0.29",
  "pydantic>=2.6",
  "networkx>=3.2",
  "numpy>=1.26",
  "scipy>=1.12",
  "httpx>=0.27",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
pythonpath = ["."]
```

- [ ] **Step 3: Install backend deps**

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate  # Windows Git Bash
pip install -e ".[dev]"
```

Expected: all packages install; `pytest --version` works.

- [ ] **Step 4: Create backend package files**

`backend/app/__init__.py`: empty file.
`backend/tests/__init__.py`: empty file.

- [ ] **Step 5: Scaffold frontend with Vite**

```bash
cd A:/google
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install reactflow zustand
```

- [ ] **Step 6: Verify frontend boots**

```bash
cd frontend
npm run dev
```

Expected: Vite serves at `http://localhost:5173`, default React page renders.

Ctrl+C to stop.

- [ ] **Step 7: Commit**

```bash
cd A:/google
git add .gitignore backend frontend
git commit -m "chore: scaffold monorepo with backend (FastAPI) and frontend (Vite+React)"
```

---

### Task 2: Pydantic models

**Files:**
- Create: `backend/app/models.py`
- Test: `backend/tests/test_models.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_models.py`:

```python
from datetime import datetime, timezone
from app.models import (
    Node, Edge, Shipment, Disruption, ETAForecast, ScenarioBucket,
    NodeType, EdgeMode, Status, Priority, DisruptionSource, DisruptionTarget,
)

def test_node_roundtrip():
    n = Node(
        id="port-rotterdam",
        type=NodeType.PORT,
        lat=51.95, lon=4.14, name="Rotterdam", country="NL",
        capacity=1000, current_load=300, status=Status.NORMAL,
    )
    assert n.model_dump()["id"] == "port-rotterdam"
    assert n.type == NodeType.PORT

def test_disruption_requires_valid_severity():
    import pytest
    with pytest.raises(ValueError):
        Disruption(
            id="d1", target_type=DisruptionTarget.NODE, target_id="x",
            severity=1.5, expected_duration_mean_hours=12,
            expected_duration_sigma_hours=2,
            source=DisruptionSource.MANUAL,
            created_at=datetime.now(timezone.utc),
        )

def test_eta_forecast_percentile_order():
    now = datetime.now(timezone.utc)
    f = ETAForecast(
        shipment_id="s1",
        p10=now, p50=now, p90=now,
        scenarios=[ScenarioBucket(label="opt", probability=0.33, eta=now)],
        cascade_impact_ids=["s2"],
    )
    assert f.shipment_id == "s1"
```

- [ ] **Step 2: Run test to confirm failure**

```bash
cd backend
pytest tests/test_models.py -v
```

Expected: ImportError (models don't exist yet).

- [ ] **Step 3: Implement models**

`backend/app/models.py`:

```python
from datetime import datetime
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict


class NodeType(str, Enum):
    PORT = "port"
    WAREHOUSE = "warehouse"
    HUB = "hub"


class EdgeMode(str, Enum):
    SEA = "sea"
    RAIL = "rail"
    TRUCK = "truck"
    AIR = "air"


class Status(str, Enum):
    NORMAL = "normal"
    DEGRADED = "degraded"
    OFFLINE = "offline"


class Priority(str, Enum):
    STANDARD = "standard"
    EXPRESS = "express"
    CRITICAL = "critical"


class DisruptionSource(str, Enum):
    MANUAL = "manual"
    WEATHER = "weather"
    NEWS = "news"


class DisruptionTarget(str, Enum):
    NODE = "node"
    EDGE = "edge"


class Node(BaseModel):
    id: str
    type: NodeType
    lat: float
    lon: float
    name: str
    country: str
    capacity: int
    current_load: int = 0
    status: Status = Status.NORMAL


class Edge(BaseModel):
    id: str
    source_node_id: str
    target_node_id: str
    mode: EdgeMode
    base_transit_mean_hours: float = Field(gt=0)
    base_transit_sigma: float = Field(gt=0, default=0.15)
    cost_per_unit: float = Field(ge=0)
    status: Status = Status.NORMAL


class Shipment(BaseModel):
    id: str
    source_node_id: str
    destination_node_id: str
    path: list[str]
    current_node_id: str
    priority: Priority = Priority.STANDARD
    sla_deadline: datetime
    volume: int = 1


class Disruption(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    id: str
    target_type: DisruptionTarget
    target_id: str
    severity: float = Field(ge=0.0, le=1.0)
    expected_duration_mean_hours: float = Field(gt=0)
    expected_duration_sigma_hours: float = Field(gt=0)
    source: DisruptionSource
    created_at: datetime


class ScenarioBucket(BaseModel):
    label: Literal["optimistic", "expected", "pessimistic"] | str
    probability: float
    eta: datetime


class ETAForecast(BaseModel):
    shipment_id: str
    p10: datetime
    p50: datetime
    p90: datetime
    scenarios: list[ScenarioBucket]
    cascade_impact_ids: list[str] = []
```

- [ ] **Step 4: Re-run tests**

```bash
pytest tests/test_models.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd A:/google
git add backend/app/models.py backend/tests/test_models.py
git commit -m "feat(backend): add Pydantic domain models"
```

---

### Task 3: Synthetic graph + shipment generator

**Files:**
- Create: `backend/app/data/__init__.py` (empty), `backend/app/data/synthetic.py`
- Test: `backend/tests/test_synthetic.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_synthetic.py`:

```python
import networkx as nx
from app.data.synthetic import generate_graph, generate_shipments
from app.models import NodeType, Status


def test_graph_has_expected_shape():
    nodes, edges = generate_graph(seed=42)
    assert 28 <= len(nodes) <= 40
    assert len(edges) >= len(nodes)  # reasonably connected
    types = {n.type for n in nodes}
    assert NodeType.PORT in types and NodeType.WAREHOUSE in types and NodeType.HUB in types


def test_graph_is_weakly_connected():
    nodes, edges = generate_graph(seed=42)
    g = nx.DiGraph()
    for n in nodes:
        g.add_node(n.id)
    for e in edges:
        g.add_edge(e.source_node_id, e.target_node_id)
    assert nx.is_weakly_connected(g)


def test_shipments_have_valid_paths():
    nodes, edges = generate_graph(seed=42)
    shipments = generate_shipments(nodes, edges, count=50, seed=42)
    node_ids = {n.id for n in nodes}
    edge_pairs = {(e.source_node_id, e.target_node_id) for e in edges}
    assert len(shipments) == 50
    for s in shipments:
        assert s.source_node_id in node_ids
        assert s.destination_node_id in node_ids
        assert s.current_node_id in s.path
        for a, b in zip(s.path, s.path[1:]):
            assert (a, b) in edge_pairs, f"invalid edge {a}->{b} in shipment {s.id}"
```

- [ ] **Step 2: Run test to confirm failure**

```bash
pytest tests/test_synthetic.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement generator**

`backend/app/data/synthetic.py`:

```python
from datetime import datetime, timedelta, timezone
import random
import networkx as nx
from app.models import (
    Node, Edge, Shipment, NodeType, EdgeMode, Priority, Status,
)

_PORTS = [
    ("port-shanghai", "Shanghai", "CN", 31.23, 121.47),
    ("port-singapore", "Singapore", "SG", 1.29, 103.85),
    ("port-rotterdam", "Rotterdam", "NL", 51.95, 4.14),
    ("port-antwerp", "Antwerp", "BE", 51.22, 4.40),
    ("port-la", "Los Angeles", "US", 33.74, -118.26),
    ("port-ny", "New York", "US", 40.66, -74.05),
    ("port-dubai", "Dubai", "AE", 25.26, 55.30),
    ("port-mumbai", "Mumbai", "IN", 18.95, 72.84),
    ("port-santos", "Santos", "BR", -23.96, -46.33),
    ("port-hamburg", "Hamburg", "DE", 53.54, 9.98),
]

_HUBS = [
    ("hub-frankfurt", "Frankfurt", "DE", 50.11, 8.68),
    ("hub-chicago", "Chicago", "US", 41.88, -87.63),
    ("hub-delhi", "Delhi", "IN", 28.70, 77.10),
    ("hub-beijing", "Beijing", "CN", 39.90, 116.40),
    ("hub-moscow", "Moscow", "RU", 55.75, 37.62),
    ("hub-saopaulo", "São Paulo", "BR", -23.55, -46.63),
    ("hub-johannesburg", "Johannesburg", "ZA", -26.20, 28.04),
    ("hub-atlanta", "Atlanta", "US", 33.75, -84.39),
]

_WAREHOUSES = [
    ("wh-madrid", "Madrid", "ES", 40.42, -3.70),
    ("wh-milan", "Milan", "IT", 45.46, 9.19),
    ("wh-dallas", "Dallas", "US", 32.78, -96.80),
    ("wh-toronto", "Toronto", "CA", 43.65, -79.38),
    ("wh-sydney", "Sydney", "AU", -33.87, 151.21),
    ("wh-seoul", "Seoul", "KR", 37.57, 126.98),
    ("wh-istanbul", "Istanbul", "TR", 41.01, 28.98),
    ("wh-lagos", "Lagos", "NG", 6.52, 3.38),
    ("wh-lima", "Lima", "PE", -12.05, -77.04),
    ("wh-jakarta", "Jakarta", "ID", -6.21, 106.85),
    ("wh-capetown", "Cape Town", "ZA", -33.92, 18.42),
    ("wh-vancouver", "Vancouver", "CA", 49.28, -123.12),
]


def _mk_node(tup, ntype: NodeType, capacity: int) -> Node:
    nid, name, country, lat, lon = tup
    return Node(
        id=nid, type=ntype, lat=lat, lon=lon, name=name, country=country,
        capacity=capacity, current_load=int(capacity * 0.3),
        status=Status.NORMAL,
    )


def _edge_params(mode: EdgeMode) -> tuple[float, float, float]:
    # (mean_hours, sigma, cost_per_unit)
    return {
        EdgeMode.SEA: (240.0, 0.18, 0.10),
        EdgeMode.RAIL: (48.0, 0.12, 0.20),
        EdgeMode.TRUCK: (12.0, 0.15, 0.35),
        EdgeMode.AIR: (6.0, 0.10, 1.20),
    }[mode]


def generate_graph(seed: int = 42) -> tuple[list[Node], list[Edge]]:
    rng = random.Random(seed)
    nodes: list[Node] = []
    for t in _PORTS:
        nodes.append(_mk_node(t, NodeType.PORT, 5000))
    for t in _HUBS:
        nodes.append(_mk_node(t, NodeType.HUB, 3000))
    for t in _WAREHOUSES:
        nodes.append(_mk_node(t, NodeType.WAREHOUSE, 1500))

    ports = [n for n in nodes if n.type == NodeType.PORT]
    hubs = [n for n in nodes if n.type == NodeType.HUB]
    whs = [n for n in nodes if n.type == NodeType.WAREHOUSE]

    edges: list[Edge] = []

    def add_edge(src: Node, dst: Node, mode: EdgeMode) -> None:
        mean, sigma, cost = _edge_params(mode)
        mean *= 0.8 + rng.random() * 0.4  # jitter
        edges.append(Edge(
            id=f"{src.id}->{dst.id}:{mode.value}",
            source_node_id=src.id, target_node_id=dst.id,
            mode=mode, base_transit_mean_hours=mean,
            base_transit_sigma=sigma, cost_per_unit=cost,
        ))

    # Sea lanes between ports (fully connect to ensure connectivity)
    for i, a in enumerate(ports):
        for b in ports[i + 1:]:
            add_edge(a, b, EdgeMode.SEA)
            add_edge(b, a, EdgeMode.SEA)

    # Each port connects to 1-2 nearest hubs via rail
    for p in ports:
        sorted_hubs = sorted(hubs, key=lambda h: (h.lat - p.lat) ** 2 + (h.lon - p.lon) ** 2)
        for h in sorted_hubs[: rng.randint(1, 2)]:
            add_edge(p, h, EdgeMode.RAIL)
            add_edge(h, p, EdgeMode.RAIL)

    # Each hub connects to 2-3 nearest warehouses via truck
    for h in hubs:
        sorted_whs = sorted(whs, key=lambda w: (w.lat - h.lat) ** 2 + (w.lon - h.lon) ** 2)
        for w in sorted_whs[: rng.randint(2, 3)]:
            add_edge(h, w, EdgeMode.TRUCK)
            add_edge(w, h, EdgeMode.TRUCK)

    # A handful of air routes (hub-hub, cross-continent)
    for _ in range(6):
        a, b = rng.sample(hubs, 2)
        add_edge(a, b, EdgeMode.AIR)
        add_edge(b, a, EdgeMode.AIR)

    return nodes, edges


def generate_shipments(
    nodes: list[Node], edges: list[Edge], count: int = 100, seed: int = 42
) -> list[Shipment]:
    rng = random.Random(seed)
    g = nx.DiGraph()
    for n in nodes:
        g.add_node(n.id)
    for e in edges:
        g.add_edge(e.source_node_id, e.target_node_id, weight=e.base_transit_mean_hours)

    ports = [n for n in nodes if n.type == NodeType.PORT]
    whs = [n for n in nodes if n.type == NodeType.WAREHOUSE]

    shipments: list[Shipment] = []
    attempts = 0
    while len(shipments) < count and attempts < count * 5:
        attempts += 1
        src = rng.choice(ports)
        dst = rng.choice(whs)
        try:
            path = nx.shortest_path(g, src.id, dst.id, weight="weight")
        except nx.NetworkXNoPath:
            continue
        if len(path) < 2:
            continue
        current_idx = rng.randint(0, max(0, len(path) - 2))
        priority = rng.choices(
            [Priority.STANDARD, Priority.EXPRESS, Priority.CRITICAL],
            weights=[0.6, 0.3, 0.1],
        )[0]
        deadline = datetime.now(timezone.utc) + timedelta(
            hours=rng.randint(48, 336)
        )
        shipments.append(Shipment(
            id=f"SHIP-{len(shipments):04d}",
            source_node_id=src.id,
            destination_node_id=dst.id,
            path=path,
            current_node_id=path[current_idx],
            priority=priority,
            sla_deadline=deadline,
            volume=rng.randint(1, 40),
        ))
    return shipments
```

- [ ] **Step 4: Re-run tests**

```bash
pytest tests/test_synthetic.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/data/__init__.py backend/app/data/synthetic.py backend/tests/test_synthetic.py
git commit -m "feat(backend): synthetic graph and shipment generator"
```

---

### Task 4: In-memory state store

**Files:**
- Create: `backend/app/state.py`
- Test: `backend/tests/test_state.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_state.py`:

```python
import pytest
from datetime import datetime, timezone
from app.state import AppState
from app.models import (
    Disruption, DisruptionTarget, DisruptionSource,
)


@pytest.mark.asyncio
async def test_state_loads_synthetic_data():
    s = AppState()
    await s.load_synthetic()
    async with s.lock:
        assert len(s.nodes) > 25
        assert len(s.edges) > 25
        assert len(s.shipments) >= 50


@pytest.mark.asyncio
async def test_add_and_remove_disruption():
    s = AppState()
    await s.load_synthetic()
    d = Disruption(
        id="d-test", target_type=DisruptionTarget.NODE,
        target_id=next(iter(s.nodes)),
        severity=0.5, expected_duration_mean_hours=12,
        expected_duration_sigma_hours=3,
        source=DisruptionSource.MANUAL,
        created_at=datetime.now(timezone.utc),
    )
    await s.add_disruption(d)
    async with s.lock:
        assert "d-test" in s.disruptions
    await s.remove_disruption("d-test")
    async with s.lock:
        assert "d-test" not in s.disruptions
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_state.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement state**

`backend/app/state.py`:

```python
import asyncio
from app.models import Node, Edge, Shipment, Disruption
from app.data.synthetic import generate_graph, generate_shipments


class AppState:
    def __init__(self) -> None:
        self.nodes: dict[str, Node] = {}
        self.edges: dict[str, Edge] = {}
        self.shipments: dict[str, Shipment] = {}
        self.disruptions: dict[str, Disruption] = {}
        self.lock = asyncio.Lock()

    async def load_synthetic(self, seed: int = 42) -> None:
        nodes, edges = generate_graph(seed=seed)
        shipments = generate_shipments(nodes, edges, count=100, seed=seed)
        async with self.lock:
            self.nodes = {n.id: n for n in nodes}
            self.edges = {e.id: e for e in edges}
            self.shipments = {s.id: s for s in shipments}
            self.disruptions = {}

    async def add_disruption(self, d: Disruption) -> None:
        async with self.lock:
            self.disruptions[d.id] = d

    async def remove_disruption(self, disruption_id: str) -> None:
        async with self.lock:
            self.disruptions.pop(disruption_id, None)


state = AppState()
```

- [ ] **Step 4: Re-run tests**

```bash
pytest tests/test_state.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/state.py backend/tests/test_state.py
git commit -m "feat(backend): in-memory AppState with async lock"
```

---

## Phase B — Simulation Engine

### Task 5: Transit-time sampling

**Files:**
- Create: `backend/app/simulation/__init__.py` (empty), `backend/app/simulation/sampling.py`
- Test: `backend/tests/test_sampling.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_sampling.py`:

```python
import numpy as np
from datetime import datetime, timezone
from app.models import (
    Edge, EdgeMode, Disruption, DisruptionTarget, DisruptionSource,
)
from app.simulation.sampling import sample_edge_transit, DISRUPTION_FACTOR


def _edge() -> Edge:
    return Edge(
        id="e1", source_node_id="a", target_node_id="b",
        mode=EdgeMode.SEA, base_transit_mean_hours=100.0,
        base_transit_sigma=0.12, cost_per_unit=0.1,
    )


def _disruption(target_id: str, severity: float) -> Disruption:
    return Disruption(
        id="d1", target_type=DisruptionTarget.EDGE,
        target_id=target_id, severity=severity,
        expected_duration_mean_hours=24,
        expected_duration_sigma_hours=6,
        source=DisruptionSource.MANUAL,
        created_at=datetime.now(timezone.utc),
    )


def test_baseline_mean_within_tolerance():
    rng = np.random.default_rng(0)
    e = _edge()
    samples = np.array([sample_edge_transit(e, [], rng) for _ in range(5000)])
    assert 90 < samples.mean() < 110


def test_disruption_inflates_mean():
    rng = np.random.default_rng(0)
    e = _edge()
    d = _disruption(target_id="e1", severity=1.0)
    samples = np.array([sample_edge_transit(e, [d], rng) for _ in range(5000)])
    expected = 100.0 * (1 + DISRUPTION_FACTOR)
    assert expected * 0.85 < samples.mean() < expected * 1.15


def test_disruption_on_unrelated_edge_has_no_effect():
    rng = np.random.default_rng(0)
    e = _edge()
    d = _disruption(target_id="other-edge", severity=1.0)
    samples = np.array([sample_edge_transit(e, [d], rng) for _ in range(5000)])
    assert 90 < samples.mean() < 110
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_sampling.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement sampling**

`backend/app/simulation/sampling.py`:

```python
from __future__ import annotations
import math
import numpy as np
from app.models import Edge, Disruption, DisruptionTarget

DISRUPTION_FACTOR: float = 3.0


def _applies_to_edge(d: Disruption, edge: Edge) -> bool:
    if d.target_type == DisruptionTarget.EDGE and d.target_id == edge.id:
        return True
    if d.target_type == DisruptionTarget.NODE and d.target_id in (
        edge.source_node_id, edge.target_node_id,
    ):
        return True
    return False


def sample_edge_transit(
    edge: Edge, disruptions: list[Disruption], rng: np.random.Generator
) -> float:
    mu = math.log(edge.base_transit_mean_hours) - 0.5 * edge.base_transit_sigma ** 2
    sample = float(rng.lognormal(mean=mu, sigma=edge.base_transit_sigma))
    multiplier = 1.0
    for d in disruptions:
        if _applies_to_edge(d, edge):
            multiplier *= 1.0 + d.severity * DISRUPTION_FACTOR
    return sample * multiplier
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_sampling.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/simulation/__init__.py backend/app/simulation/sampling.py backend/tests/test_sampling.py
git commit -m "feat(sim): log-normal transit sampling with disruption inflation"
```

---

### Task 6: Monte Carlo engine

**Files:**
- Create: `backend/app/simulation/engine.py`
- Test: `backend/tests/test_engine.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_engine.py`:

```python
from datetime import datetime, timezone
from app.data.synthetic import generate_graph, generate_shipments
from app.simulation.engine import simulate_shipment


def test_simulate_returns_n_trajectories():
    nodes, edges = generate_graph(seed=42)
    shipments = generate_shipments(nodes, edges, count=20, seed=42)
    edges_by_pair = {(e.source_node_id, e.target_node_id): e for e in edges}
    shipment = next(s for s in shipments if len(s.path) >= 3)

    now = datetime.now(timezone.utc)
    result = simulate_shipment(
        shipment=shipment, edges_by_pair=edges_by_pair,
        disruptions=[], n=300, now=now, seed=0,
    )
    assert len(result.trajectories_hours) == 300
    assert result.p10 <= result.p50 <= result.p90
    assert result.p10 >= now


def test_disruption_shifts_distribution_later():
    from app.models import Disruption, DisruptionTarget, DisruptionSource
    nodes, edges = generate_graph(seed=42)
    shipments = generate_shipments(nodes, edges, count=20, seed=42)
    edges_by_pair = {(e.source_node_id, e.target_node_id): e for e in edges}
    shipment = next(s for s in shipments if len(s.path) >= 3)
    first_remaining_node = shipment.path[shipment.path.index(shipment.current_node_id) + 1]

    d = Disruption(
        id="d1", target_type=DisruptionTarget.NODE,
        target_id=first_remaining_node, severity=1.0,
        expected_duration_mean_hours=24,
        expected_duration_sigma_hours=6,
        source=DisruptionSource.MANUAL,
        created_at=datetime.now(timezone.utc),
    )
    now = datetime.now(timezone.utc)
    baseline = simulate_shipment(
        shipment=shipment, edges_by_pair=edges_by_pair,
        disruptions=[], n=500, now=now, seed=0,
    )
    disrupted = simulate_shipment(
        shipment=shipment, edges_by_pair=edges_by_pair,
        disruptions=[d], n=500, now=now, seed=0,
    )
    assert disrupted.p50 > baseline.p50
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_engine.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement engine**

`backend/app/simulation/engine.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
import numpy as np
from app.models import Shipment, Edge, Disruption
from app.simulation.sampling import sample_edge_transit


@dataclass
class SimulationResult:
    shipment_id: str
    trajectories_hours: list[float]
    p10: datetime
    p50: datetime
    p90: datetime


def simulate_shipment(
    shipment: Shipment,
    edges_by_pair: dict[tuple[str, str], Edge],
    disruptions: list[Disruption],
    n: int = 500,
    now: datetime | None = None,
    seed: int | None = None,
) -> SimulationResult:
    now = now or datetime.utcnow()
    rng = np.random.default_rng(seed)

    try:
        start_idx = shipment.path.index(shipment.current_node_id)
    except ValueError:
        start_idx = 0
    remaining = shipment.path[start_idx:]
    if len(remaining) < 2:
        return SimulationResult(
            shipment_id=shipment.id, trajectories_hours=[0.0] * n,
            p10=now, p50=now, p90=now,
        )

    trajectories: list[float] = []
    for _ in range(n):
        total = 0.0
        for a, b in zip(remaining, remaining[1:]):
            edge = edges_by_pair.get((a, b))
            if edge is None:
                total += 24.0  # fallback when path is stale
                continue
            total += sample_edge_transit(edge, disruptions, rng)
        trajectories.append(total)

    arr = np.asarray(trajectories)
    p10, p50, p90 = np.percentile(arr, [10, 50, 90])
    return SimulationResult(
        shipment_id=shipment.id,
        trajectories_hours=trajectories,
        p10=now + timedelta(hours=float(p10)),
        p50=now + timedelta(hours=float(p50)),
        p90=now + timedelta(hours=float(p90)),
    )
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_engine.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/simulation/engine.py backend/tests/test_engine.py
git commit -m "feat(sim): Monte Carlo simulate_shipment with percentile ETAs"
```

---

### Task 7: Cascade identification

**Files:**
- Create: `backend/app/simulation/cascade.py`
- Test: `backend/tests/test_cascade.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_cascade.py`:

```python
from datetime import datetime, timezone
from app.models import (
    Shipment, Disruption, DisruptionTarget, DisruptionSource, Priority,
)
from app.simulation.cascade import cascade_affected_ids


def _ship(id_: str, path: list[str], current: str) -> Shipment:
    return Shipment(
        id=id_, source_node_id=path[0], destination_node_id=path[-1],
        path=path, current_node_id=current, priority=Priority.STANDARD,
        sla_deadline=datetime.now(timezone.utc), volume=1,
    )


def _node_disruption(node_id: str) -> Disruption:
    return Disruption(
        id="d1", target_type=DisruptionTarget.NODE, target_id=node_id,
        severity=0.7, expected_duration_mean_hours=12,
        expected_duration_sigma_hours=4,
        source=DisruptionSource.MANUAL,
        created_at=datetime.now(timezone.utc),
    )


def test_cascade_affects_downstream_shipments():
    ships = [
        _ship("s1", ["A", "B", "C", "D"], "A"),
        _ship("s2", ["X", "B", "Y"], "X"),
        _ship("s3", ["A", "Z"], "A"),  # no B in path
        _ship("s4", ["A", "B", "C"], "C"),  # already past B
    ]
    d = _node_disruption("B")
    affected = cascade_affected_ids(ships, d)
    assert affected == {"s1", "s2"}


def test_edge_disruption_matches_pair():
    from app.models import Disruption, DisruptionTarget
    ships = [_ship("s1", ["A", "B", "C"], "A")]
    d = Disruption(
        id="d1", target_type=DisruptionTarget.EDGE, target_id="A->B:sea",
        severity=0.5, expected_duration_mean_hours=12,
        expected_duration_sigma_hours=3,
        source=DisruptionSource.MANUAL,
        created_at=datetime.now(timezone.utc),
    )
    # Edge ids use pattern src->dst:mode. Here we do prefix-based matching.
    affected = cascade_affected_ids(ships, d)
    assert "s1" in affected
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_cascade.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement cascade**

`backend/app/simulation/cascade.py`:

```python
from __future__ import annotations
from app.models import Shipment, Disruption, DisruptionTarget


def cascade_affected_ids(
    shipments: list[Shipment], disruption: Disruption
) -> set[str]:
    affected: set[str] = set()
    for s in shipments:
        try:
            idx = s.path.index(s.current_node_id)
        except ValueError:
            idx = 0
        remaining = s.path[idx:]
        if disruption.target_type == DisruptionTarget.NODE:
            if disruption.target_id in remaining[1:]:
                affected.add(s.id)
        else:  # EDGE
            # Edge id pattern: src->dst:mode. Match by src-dst pair prefix.
            prefix = disruption.target_id.split(":", 1)[0]
            for a, b in zip(remaining, remaining[1:]):
                if f"{a}->{b}" == prefix:
                    affected.add(s.id)
                    break
    return affected
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_cascade.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/simulation/cascade.py backend/tests/test_cascade.py
git commit -m "feat(sim): cascade-affected shipment identification"
```

---

### Task 8: Scenario tree

**Files:**
- Create: `backend/app/simulation/scenarios.py`
- Test: `backend/tests/test_scenarios.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_scenarios.py`:

```python
from datetime import datetime, timezone
from app.simulation.scenarios import build_scenarios


def test_three_buckets_cover_full_probability():
    trajectories = list(range(300))  # 0..299 hours
    now = datetime.now(timezone.utc)
    buckets = build_scenarios(trajectories, now)
    assert len(buckets) == 3
    labels = [b.label for b in buckets]
    assert labels == ["optimistic", "expected", "pessimistic"]
    total = sum(b.probability for b in buckets)
    assert 0.99 < total < 1.01


def test_etas_are_monotonically_later():
    trajectories = [5, 10, 15, 20, 25, 30, 35, 40, 45]
    now = datetime.now(timezone.utc)
    buckets = build_scenarios(trajectories, now)
    assert buckets[0].eta < buckets[1].eta < buckets[2].eta
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_scenarios.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement scenarios**

`backend/app/simulation/scenarios.py`:

```python
from __future__ import annotations
from datetime import datetime, timedelta
import numpy as np
from app.models import ScenarioBucket


def build_scenarios(
    trajectories_hours: list[float], now: datetime
) -> list[ScenarioBucket]:
    if not trajectories_hours:
        return []
    arr = np.asarray(trajectories_hours)
    p10, p50, p90 = np.percentile(arr, [10, 50, 90])
    t33, t66 = np.percentile(arr, [33.33, 66.67])
    n = len(arr)
    opt_count = int((arr <= t33).sum())
    mid_count = int(((arr > t33) & (arr <= t66)).sum())
    pes_count = n - opt_count - mid_count
    return [
        ScenarioBucket(
            label="optimistic", probability=opt_count / n,
            eta=now + timedelta(hours=float(p10)),
        ),
        ScenarioBucket(
            label="expected", probability=mid_count / n,
            eta=now + timedelta(hours=float(p50)),
        ),
        ScenarioBucket(
            label="pessimistic", probability=pes_count / n,
            eta=now + timedelta(hours=float(p90)),
        ),
    ]
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_scenarios.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/simulation/scenarios.py backend/tests/test_scenarios.py
git commit -m "feat(sim): scenario tree tercile bucketing"
```

---

### Task 9: Dijkstra rerouting

**Files:**
- Create: `backend/app/simulation/routing.py`
- Test: `backend/tests/test_routing.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_routing.py`:

```python
from datetime import datetime, timezone
from app.models import (
    Node, Edge, EdgeMode, Shipment, Disruption, DisruptionTarget,
    DisruptionSource, Priority, NodeType,
)
from app.simulation.routing import reroute


def _n(id_: str) -> Node:
    return Node(
        id=id_, type=NodeType.HUB, lat=0, lon=0, name=id_, country="XX",
        capacity=100, current_load=0,
    )


def _e(src: str, dst: str, mean: float) -> Edge:
    return Edge(
        id=f"{src}->{dst}:rail",
        source_node_id=src, target_node_id=dst, mode=EdgeMode.RAIL,
        base_transit_mean_hours=mean, base_transit_sigma=0.1, cost_per_unit=0.2,
    )


def test_reroute_avoids_disrupted_node():
    nodes = [_n(i) for i in ["A", "B", "C", "D", "E"]]
    edges = [
        _e("A", "B", 10), _e("B", "D", 10),   # direct path via B
        _e("A", "C", 20), _e("C", "D", 20),   # longer path via C
        _e("D", "E", 5),
    ]
    shipment = Shipment(
        id="s1", source_node_id="A", destination_node_id="E",
        path=["A", "B", "D", "E"], current_node_id="A",
        priority=Priority.STANDARD,
        sla_deadline=datetime.now(timezone.utc), volume=1,
    )
    d = Disruption(
        id="d1", target_type=DisruptionTarget.NODE, target_id="B",
        severity=1.0, expected_duration_mean_hours=24,
        expected_duration_sigma_hours=6,
        source=DisruptionSource.MANUAL,
        created_at=datetime.now(timezone.utc),
    )
    result = reroute(shipment, nodes, edges, [d])
    assert result is not None
    assert "B" not in result.new_path
    assert result.new_path[0] == "A"
    assert result.new_path[-1] == "E"


def test_reroute_returns_none_if_no_alternate():
    nodes = [_n(i) for i in ["A", "B"]]
    edges = [_e("A", "B", 10)]
    shipment = Shipment(
        id="s1", source_node_id="A", destination_node_id="B",
        path=["A", "B"], current_node_id="A", priority=Priority.STANDARD,
        sla_deadline=datetime.now(timezone.utc), volume=1,
    )
    d = Disruption(
        id="d1", target_type=DisruptionTarget.NODE, target_id="B",
        severity=1.0, expected_duration_mean_hours=24,
        expected_duration_sigma_hours=6,
        source=DisruptionSource.MANUAL,
        created_at=datetime.now(timezone.utc),
    )
    assert reroute(shipment, nodes, edges, [d]) is None
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_routing.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement rerouting**

`backend/app/simulation/routing.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
import networkx as nx
from app.models import (
    Node, Edge, Shipment, Disruption, DisruptionTarget,
)

COST_WEIGHT: float = 0.1


@dataclass
class RerouteResult:
    shipment_id: str
    new_path: list[str]
    expected_transit_hours: float
    expected_cost: float


def reroute(
    shipment: Shipment,
    nodes: list[Node],
    edges: list[Edge],
    disruptions: list[Disruption],
) -> RerouteResult | None:
    disrupted_nodes = {
        d.target_id for d in disruptions if d.target_type == DisruptionTarget.NODE
    }
    disrupted_edges = {
        d.target_id.split(":", 1)[0] for d in disruptions
        if d.target_type == DisruptionTarget.EDGE
    }

    g = nx.DiGraph()
    for n in nodes:
        if n.id in disrupted_nodes:
            continue
        g.add_node(n.id)
    for e in edges:
        if e.source_node_id in disrupted_nodes or e.target_node_id in disrupted_nodes:
            continue
        if f"{e.source_node_id}->{e.target_node_id}" in disrupted_edges:
            continue
        g.add_edge(
            e.source_node_id, e.target_node_id,
            transit=e.base_transit_mean_hours,
            cost=e.cost_per_unit,
            weight=e.base_transit_mean_hours + COST_WEIGHT * e.cost_per_unit * 1000,
        )

    if shipment.current_node_id not in g or shipment.destination_node_id not in g:
        return None

    try:
        path = nx.shortest_path(
            g, shipment.current_node_id, shipment.destination_node_id, weight="weight",
        )
    except nx.NetworkXNoPath:
        return None

    transit = sum(g[a][b]["transit"] for a, b in zip(path, path[1:]))
    cost = sum(g[a][b]["cost"] for a, b in zip(path, path[1:]))
    return RerouteResult(
        shipment_id=shipment.id, new_path=path,
        expected_transit_hours=float(transit), expected_cost=float(cost),
    )
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_routing.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/simulation/routing.py backend/tests/test_routing.py
git commit -m "feat(sim): Dijkstra rerouting on residual graph"
```

---

## Phase C — Backend API

### Task 10: FastAPI skeleton + GET /graph

**Files:**
- Create: `backend/app/main.py`, `backend/app/websocket.py`
- Test: `backend/tests/test_api.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_api.py`:

```python
import os
os.environ.setdefault("CASCADE_DISABLE_WEATHER", "1")

import pytest
from fastapi.testclient import TestClient
from app.main import app, get_state


@pytest.fixture
def client():
    # TestClient triggers FastAPI lifespan, which calls load_synthetic().
    with TestClient(app) as c:
        yield c


def test_graph_endpoint_returns_nodes_edges_shipments(client):
    r = client.get("/graph")
    assert r.status_code == 200
    data = r.json()
    assert "nodes" in data and "edges" in data and "shipments" in data
    assert len(data["nodes"]) > 25


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_api.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement WebSocket manager**

`backend/app/websocket.py`:

```python
from __future__ import annotations
import asyncio
import json
from typing import Any
from fastapi import WebSocket


class WSManager:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, event: str, payload: dict[str, Any]) -> None:
        message = json.dumps({"event": event, "payload": payload}, default=str)
        async with self._lock:
            targets = list(self._clients)
        for ws in targets:
            try:
                await ws.send_text(message)
            except Exception:
                await self.disconnect(ws)


ws_manager = WSManager()
```

- [ ] **Step 4: Implement FastAPI app**

`backend/app/main.py`:

```python
from __future__ import annotations
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.state import state as _state, AppState


def get_state() -> AppState:
    return _state


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not _state.nodes:
        await _state.load_synthetic()
    yield


app = FastAPI(title="Cascade Simulator", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/graph")
async def get_graph() -> dict:
    async with _state.lock:
        return {
            "nodes": [n.model_dump() for n in _state.nodes.values()],
            "edges": [e.model_dump() for e in _state.edges.values()],
            "shipments": [s.model_dump() for s in _state.shipments.values()],
            "disruptions": [d.model_dump() for d in _state.disruptions.values()],
        }
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_api.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/main.py backend/app/websocket.py backend/tests/test_api.py
git commit -m "feat(api): FastAPI skeleton with /health and /graph"
```

---

### Task 11: Disruption endpoints

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_api.py`

- [ ] **Step 1: Add failing test**

Append to `backend/tests/test_api.py`:

```python
def test_post_and_delete_disruption(client):
    state = get_state()
    node_id = next(iter(state.nodes))
    body = {
        "target_type": "node",
        "target_id": node_id,
        "severity": 0.6,
        "expected_duration_mean_hours": 12,
        "expected_duration_sigma_hours": 3,
        "source": "manual",
    }
    r = client.post("/disruptions", json=body)
    assert r.status_code == 200
    d = r.json()
    assert d["target_id"] == node_id
    disruption_id = d["id"]

    r2 = client.get("/graph")
    assert any(x["id"] == disruption_id for x in r2.json()["disruptions"])

    r3 = client.delete(f"/disruptions/{disruption_id}")
    assert r3.status_code == 200

    r4 = client.get("/graph")
    assert not any(x["id"] == disruption_id for x in r4.json()["disruptions"])
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_api.py::test_post_and_delete_disruption -v
```

Expected: 404 or similar.

- [ ] **Step 3: Add disruption endpoints**

Append to `backend/app/main.py`:

```python
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException
from pydantic import BaseModel
from app.models import Disruption, DisruptionTarget, DisruptionSource
from app.websocket import ws_manager


class DisruptionCreate(BaseModel):
    target_type: DisruptionTarget
    target_id: str
    severity: float
    expected_duration_mean_hours: float
    expected_duration_sigma_hours: float
    source: DisruptionSource = DisruptionSource.MANUAL


@app.post("/disruptions")
async def post_disruption(body: DisruptionCreate) -> dict:
    if body.target_type == DisruptionTarget.NODE and body.target_id not in _state.nodes:
        raise HTTPException(404, f"node {body.target_id} not found")
    if body.target_type == DisruptionTarget.EDGE:
        prefix = body.target_id.split(":", 1)[0]
        if not any(f"{e.source_node_id}->{e.target_node_id}" == prefix for e in _state.edges.values()):
            raise HTTPException(404, f"edge {body.target_id} not found")
    d = Disruption(
        id=f"d-{uuid.uuid4().hex[:8]}",
        target_type=body.target_type,
        target_id=body.target_id,
        severity=body.severity,
        expected_duration_mean_hours=body.expected_duration_mean_hours,
        expected_duration_sigma_hours=body.expected_duration_sigma_hours,
        source=body.source,
        created_at=datetime.now(timezone.utc),
    )
    await _state.add_disruption(d)
    await ws_manager.broadcast("disruption.added", d.model_dump(mode="json"))
    return d.model_dump(mode="json")


@app.delete("/disruptions/{disruption_id}")
async def delete_disruption(disruption_id: str) -> dict:
    async with _state.lock:
        if disruption_id not in _state.disruptions:
            raise HTTPException(404, "disruption not found")
    await _state.remove_disruption(disruption_id)
    await ws_manager.broadcast("disruption.removed", {"id": disruption_id})
    return {"id": disruption_id, "status": "removed"}
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_api.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/test_api.py
git commit -m "feat(api): POST/DELETE /disruptions with validation"
```

---

### Task 12: POST /simulate

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_api.py`

- [ ] **Step 1: Add failing test**

Append to `backend/tests/test_api.py`:

```python
def test_simulate_returns_forecasts(client):
    r = client.post("/simulate", json={"n": 200})
    assert r.status_code == 200
    data = r.json()
    assert "forecasts" in data
    assert len(data["forecasts"]) > 0
    f = data["forecasts"][0]
    assert "shipment_id" in f and "p10" in f and "p50" in f and "p90" in f
    assert "scenarios" in f and len(f["scenarios"]) == 3


def test_simulate_with_shipment_filter(client):
    state = get_state()
    ids = list(state.shipments)[:3]
    r = client.post("/simulate", json={"n": 100, "shipment_ids": ids})
    assert r.status_code == 200
    data = r.json()
    assert {f["shipment_id"] for f in data["forecasts"]} == set(ids)
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_api.py::test_simulate_returns_forecasts -v
```

Expected: 404.

- [ ] **Step 3: Implement /simulate**

Append to `backend/app/main.py`:

```python
from datetime import datetime as _dt, timezone as _tz
from app.models import ETAForecast
from app.simulation.engine import simulate_shipment
from app.simulation.scenarios import build_scenarios
from app.simulation.cascade import cascade_affected_ids


class SimulateRequest(BaseModel):
    n: int = 500
    shipment_ids: list[str] | None = None


@app.post("/simulate")
async def simulate(body: SimulateRequest) -> dict:
    async with _state.lock:
        shipments = list(_state.shipments.values())
        disruptions = list(_state.disruptions.values())
        edges_by_pair = {
            (e.source_node_id, e.target_node_id): e
            for e in _state.edges.values()
        }
    if body.shipment_ids:
        wanted = set(body.shipment_ids)
        shipments = [s for s in shipments if s.id in wanted]

    cascade_ids: set[str] = set()
    for d in disruptions:
        cascade_ids |= cascade_affected_ids(shipments, d)

    now = _dt.now(_tz.utc)
    forecasts = []
    for s in shipments:
        res = simulate_shipment(
            shipment=s, edges_by_pair=edges_by_pair,
            disruptions=disruptions, n=body.n, now=now,
        )
        buckets = build_scenarios(res.trajectories_hours, now)
        forecast = ETAForecast(
            shipment_id=s.id, p10=res.p10, p50=res.p50, p90=res.p90,
            scenarios=buckets,
            cascade_impact_ids=sorted(cascade_ids - {s.id}) if s.id in cascade_ids else [],
        )
        forecasts.append(forecast.model_dump(mode="json"))
    return {"forecasts": forecasts, "cascade_affected": sorted(cascade_ids)}
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_api.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/test_api.py
git commit -m "feat(api): POST /simulate with cascade-aware ETA forecasts"
```

---

### Task 13: POST /reroute/{shipment_id}

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_api.py`

- [ ] **Step 1: Add failing test**

Append to `backend/tests/test_api.py`:

```python
def test_reroute_endpoint(client):
    state = get_state()
    shipment_id = next(iter(state.shipments))
    r = client.post(f"/reroute/{shipment_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["shipment_id"] == shipment_id
    assert "new_path" in data
    assert "expected_transit_hours" in data
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_api.py::test_reroute_endpoint -v
```

Expected: 404.

- [ ] **Step 3: Implement /reroute**

Append to `backend/app/main.py`:

```python
from app.simulation.routing import reroute as do_reroute


@app.post("/reroute/{shipment_id}")
async def reroute_shipment(shipment_id: str) -> dict:
    async with _state.lock:
        shipment = _state.shipments.get(shipment_id)
        if not shipment:
            raise HTTPException(404, "shipment not found")
        nodes = list(_state.nodes.values())
        edges = list(_state.edges.values())
        disruptions = list(_state.disruptions.values())
    result = do_reroute(shipment, nodes, edges, disruptions)
    if result is None:
        raise HTTPException(409, "no viable alternate route")
    return {
        "shipment_id": result.shipment_id,
        "new_path": result.new_path,
        "expected_transit_hours": result.expected_transit_hours,
        "expected_cost": result.expected_cost,
        "original_path": shipment.path,
    }
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_api.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/test_api.py
git commit -m "feat(api): POST /reroute/{shipment_id} with Dijkstra fallback"
```

---

### Task 14: WebSocket /live endpoint

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_api.py`

- [ ] **Step 1: Add WebSocket test**

Append to `backend/tests/test_api.py`:

```python
def test_websocket_receives_disruption_broadcast(client):
    state = get_state()
    node_id = next(iter(state.nodes))
    with client.websocket_connect("/live") as ws:
        r = client.post("/disruptions", json={
            "target_type": "node", "target_id": node_id,
            "severity": 0.4, "expected_duration_mean_hours": 6,
            "expected_duration_sigma_hours": 2, "source": "manual",
        })
        assert r.status_code == 200
        msg = ws.receive_json()
        assert msg["event"] == "disruption.added"
        assert msg["payload"]["target_id"] == node_id
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_api.py::test_websocket_receives_disruption_broadcast -v
```

Expected: WebSocket connection error.

- [ ] **Step 3: Implement /live**

Append to `backend/app/main.py`:

```python
from fastapi import WebSocket, WebSocketDisconnect


@app.websocket("/live")
async def websocket_live(ws: WebSocket) -> None:
    await ws_manager.connect(ws)
    try:
        while True:
            await ws.receive_text()  # ignore client messages (keep-alive)
    except WebSocketDisconnect:
        await ws_manager.disconnect(ws)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_api.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/test_api.py
git commit -m "feat(api): WebSocket /live broadcasts disruption events"
```

---

## Phase D — External Data

### Task 15: NOAA weather adapter

**Files:**
- Create: `backend/app/data/weather.py`
- Test: `backend/tests/test_weather.py`
- Modify: `backend/app/main.py` (startup hook)

- [ ] **Step 1: Write the failing test**

`backend/tests/test_weather.py`:

```python
import pytest
from app.data.weather import parse_alerts_to_disruptions
from app.models import Node, NodeType


def _fake_alert(severity: str, lat: float, lon: float, event: str) -> dict:
    return {
        "properties": {
            "severity": severity,
            "event": event,
            "headline": f"{event} near lat {lat} lon {lon}",
            "ends": None,
            "expires": "2026-04-25T12:00:00Z",
            "id": f"urn:alert:{event}:{lat}:{lon}",
        },
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
    }


def test_parse_alerts_creates_disruptions_for_nearby_ports():
    ports = [
        Node(id="port-la", type=NodeType.PORT, lat=33.74, lon=-118.26,
             name="Los Angeles", country="US", capacity=5000),
        Node(id="port-ny", type=NodeType.PORT, lat=40.66, lon=-74.05,
             name="New York", country="US", capacity=5000),
    ]
    alerts = [_fake_alert("Severe", 33.80, -118.30, "Storm Warning")]
    disruptions = parse_alerts_to_disruptions(alerts, ports)
    assert len(disruptions) == 1
    assert disruptions[0].target_id == "port-la"
    assert disruptions[0].severity >= 0.5


def test_parse_ignores_minor_alerts():
    ports = [Node(id="port-la", type=NodeType.PORT, lat=33.74, lon=-118.26,
                  name="LA", country="US", capacity=5000)]
    alerts = [_fake_alert("Minor", 33.80, -118.30, "Advisory")]
    disruptions = parse_alerts_to_disruptions(alerts, ports)
    assert disruptions == []
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_weather.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement weather adapter**

`backend/app/data/weather.py`:

```python
from __future__ import annotations
import asyncio
import math
import uuid
from datetime import datetime, timezone
import httpx
from app.models import (
    Node, NodeType, Disruption, DisruptionTarget, DisruptionSource,
)

NOAA_ALERTS_URL = "https://api.weather.gov/alerts/active"
POLL_INTERVAL_SECONDS = 120
SEVERITY_MAP = {
    "Extreme": 1.0, "Severe": 0.7, "Moderate": 0.4,
    "Minor": 0.0, "Unknown": 0.0,
}
MAX_DISTANCE_KM = 300


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(a))


def _alert_point(alert: dict) -> tuple[float, float] | None:
    geom = alert.get("geometry")
    if not geom:
        return None
    if geom.get("type") == "Point":
        lon, lat = geom["coordinates"]
        return (lat, lon)
    if geom.get("type") == "Polygon":
        coords = geom["coordinates"][0]
        lat = sum(c[1] for c in coords) / len(coords)
        lon = sum(c[0] for c in coords) / len(coords)
        return (lat, lon)
    return None


def parse_alerts_to_disruptions(
    alerts: list[dict], nodes: list[Node]
) -> list[Disruption]:
    ports = [n for n in nodes if n.type == NodeType.PORT]
    out: list[Disruption] = []
    for alert in alerts:
        props = alert.get("properties", {})
        severity = SEVERITY_MAP.get(props.get("severity", "Unknown"), 0.0)
        if severity <= 0.0:
            continue
        point = _alert_point(alert)
        if not point:
            continue
        alat, alon = point
        nearest: Node | None = None
        nearest_d = float("inf")
        for p in ports:
            d = _haversine_km(alat, alon, p.lat, p.lon)
            if d < nearest_d:
                nearest_d = d
                nearest = p
        if nearest is None or nearest_d > MAX_DISTANCE_KM:
            continue
        out.append(Disruption(
            id=f"d-wx-{uuid.uuid4().hex[:8]}",
            target_type=DisruptionTarget.NODE,
            target_id=nearest.id,
            severity=severity,
            expected_duration_mean_hours=12.0,
            expected_duration_sigma_hours=4.0,
            source=DisruptionSource.WEATHER,
            created_at=datetime.now(timezone.utc),
        ))
    return out


async def fetch_alerts(client: httpx.AsyncClient) -> list[dict]:
    r = await client.get(
        NOAA_ALERTS_URL,
        headers={"User-Agent": "cascade-simulator (hackathon demo)"},
        timeout=20.0,
    )
    r.raise_for_status()
    return r.json().get("features", [])


async def weather_loop(state, ws_manager) -> None:
    async with httpx.AsyncClient() as client:
        while True:
            try:
                alerts = await fetch_alerts(client)
                async with state.lock:
                    nodes = list(state.nodes.values())
                    existing_wx = {
                        d.id for d in state.disruptions.values()
                        if d.source == DisruptionSource.WEATHER
                    }
                disruptions = parse_alerts_to_disruptions(alerts, nodes)
                for d in disruptions:
                    if d.id in existing_wx:
                        continue
                    await state.add_disruption(d)
                    await ws_manager.broadcast(
                        "disruption.added", d.model_dump(mode="json")
                    )
            except Exception as exc:
                print(f"[weather] poll failed: {exc}")
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
```

- [ ] **Step 4: Wire into app lifespan**

Modify `backend/app/main.py` — replace the existing `lifespan` (set `CASCADE_DISABLE_WEATHER=1` to skip the live poll in tests):

```python
import asyncio
import os
from app.data.weather import weather_loop
from app.websocket import ws_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not _state.nodes:
        await _state.load_synthetic()
    task = None
    if os.environ.get("CASCADE_DISABLE_WEATHER") != "1":
        task = asyncio.create_task(weather_loop(_state, ws_manager))
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
```

- [ ] **Step 5: Run tests**

```bash
pytest -v
```

Expected: all tests pass (weather unit tests use the parse function directly; full poll loop is not exercised in tests).

- [ ] **Step 6: Commit**

```bash
git add backend/app/data/weather.py backend/app/main.py backend/tests/test_weather.py
git commit -m "feat(data): NOAA weather adapter creating port-node disruptions"
```

---

## Phase E — Frontend

### Task 16: Frontend types + API client

**Files:**
- Create: `frontend/src/types.ts`, `frontend/src/api/client.ts`

- [ ] **Step 1: Create shared types**

`frontend/src/types.ts`:

```typescript
export type NodeType = "port" | "warehouse" | "hub";
export type EdgeMode = "sea" | "rail" | "truck" | "air";
export type Status = "normal" | "degraded" | "offline";
export type Priority = "standard" | "express" | "critical";
export type DisruptionSource = "manual" | "weather" | "news";
export type DisruptionTarget = "node" | "edge";

export interface Node {
  id: string;
  type: NodeType;
  lat: number;
  lon: number;
  name: string;
  country: string;
  capacity: number;
  current_load: number;
  status: Status;
}

export interface Edge {
  id: string;
  source_node_id: string;
  target_node_id: string;
  mode: EdgeMode;
  base_transit_mean_hours: number;
  base_transit_sigma: number;
  cost_per_unit: number;
  status: Status;
}

export interface Shipment {
  id: string;
  source_node_id: string;
  destination_node_id: string;
  path: string[];
  current_node_id: string;
  priority: Priority;
  sla_deadline: string;
  volume: number;
}

export interface Disruption {
  id: string;
  target_type: DisruptionTarget;
  target_id: string;
  severity: number;
  expected_duration_mean_hours: number;
  expected_duration_sigma_hours: number;
  source: DisruptionSource;
  created_at: string;
}

export interface ScenarioBucket {
  label: "optimistic" | "expected" | "pessimistic" | string;
  probability: number;
  eta: string;
}

export interface ETAForecast {
  shipment_id: string;
  p10: string;
  p50: string;
  p90: string;
  scenarios: ScenarioBucket[];
  cascade_impact_ids: string[];
}

export interface GraphSnapshot {
  nodes: Node[];
  edges: Edge[];
  shipments: Shipment[];
  disruptions: Disruption[];
}

export interface RerouteResult {
  shipment_id: string;
  new_path: string[];
  expected_transit_hours: number;
  expected_cost: number;
  original_path: string[];
}
```

- [ ] **Step 2: Create API client**

`frontend/src/api/client.ts`:

```typescript
import type {
  GraphSnapshot, Disruption, DisruptionTarget, DisruptionSource,
  ETAForecast, RerouteResult,
} from "../types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

async function request<T>(
  path: string, init?: RequestInit
): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json() as Promise<T>;
}

export const api = {
  getGraph: () => request<GraphSnapshot>("/graph"),
  postDisruption: (body: {
    target_type: DisruptionTarget;
    target_id: string;
    severity: number;
    expected_duration_mean_hours: number;
    expected_duration_sigma_hours: number;
    source?: DisruptionSource;
  }) => request<Disruption>("/disruptions", {
    method: "POST", body: JSON.stringify(body),
  }),
  deleteDisruption: (id: string) => request<{ id: string; status: string }>(
    `/disruptions/${id}`, { method: "DELETE" }
  ),
  simulate: (body: { n?: number; shipment_ids?: string[] }) =>
    request<{ forecasts: ETAForecast[]; cascade_affected: string[] }>(
      "/simulate", { method: "POST", body: JSON.stringify(body) }
    ),
  reroute: (shipmentId: string) => request<RerouteResult>(
    `/reroute/${shipmentId}`, { method: "POST" }
  ),
};
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types.ts frontend/src/api/client.ts
git commit -m "feat(frontend): type mirrors + REST API client"
```

---

### Task 17: WebSocket client + Zustand store

**Files:**
- Create: `frontend/src/api/websocket.ts`, `frontend/src/state/store.ts`

- [ ] **Step 1: Create WebSocket client**

`frontend/src/api/websocket.ts`:

```typescript
const WS_BASE = (import.meta.env.VITE_WS_BASE as string | undefined) ??
  "ws://localhost:8000";

export type LiveEvent =
  | { event: "disruption.added"; payload: any }
  | { event: "disruption.removed"; payload: { id: string } };

export function connectLive(
  onEvent: (ev: LiveEvent) => void
): () => void {
  let ws: WebSocket | null = null;
  let closed = false;

  const open = () => {
    ws = new WebSocket(`${WS_BASE}/live`);
    ws.onmessage = (e) => {
      try { onEvent(JSON.parse(e.data) as LiveEvent); } catch {}
    };
    ws.onclose = () => {
      if (!closed) setTimeout(open, 2000);
    };
  };
  open();

  return () => {
    closed = true;
    ws?.close();
  };
}
```

- [ ] **Step 2: Create Zustand store**

`frontend/src/state/store.ts`:

```typescript
import { create } from "zustand";
import type {
  Node, Edge, Shipment, Disruption, ETAForecast,
} from "../types";
import { api } from "../api/client";

interface AppStore {
  nodes: Node[];
  edges: Edge[];
  shipments: Shipment[];
  disruptions: Disruption[];
  forecasts: Record<string, ETAForecast>;
  cascadeAffected: Set<string>;
  selectedShipmentId: string | null;
  loading: boolean;

  loadGraph: () => Promise<void>;
  runSimulation: () => Promise<void>;
  addDisruption: (d: Disruption) => void;
  removeDisruption: (id: string) => void;
  selectShipment: (id: string | null) => void;
}

export const useStore = create<AppStore>((set, get) => ({
  nodes: [],
  edges: [],
  shipments: [],
  disruptions: [],
  forecasts: {},
  cascadeAffected: new Set(),
  selectedShipmentId: null,
  loading: false,

  loadGraph: async () => {
    set({ loading: true });
    const g = await api.getGraph();
    set({
      nodes: g.nodes, edges: g.edges,
      shipments: g.shipments, disruptions: g.disruptions,
      loading: false,
    });
  },

  runSimulation: async () => {
    const { forecasts: prev } = get();
    const r = await api.simulate({ n: 500 });
    const next: Record<string, ETAForecast> = { ...prev };
    r.forecasts.forEach((f) => { next[f.shipment_id] = f; });
    set({ forecasts: next, cascadeAffected: new Set(r.cascade_affected) });
  },

  addDisruption: (d) => set((s) => ({
    disruptions: [...s.disruptions.filter((x) => x.id !== d.id), d],
  })),

  removeDisruption: (id) => set((s) => ({
    disruptions: s.disruptions.filter((x) => x.id !== id),
  })),

  selectShipment: (id) => set({ selectedShipmentId: id }),
}));
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/websocket.ts frontend/src/state/store.ts
git commit -m "feat(frontend): WebSocket client and Zustand store"
```

---

### Task 18: GraphView with React Flow

**Files:**
- Create: `frontend/src/utils/format.ts`, `frontend/src/components/GraphView.tsx`
- Modify: `frontend/src/App.tsx`, `frontend/src/main.tsx`

- [ ] **Step 1: Create formatting utils**

`frontend/src/utils/format.ts`:

```typescript
export function formatHours(hours: number): string {
  if (hours < 1) return `${Math.round(hours * 60)}m`;
  if (hours < 48) return `${hours.toFixed(1)}h`;
  return `${(hours / 24).toFixed(1)}d`;
}

export function formatETA(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

export function projectLatLon(
  lat: number, lon: number, width = 1400, height = 700
): { x: number; y: number } {
  const x = ((lon + 180) / 360) * width;
  const y = ((90 - lat) / 180) * height;
  return { x, y };
}
```

- [ ] **Step 2: Create GraphView**

`frontend/src/components/GraphView.tsx`:

```typescript
import { useMemo } from "react";
import ReactFlow, {
  Background, Controls, Node as RFNode, Edge as RFEdge,
  MarkerType,
} from "reactflow";
import "reactflow/dist/style.css";
import { useStore } from "../state/store";
import { projectLatLon } from "../utils/format";

export function GraphView() {
  const {
    nodes, edges, disruptions, cascadeAffected, shipments,
    selectShipment,
  } = useStore();

  const disruptedNodeIds = useMemo(
    () => new Set(
      disruptions.filter((d) => d.target_type === "node").map((d) => d.target_id)
    ),
    [disruptions]
  );

  const shipmentsOnEdge = useMemo(() => {
    const m = new Map<string, string[]>();
    shipments.forEach((s) => {
      for (let i = 0; i < s.path.length - 1; i++) {
        const k = `${s.path[i]}->${s.path[i + 1]}`;
        const arr = m.get(k) ?? [];
        arr.push(s.id);
        m.set(k, arr);
      }
    });
    return m;
  }, [shipments]);

  const cascadePathNodes = useMemo(() => {
    const ids = new Set<string>();
    shipments.forEach((s) => {
      if (cascadeAffected.has(s.id)) {
        const idx = s.path.indexOf(s.current_node_id);
        s.path.slice(idx >= 0 ? idx : 0).forEach((n) => ids.add(n));
      }
    });
    return ids;
  }, [shipments, cascadeAffected]);

  const rfNodes: RFNode[] = nodes.map((n) => {
    const { x, y } = projectLatLon(n.lat, n.lon);
    const disrupted = disruptedNodeIds.has(n.id);
    const onCascade = cascadePathNodes.has(n.id);
    const color = disrupted ? "#dc2626" : onCascade ? "#f97316" :
      n.type === "port" ? "#2563eb" :
      n.type === "hub" ? "#059669" : "#9333ea";
    return {
      id: n.id, position: { x, y },
      data: { label: `${n.type === "port" ? "🚢" : n.type === "hub" ? "🏭" : "📦"} ${n.name}` },
      style: {
        background: color, color: "white", borderRadius: 6,
        padding: "4px 8px", fontSize: 11, border: "none",
      },
    };
  });

  const rfEdges: RFEdge[] = edges.map((e) => {
    const key = `${e.source_node_id}->${e.target_node_id}`;
    const hasShipments = (shipmentsOnEdge.get(key)?.length ?? 0) > 0;
    const onCascade = cascadePathNodes.has(e.source_node_id) && cascadePathNodes.has(e.target_node_id);
    return {
      id: e.id, source: e.source_node_id, target: e.target_node_id,
      animated: hasShipments,
      style: {
        stroke: onCascade ? "#f97316" : "#94a3b8",
        strokeWidth: onCascade ? 2 : 1,
        opacity: hasShipments ? 0.9 : 0.35,
      },
      markerEnd: { type: MarkerType.ArrowClosed },
    };
  });

  return (
    <div style={{ height: "100%", width: "100%" }}>
      <ReactFlow
        nodes={rfNodes}
        edges={rfEdges}
        onNodeClick={(_e, n) => selectShipment(null)}
        fitView
      >
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  );
}
```

- [ ] **Step 3: Wire up App + main**

`frontend/src/App.tsx`:

```typescript
import { useEffect } from "react";
import { GraphView } from "./components/GraphView";
import { useStore } from "./state/store";
import { connectLive } from "./api/websocket";

export default function App() {
  const { loadGraph, runSimulation, addDisruption, removeDisruption } = useStore();

  useEffect(() => {
    (async () => {
      await loadGraph();
      await runSimulation();
    })();
    const close = connectLive((ev) => {
      if (ev.event === "disruption.added") {
        addDisruption(ev.payload);
        runSimulation();
      } else if (ev.event === "disruption.removed") {
        removeDisruption(ev.payload.id);
        runSimulation();
      }
    });
    return close;
  }, [loadGraph, runSimulation, addDisruption, removeDisruption]);

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 360px", height: "100vh" }}>
      <GraphView />
      <aside style={{ borderLeft: "1px solid #e5e7eb", padding: 12, overflow: "auto" }}>
        <h2 style={{ margin: 0, fontSize: 16 }}>Cascade Simulator</h2>
        <p style={{ fontSize: 12, color: "#64748b" }}>
          Click a node to inject disruption. Scenario trees appear when a shipment is selected.
        </p>
      </aside>
    </div>
  );
}
```

`frontend/src/main.tsx`:

```typescript
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
```

- [ ] **Step 4: Start backend + frontend, verify visually**

Terminal 1:
```bash
cd A:/google/backend
source .venv/Scripts/activate
uvicorn app.main:app --reload --port 8000
```

Terminal 2:
```bash
cd A:/google/frontend
npm run dev
```

Open `http://localhost:5173`. Expected: world-map-projected node layout, edges between them, node colors by type.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/utils/format.ts frontend/src/components/GraphView.tsx frontend/src/App.tsx frontend/src/main.tsx
git commit -m "feat(frontend): GraphView with React Flow + cascade coloring"
```

---

### Task 19: Disruption injection modal

**Files:**
- Create: `frontend/src/components/DisruptionModal.tsx`
- Modify: `frontend/src/components/GraphView.tsx`, `frontend/src/App.tsx`

- [ ] **Step 1: Create modal component**

`frontend/src/components/DisruptionModal.tsx`:

```typescript
import { useState } from "react";
import { api } from "../api/client";

export function DisruptionModal({
  nodeId, nodeName, onClose,
}: {
  nodeId: string | null;
  nodeName: string;
  onClose: () => void;
}) {
  const [severity, setSeverity] = useState(0.6);
  const [duration, setDuration] = useState(12);
  const [submitting, setSubmitting] = useState(false);

  if (!nodeId) return null;

  const submit = async () => {
    setSubmitting(true);
    try {
      await api.postDisruption({
        target_type: "node", target_id: nodeId,
        severity, expected_duration_mean_hours: duration,
        expected_duration_sigma_hours: duration * 0.25,
        source: "manual",
      });
      onClose();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)",
      display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100,
    }} onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        style={{ background: "white", padding: 20, borderRadius: 8, minWidth: 320 }}
      >
        <h3 style={{ marginTop: 0 }}>Inject disruption at {nodeName}</h3>

        <label style={{ display: "block", marginTop: 12 }}>
          Severity: {severity.toFixed(2)}
          <input type="range" min={0} max={1} step={0.05}
            value={severity} onChange={(e) => setSeverity(+e.target.value)}
            style={{ display: "block", width: "100%" }} />
        </label>

        <label style={{ display: "block", marginTop: 12 }}>
          Expected duration (hours): {duration}
          <input type="range" min={1} max={72} step={1}
            value={duration} onChange={(e) => setDuration(+e.target.value)}
            style={{ display: "block", width: "100%" }} />
        </label>

        <div style={{ marginTop: 16, display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button onClick={onClose}>Cancel</button>
          <button onClick={submit} disabled={submitting}
            style={{ background: "#dc2626", color: "white", border: "none", padding: "6px 12px", borderRadius: 4 }}>
            {submitting ? "Injecting..." : "Inject"}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Wire into App**

Modify `frontend/src/App.tsx` — add modal state and pass node click handler:

```typescript
import { useEffect, useState } from "react";
import { GraphView } from "./components/GraphView";
import { DisruptionModal } from "./components/DisruptionModal";
import { useStore } from "./state/store";
import { connectLive } from "./api/websocket";

export default function App() {
  const { loadGraph, runSimulation, addDisruption, removeDisruption, nodes } = useStore();
  const [injectNodeId, setInjectNodeId] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      await loadGraph();
      await runSimulation();
    })();
    const close = connectLive((ev) => {
      if (ev.event === "disruption.added") {
        addDisruption(ev.payload);
        runSimulation();
      } else if (ev.event === "disruption.removed") {
        removeDisruption(ev.payload.id);
        runSimulation();
      }
    });
    return close;
  }, [loadGraph, runSimulation, addDisruption, removeDisruption]);

  const injectNode = nodes.find((n) => n.id === injectNodeId);

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 360px", height: "100vh" }}>
      <GraphView onNodeClick={setInjectNodeId} />
      <aside style={{ borderLeft: "1px solid #e5e7eb", padding: 12, overflow: "auto" }}>
        <h2 style={{ margin: 0, fontSize: 16 }}>Cascade Simulator</h2>
        <p style={{ fontSize: 12, color: "#64748b" }}>
          Click a node to inject disruption.
        </p>
      </aside>
      <DisruptionModal
        nodeId={injectNodeId}
        nodeName={injectNode?.name ?? ""}
        onClose={() => setInjectNodeId(null)}
      />
    </div>
  );
}
```

Modify `frontend/src/components/GraphView.tsx` — accept `onNodeClick` prop:

Change the component signature to `export function GraphView({ onNodeClick }: { onNodeClick: (id: string) => void })` and replace the `onNodeClick` handler inside `<ReactFlow>` with:

```typescript
onNodeClick={(_e, n) => onNodeClick(n.id)}
```

- [ ] **Step 3: Verify in browser**

Restart `npm run dev` if needed. Click a node → modal opens → set severity → Inject. Expected: modal closes, disruption appears in graph (red node), cascade recolors downstream.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/DisruptionModal.tsx frontend/src/App.tsx frontend/src/components/GraphView.tsx
git commit -m "feat(frontend): DisruptionModal for click-to-inject"
```

---

### Task 20: ShipmentPanel with ScenarioTree + ETA histogram

**Files:**
- Create: `frontend/src/components/ScenarioTree.tsx`, `frontend/src/components/ETAHistogram.tsx`, `frontend/src/components/ShipmentPanel.tsx`
- Modify: `frontend/src/App.tsx`, `frontend/src/components/GraphView.tsx`

- [ ] **Step 1: ScenarioTree**

`frontend/src/components/ScenarioTree.tsx`:

```typescript
import type { ScenarioBucket } from "../types";
import { formatETA } from "../utils/format";

const COLORS = {
  optimistic: "#16a34a",
  expected: "#2563eb",
  pessimistic: "#dc2626",
} as const;

export function ScenarioTree({ scenarios }: { scenarios: ScenarioBucket[] }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {scenarios.map((b) => {
        const color = (COLORS as any)[b.label] ?? "#64748b";
        const pct = Math.round(b.probability * 100);
        return (
          <div key={b.label} style={{
            display: "grid", gridTemplateColumns: "90px 1fr 140px",
            alignItems: "center", gap: 8, fontSize: 12,
          }}>
            <div style={{ color, fontWeight: 600, textTransform: "capitalize" }}>
              {b.label}
            </div>
            <div style={{ background: "#f1f5f9", height: 10, borderRadius: 5 }}>
              <div style={{
                background: color, height: "100%", width: `${pct}%`,
                borderRadius: 5, transition: "width 200ms",
              }} />
            </div>
            <div style={{ textAlign: "right", color: "#475569" }}>
              {pct}% · {formatETA(b.eta)}
            </div>
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: ETAHistogram**

`frontend/src/components/ETAHistogram.tsx`:

```typescript
import { useMemo } from "react";
import type { ETAForecast } from "../types";

export function ETAHistogram({ forecast }: { forecast: ETAForecast }) {
  const { bars, labels } = useMemo(() => {
    const pts = [forecast.p10, forecast.p50, forecast.p90]
      .map((t) => new Date(t).getTime());
    const min = pts[0], max = pts[2];
    const buckets = 12;
    const width = (max - min) / buckets;
    const bars = new Array(buckets).fill(0);
    forecast.scenarios.forEach((s) => {
      const t = new Date(s.eta).getTime();
      const idx = Math.min(
        buckets - 1, Math.max(0, Math.floor((t - min) / width))
      );
      bars[idx] += s.probability;
    });
    const labels = [new Date(min), new Date(max)]
      .map((d) => d.toLocaleDateString(undefined, { month: "short", day: "numeric" }));
    return { bars, labels };
  }, [forecast]);

  const maxBar = Math.max(...bars, 0.01);

  return (
    <div>
      <div style={{ display: "flex", alignItems: "flex-end", gap: 2, height: 60 }}>
        {bars.map((v, i) => (
          <div key={i} style={{
            flex: 1, background: "#3b82f6",
            height: `${(v / maxBar) * 100}%`, borderRadius: "2px 2px 0 0",
            minHeight: 2, opacity: 0.8,
          }} />
        ))}
      </div>
      <div style={{
        display: "flex", justifyContent: "space-between",
        fontSize: 10, color: "#64748b", marginTop: 4,
      }}>
        <span>{labels[0]}</span><span>{labels[1]}</span>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: ShipmentPanel**

`frontend/src/components/ShipmentPanel.tsx`:

```typescript
import { useState } from "react";
import type { Shipment } from "../types";
import { useStore } from "../state/store";
import { ScenarioTree } from "./ScenarioTree";
import { ETAHistogram } from "./ETAHistogram";
import { api } from "../api/client";
import { formatETA, formatHours } from "../utils/format";

export function ShipmentPanel({ shipment }: { shipment: Shipment }) {
  const forecast = useStore((s) => s.forecasts[shipment.id]);
  const cascadeAffected = useStore((s) => s.cascadeAffected.has(shipment.id));
  const nodes = useStore((s) => s.nodes);
  const nameFor = (id: string) =>
    nodes.find((n) => n.id === id)?.name ?? id;

  const [reroute, setReroute] = useState<any | null>(null);
  const [rerouting, setRerouting] = useState(false);

  const doReroute = async () => {
    setRerouting(true);
    try {
      const r = await api.reroute(shipment.id);
      setReroute(r);
    } catch (e: any) {
      alert(e.message);
    } finally {
      setRerouting(false);
    }
  };

  return (
    <div style={{ padding: 12, borderTop: "1px solid #e5e7eb" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <h3 style={{ margin: 0, fontSize: 14 }}>{shipment.id}</h3>
        {cascadeAffected && (
          <span style={{
            background: "#fee2e2", color: "#991b1b", fontSize: 10,
            padding: "2px 6px", borderRadius: 10,
          }}>CASCADE AFFECTED</span>
        )}
      </div>
      <div style={{ fontSize: 11, color: "#64748b", marginTop: 4 }}>
        {nameFor(shipment.source_node_id)} → {nameFor(shipment.destination_node_id)} · {shipment.priority} · SLA {formatETA(shipment.sla_deadline)}
      </div>

      {forecast && (
        <div style={{ marginTop: 12 }}>
          <div style={{ fontSize: 11, color: "#475569", marginBottom: 6 }}>
            Delivery windows
          </div>
          <ScenarioTree scenarios={forecast.scenarios} />
          <div style={{ marginTop: 10 }}>
            <ETAHistogram forecast={forecast} />
          </div>
          <div style={{ fontSize: 10, color: "#64748b", marginTop: 6 }}>
            P10 {formatETA(forecast.p10)} · P50 {formatETA(forecast.p50)} · P90 {formatETA(forecast.p90)}
          </div>
        </div>
      )}

      <button onClick={doReroute} disabled={rerouting}
        style={{
          marginTop: 12, padding: "6px 12px", border: "none",
          background: "#2563eb", color: "white", borderRadius: 4,
        }}>
        {rerouting ? "Rerouting..." : "Recommend reroute"}
      </button>

      {reroute && (
        <div style={{ marginTop: 10, fontSize: 11, background: "#f0f9ff", padding: 8, borderRadius: 4 }}>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>Recommended path</div>
          <div>{reroute.new_path.map(nameFor).join(" → ")}</div>
          <div style={{ marginTop: 4 }}>
            Transit: {formatHours(reroute.expected_transit_hours)} · Cost: {reroute.expected_cost.toFixed(2)}
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Wire selection into GraphView and App**

Modify `frontend/src/components/GraphView.tsx` — accept an `onShipmentSelect` prop OR make the right panel show the currently-selected shipment. For a cleaner UX, add a shipment list in the aside. Modify `frontend/src/App.tsx`:

```typescript
import { useEffect, useState } from "react";
import { GraphView } from "./components/GraphView";
import { DisruptionModal } from "./components/DisruptionModal";
import { ShipmentPanel } from "./components/ShipmentPanel";
import { useStore } from "./state/store";
import { connectLive } from "./api/websocket";

export default function App() {
  const {
    loadGraph, runSimulation, addDisruption, removeDisruption,
    nodes, shipments, cascadeAffected, selectedShipmentId, selectShipment,
  } = useStore();
  const [injectNodeId, setInjectNodeId] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      await loadGraph();
      await runSimulation();
    })();
    const close = connectLive((ev) => {
      if (ev.event === "disruption.added") {
        addDisruption(ev.payload);
        runSimulation();
      } else if (ev.event === "disruption.removed") {
        removeDisruption(ev.payload.id);
        runSimulation();
      }
    });
    return close;
  }, [loadGraph, runSimulation, addDisruption, removeDisruption]);

  const injectNode = nodes.find((n) => n.id === injectNodeId);
  const selected = shipments.find((s) => s.id === selectedShipmentId);
  const cascadeShipments = shipments.filter((s) => cascadeAffected.has(s.id));

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 380px", height: "100vh" }}>
      <GraphView onNodeClick={setInjectNodeId} />
      <aside style={{
        borderLeft: "1px solid #e5e7eb", overflow: "auto",
        display: "flex", flexDirection: "column",
      }}>
        <div style={{ padding: 12 }}>
          <h2 style={{ margin: 0, fontSize: 16 }}>Cascade Simulator</h2>
          <p style={{ fontSize: 11, color: "#64748b" }}>
            Click a node on the map to inject a disruption. Select a cascade-affected shipment to see its probabilistic ETA.
          </p>
        </div>

        {cascadeShipments.length > 0 && (
          <div style={{ padding: 12, borderTop: "1px solid #e5e7eb" }}>
            <div style={{ fontSize: 11, color: "#991b1b", fontWeight: 600, marginBottom: 6 }}>
              {cascadeShipments.length} shipments affected
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 4, maxHeight: 140, overflow: "auto" }}>
              {cascadeShipments.map((s) => (
                <button key={s.id} onClick={() => selectShipment(s.id)}
                  style={{
                    textAlign: "left", padding: "4px 8px",
                    border: "1px solid #e5e7eb", borderRadius: 4,
                    background: selectedShipmentId === s.id ? "#eff6ff" : "white",
                    fontSize: 11, cursor: "pointer",
                  }}>
                  {s.id} · {s.priority}
                </button>
              ))}
            </div>
          </div>
        )}

        {selected && <ShipmentPanel shipment={selected} />}
      </aside>
      <DisruptionModal
        nodeId={injectNodeId}
        nodeName={injectNode?.name ?? ""}
        onClose={() => setInjectNodeId(null)}
      />
    </div>
  );
}
```

- [ ] **Step 5: Verify end-to-end**

Run backend + frontend. Inject a disruption at a well-connected port. Expected: cascade shipments appear in the list; clicking one reveals its scenario tree and histogram; "Recommend reroute" returns an alternate path.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ScenarioTree.tsx frontend/src/components/ETAHistogram.tsx frontend/src/components/ShipmentPanel.tsx frontend/src/App.tsx
git commit -m "feat(frontend): ShipmentPanel with scenario tree, histogram, reroute"
```

---

### Task 21: WeatherFeed live panel

**Files:**
- Create: `frontend/src/components/WeatherFeed.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create WeatherFeed**

`frontend/src/components/WeatherFeed.tsx`:

```typescript
import { useStore } from "../state/store";
import { api } from "../api/client";
import { formatETA } from "../utils/format";

export function WeatherFeed() {
  const { disruptions, nodes } = useStore();
  const weatherDisruptions = disruptions.filter((d) => d.source === "weather");

  const nameFor = (id: string) =>
    nodes.find((n) => n.id === id)?.name ?? id;

  return (
    <div style={{ padding: 12, borderTop: "1px solid #e5e7eb" }}>
      <div style={{ fontSize: 11, color: "#0f766e", fontWeight: 600, marginBottom: 6 }}>
        Live weather triggers ({weatherDisruptions.length})
      </div>
      {weatherDisruptions.length === 0 ? (
        <div style={{ fontSize: 11, color: "#94a3b8" }}>No active weather disruptions.</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {weatherDisruptions.map((d) => (
            <div key={d.id} style={{
              padding: "6px 8px", border: "1px solid #e5e7eb",
              borderRadius: 4, fontSize: 11,
              display: "flex", justifyContent: "space-between", alignItems: "center",
            }}>
              <div>
                <div style={{ fontWeight: 600 }}>{nameFor(d.target_id)}</div>
                <div style={{ color: "#64748b" }}>
                  severity {d.severity.toFixed(2)} · started {formatETA(d.created_at)}
                </div>
              </div>
              <button onClick={() => api.deleteDisruption(d.id)}
                style={{
                  padding: "2px 8px", fontSize: 10,
                  background: "white", border: "1px solid #cbd5e1", borderRadius: 3,
                }}>
                Clear
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Wire into App**

Add `<WeatherFeed />` above the cascade shipments list in `frontend/src/App.tsx`. Import it at the top.

- [ ] **Step 3: Manually verify**

Start the backend (with the NOAA loop running). If the US has active alerts, severe ones should appear in the panel within ~2 minutes. For demo: ensure internet access or include a canned fallback.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/WeatherFeed.tsx frontend/src/App.tsx
git commit -m "feat(frontend): live weather trigger panel"
```

---

## Phase F — Integration & Demo

### Task 22: End-to-end smoke test

**Files:**
- Create: `backend/tests/test_e2e.py`

- [ ] **Step 1: Write integration test**

`backend/tests/test_e2e.py`:

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app, get_state


@pytest.fixture
def client():
    import os
    os.environ.setdefault("CASCADE_DISABLE_WEATHER", "1")
    with TestClient(app) as c:
        yield c


def test_full_disruption_cascade_reroute_flow(client):
    state = get_state()

    # 1. Graph loaded
    g = client.get("/graph").json()
    assert len(g["shipments"]) > 0

    # 2. Baseline simulation
    sim1 = client.post("/simulate", json={"n": 200}).json()
    baseline_cascade = len(sim1["cascade_affected"])
    assert baseline_cascade == 0

    # 3. Inject disruption at a high-traffic port
    port_ids = [n["id"] for n in g["nodes"] if n["type"] == "port"]
    # Pick the port that appears in the most shipment paths
    traffic = {pid: 0 for pid in port_ids}
    for s in g["shipments"]:
        for n in s["path"]:
            if n in traffic:
                traffic[n] += 1
    busiest = max(traffic, key=traffic.get)
    d = client.post("/disruptions", json={
        "target_type": "node", "target_id": busiest,
        "severity": 0.9, "expected_duration_mean_hours": 24,
        "expected_duration_sigma_hours": 6, "source": "manual",
    }).json()

    # 4. Cascade now has affected shipments
    sim2 = client.post("/simulate", json={"n": 200}).json()
    assert len(sim2["cascade_affected"]) > 0

    # 5. Reroute one affected shipment
    affected_id = sim2["cascade_affected"][0]
    r = client.post(f"/reroute/{affected_id}")
    # May be 200 or 409 depending on topology; either is valid
    assert r.status_code in (200, 409)

    # 6. Clean up
    assert client.delete(f"/disruptions/{d['id']}").status_code == 200
```

- [ ] **Step 2: Run it**

```bash
cd backend
pytest tests/test_e2e.py -v
```

Expected: 1 passed.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_e2e.py
git commit -m "test: end-to-end cascade and reroute smoke test"
```

---

### Task 23: Demo seed script

**Files:**
- Create: `backend/scripts/demo_seed.py`

- [ ] **Step 1: Create script**

`backend/scripts/demo_seed.py`:

```python
"""Run against a live backend to inject a demo cascade.

Usage:
    python scripts/demo_seed.py [--host http://localhost:8000]
"""
import argparse
import httpx


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="http://localhost:8000")
    args = p.parse_args()

    g = httpx.get(f"{args.host}/graph").json()
    ports = [n for n in g["nodes"] if n["type"] == "port"]

    # Pick Rotterdam if available (high traffic demo port)
    target = next((n for n in ports if n["id"] == "port-rotterdam"), ports[0])
    body = {
        "target_type": "node",
        "target_id": target["id"],
        "severity": 0.85,
        "expected_duration_mean_hours": 36,
        "expected_duration_sigma_hours": 8,
        "source": "manual",
    }
    r = httpx.post(f"{args.host}/disruptions", json=body)
    r.raise_for_status()
    print(f"Injected demo disruption at {target['name']}: {r.json()['id']}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add backend/scripts/demo_seed.py
git commit -m "chore: demo seed script for consistent presentations"
```

---

### Task 24: README + run instructions

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write README**

`README.md`:

````markdown
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
````

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: project README with setup, architecture, demo script"
```

---

## Self-Review Notes

Performed during plan authoring:

- **Spec coverage:** All seven spec sections (problem, goal, non-goals, architecture, data model, algorithms, data flow, testing, demo script, stretch goals, risks) map to tasks. The spec's "explicit YAGNI" list is honored — no auth, no DB, no RL, no ML-learned distributions were added.
- **Placeholder scan:** No TODO/TBD/"handle edge cases" lines. All code steps include complete, runnable code. Every test includes full imports and assertions.
- **Type consistency:** Model names (`Node`, `Edge`, `Shipment`, `Disruption`, `ETAForecast`, `ScenarioBucket`) and enum values (`NodeType.PORT`, `EdgeMode.SEA`, etc.) are used identically in backend models, tests, and frontend type mirrors. Function names (`sample_edge_transit`, `simulate_shipment`, `cascade_affected_ids`, `build_scenarios`, `reroute`) are consistent across their test and implementation tasks.
- **Risk mitigation carried through:** NOAA poll wrapped in try/except with logged failure; React Flow fallback noted (Cytoscape) though not implemented by default; Monte Carlo N tunable from API body.

---

## Parallelization Guide (for the 4-person team)

This plan is linear to keep dependencies clear, but the four teammates can work Phases B / C / D / E in parallel after Phase A completes. Suggested split:

| Person | Tasks | Phase |
|---|---|---|
| ML/data (you) | 5, 6, 7, 8, 9 | Phase B |
| Backend/APIs friend | 10, 11, 12, 13, 14 | Phase C |
| Generalist | 3, 15, 22, 23 | Phases A, D, F |
| Frontend/viz friend | 16, 17, 18, 19, 20, 21 | Phase E |

Everyone contributes to Task 1 (repo scaffold) and Task 24 (README polish). Agree on the API contract in `app/models.py` and `frontend/src/types.ts` as the shared interface — touch those files first, together, before anyone else starts coding.
