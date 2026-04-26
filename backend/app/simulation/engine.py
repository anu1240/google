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
                total += 24.0
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
