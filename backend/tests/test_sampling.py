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
