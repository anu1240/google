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
