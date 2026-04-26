from __future__ import annotations
import asyncio
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.state import state as _state, AppState
from app.models import (
    Disruption, DisruptionTarget, DisruptionSource, ETAForecast,
)
from app.simulation.engine import simulate_shipment
from app.simulation.scenarios import build_scenarios
from app.simulation.cascade import cascade_affected_ids
from app.simulation.routing import reroute as do_reroute
from app.data.weather import weather_loop
from app.websocket import ws_manager


def get_state() -> AppState:
    return _state


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

    now = datetime.now(timezone.utc)
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


@app.websocket("/live")
async def websocket_live(ws: WebSocket) -> None:
    await ws_manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        await ws_manager.disconnect(ws)
