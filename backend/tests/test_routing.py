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
        _e("A", "B", 10), _e("B", "D", 10),
        _e("A", "C", 20), _e("C", "D", 20),
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
