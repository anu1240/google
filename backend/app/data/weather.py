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
