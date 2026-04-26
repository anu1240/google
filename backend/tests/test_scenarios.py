from datetime import datetime, timezone
from app.simulation.scenarios import build_scenarios


def test_three_buckets_cover_full_probability():
    trajectories = list(range(300))
    now = datetime.now(timezone.utc)
    buckets = build_scenarios(trajectories, now)
    assert len(buckets) == 3
    labels = [b.label for b in buckets]
    assert labels == ["optimistic", "expected", "pessimistic"]
    total = sum(b.probability for b in buckets)
    assert 0.99 < total < 1.01


def test_etas_are_monotonically_later():
    trajectories = [5, 10, 15, 20, 25, 30, 35, 40, 45]
    now = datetime.now(timezone.utc)
    buckets = build_scenarios(trajectories, now)
    assert buckets[0].eta < buckets[1].eta < buckets[2].eta
