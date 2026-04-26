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
