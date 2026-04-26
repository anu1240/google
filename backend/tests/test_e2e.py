import os
os.environ.setdefault("CASCADE_DISABLE_WEATHER", "1")

import pytest
from fastapi.testclient import TestClient
from app.main import app, get_state


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_full_disruption_cascade_reroute_flow(client):
    state = get_state()

    g = client.get("/graph").json()
    assert len(g["shipments"]) > 0

    sim1 = client.post("/simulate", json={"n": 200}).json()
    baseline_cascade = len(sim1["cascade_affected"])
    assert baseline_cascade == 0

    hub_ids = [n["id"] for n in g["nodes"] if n["type"] == "hub"]
    traffic = {hid: 0 for hid in hub_ids}
    for s in g["shipments"]:
        for n in s["path"]:
            if n in traffic:
                traffic[n] += 1
    busiest = max(traffic, key=traffic.get)
    d = client.post("/disruptions", json={
        "target_type": "node", "target_id": busiest,
        "severity": 0.9, "expected_duration_mean_hours": 24,
        "expected_duration_sigma_hours": 6, "source": "manual",
    }).json()

    sim2 = client.post("/simulate", json={"n": 200}).json()
    assert len(sim2["cascade_affected"]) > 0

    affected_id = sim2["cascade_affected"][0]
    r = client.post(f"/reroute/{affected_id}")
    assert r.status_code in (200, 409)

    assert client.delete(f"/disruptions/{d['id']}").status_code == 200
