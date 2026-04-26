import os
os.environ.setdefault("CASCADE_DISABLE_WEATHER", "1")

import pytest
from fastapi.testclient import TestClient
from app.main import app, get_state


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_graph_endpoint_returns_nodes_edges_shipments(client):
    r = client.get("/graph")
    assert r.status_code == 200
    data = r.json()
    assert "nodes" in data and "edges" in data and "shipments" in data
    assert len(data["nodes"]) > 25


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_post_and_delete_disruption(client):
    state = get_state()
    node_id = next(iter(state.nodes))
    body = {
        "target_type": "node",
        "target_id": node_id,
        "severity": 0.6,
        "expected_duration_mean_hours": 12,
        "expected_duration_sigma_hours": 3,
        "source": "manual",
    }
    r = client.post("/disruptions", json=body)
    assert r.status_code == 200
    d = r.json()
    assert d["target_id"] == node_id
    disruption_id = d["id"]

    r2 = client.get("/graph")
    assert any(x["id"] == disruption_id for x in r2.json()["disruptions"])

    r3 = client.delete(f"/disruptions/{disruption_id}")
    assert r3.status_code == 200

    r4 = client.get("/graph")
    assert not any(x["id"] == disruption_id for x in r4.json()["disruptions"])


def test_simulate_returns_forecasts(client):
    r = client.post("/simulate", json={"n": 200})
    assert r.status_code == 200
    data = r.json()
    assert "forecasts" in data
    assert len(data["forecasts"]) > 0
    f = data["forecasts"][0]
    assert "shipment_id" in f and "p10" in f and "p50" in f and "p90" in f
    assert "scenarios" in f and len(f["scenarios"]) == 3


def test_simulate_with_shipment_filter(client):
    state = get_state()
    ids = list(state.shipments)[:3]
    r = client.post("/simulate", json={"n": 100, "shipment_ids": ids})
    assert r.status_code == 200
    data = r.json()
    assert {f["shipment_id"] for f in data["forecasts"]} == set(ids)


def test_reroute_endpoint(client):
    state = get_state()
    shipment_id = next(iter(state.shipments))
    r = client.post(f"/reroute/{shipment_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["shipment_id"] == shipment_id
    assert "new_path" in data
    assert "expected_transit_hours" in data


def test_websocket_receives_disruption_broadcast(client):
    state = get_state()
    node_id = next(iter(state.nodes))
    with client.websocket_connect("/live") as ws:
        r = client.post("/disruptions", json={
            "target_type": "node", "target_id": node_id,
            "severity": 0.4, "expected_duration_mean_hours": 6,
            "expected_duration_sigma_hours": 2, "source": "manual",
        })
        assert r.status_code == 200
        msg = ws.receive_json()
        assert msg["event"] == "disruption.added"
        assert msg["payload"]["target_id"] == node_id
