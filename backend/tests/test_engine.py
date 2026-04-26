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
