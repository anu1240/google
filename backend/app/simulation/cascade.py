from __future__ import annotations
from app.models import Shipment, Disruption, DisruptionTarget


def cascade_affected_ids(
    shipments: list[Shipment], disruption: Disruption
) -> set[str]:
    affected: set[str] = set()
    for s in shipments:
        try:
            idx = s.path.index(s.current_node_id)
        except ValueError:
            idx = 0
        remaining = s.path[idx:]
        if disruption.target_type == DisruptionTarget.NODE:
            if disruption.target_id in remaining[1:]:
                affected.add(s.id)
        else:
            prefix = disruption.target_id.split(":", 1)[0]
            for a, b in zip(remaining, remaining[1:]):
                if f"{a}->{b}" == prefix:
                    affected.add(s.id)
                    break
    return affected
