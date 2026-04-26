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
