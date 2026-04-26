from __future__ import annotations
from datetime import datetime, timedelta
import numpy as np
from app.models import ScenarioBucket


def build_scenarios(
    trajectories_hours: list[float], now: datetime
) -> list[ScenarioBucket]:
    if not trajectories_hours:
        return []
    arr = np.asarray(trajectories_hours)
    p10, p50, p90 = np.percentile(arr, [10, 50, 90])
    t33, t66 = np.percentile(arr, [33.33, 66.67])
    n = len(arr)
    opt_count = int((arr <= t33).sum())
    mid_count = int(((arr > t33) & (arr <= t66)).sum())
    pes_count = n - opt_count - mid_count
    return [
        ScenarioBucket(
            label="optimistic", probability=opt_count / n,
            eta=now + timedelta(hours=float(p10)),
        ),
        ScenarioBucket(
            label="expected", probability=mid_count / n,
            eta=now + timedelta(hours=float(p50)),
        ),
        ScenarioBucket(
            label="pessimistic", probability=pes_count / n,
            eta=now + timedelta(hours=float(p90)),
        ),
    ]
