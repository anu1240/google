import pytest
from datetime import datetime, timezone
from app.state import AppState
from app.models import (
    Disruption, DisruptionTarget, DisruptionSource,
)


@pytest.mark.asyncio
async def test_state_loads_synthetic_data():
    s = AppState()
    await s.load_synthetic()
    async with s.lock:
        assert len(s.nodes) > 25
        assert len(s.edges) > 25
        assert len(s.shipments) >= 50


@pytest.mark.asyncio
async def test_add_and_remove_disruption():
    s = AppState()
    await s.load_synthetic()
    d = Disruption(
        id="d-test", target_type=DisruptionTarget.NODE,
        target_id=next(iter(s.nodes)),
        severity=0.5, expected_duration_mean_hours=12,
        expected_duration_sigma_hours=3,
        source=DisruptionSource.MANUAL,
        created_at=datetime.now(timezone.utc),
    )
    await s.add_disruption(d)
    async with s.lock:
        assert "d-test" in s.disruptions
    await s.remove_disruption("d-test")
    async with s.lock:
        assert "d-test" not in s.disruptions
