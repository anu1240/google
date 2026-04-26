import pytest
from app.data.weather import parse_alerts_to_disruptions
from app.models import Node, NodeType


def _fake_alert(severity: str, lat: float, lon: float, event: str) -> dict:
    return {
        "properties": {
            "severity": severity,
            "event": event,
            "headline": f"{event} near lat {lat} lon {lon}",
            "ends": None,
            "expires": "2026-04-25T12:00:00Z",
            "id": f"urn:alert:{event}:{lat}:{lon}",
        },
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
    }


def test_parse_alerts_creates_disruptions_for_nearby_ports():
    ports = [
        Node(id="port-la", type=NodeType.PORT, lat=33.74, lon=-118.26,
             name="Los Angeles", country="US", capacity=5000),
        Node(id="port-ny", type=NodeType.PORT, lat=40.66, lon=-74.05,
             name="New York", country="US", capacity=5000),
    ]
    alerts = [_fake_alert("Severe", 33.80, -118.30, "Storm Warning")]
    disruptions = parse_alerts_to_disruptions(alerts, ports)
    assert len(disruptions) == 1
    assert disruptions[0].target_id == "port-la"
    assert disruptions[0].severity >= 0.5


def test_parse_ignores_minor_alerts():
    ports = [Node(id="port-la", type=NodeType.PORT, lat=33.74, lon=-118.26,
                  name="LA", country="US", capacity=5000)]
    alerts = [_fake_alert("Minor", 33.80, -118.30, "Advisory")]
    disruptions = parse_alerts_to_disruptions(alerts, ports)
    assert disruptions == []
