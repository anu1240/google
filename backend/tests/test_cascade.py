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
        _ship("s3", ["A", "Z"], "A"),
        _ship("s4", ["A", "B", "C"], "C"),
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
    affected = cascade_affected_ids(ships, d)
    assert "s1" in affected
