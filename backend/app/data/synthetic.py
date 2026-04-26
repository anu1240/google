from datetime import datetime, timedelta, timezone
import random
import networkx as nx
from app.models import (
    Node, Edge, Shipment, NodeType, EdgeMode, Priority, Status,
)

_PORTS = [
    ("port-shanghai", "Shanghai", "CN", 31.23, 121.47),
    ("port-singapore", "Singapore", "SG", 1.29, 103.85),
    ("port-rotterdam", "Rotterdam", "NL", 51.95, 4.14),
    ("port-antwerp", "Antwerp", "BE", 51.22, 4.40),
    ("port-la", "Los Angeles", "US", 33.74, -118.26),
    ("port-ny", "New York", "US", 40.66, -74.05),
    ("port-dubai", "Dubai", "AE", 25.26, 55.30),
    ("port-mumbai", "Mumbai", "IN", 18.95, 72.84),
    ("port-santos", "Santos", "BR", -23.96, -46.33),
    ("port-hamburg", "Hamburg", "DE", 53.54, 9.98),
]

_HUBS = [
    ("hub-frankfurt", "Frankfurt", "DE", 50.11, 8.68),
    ("hub-chicago", "Chicago", "US", 41.88, -87.63),
    ("hub-delhi", "Delhi", "IN", 28.70, 77.10),
    ("hub-beijing", "Beijing", "CN", 39.90, 116.40),
    ("hub-moscow", "Moscow", "RU", 55.75, 37.62),
    ("hub-saopaulo", "São Paulo", "BR", -23.55, -46.63),
    ("hub-johannesburg", "Johannesburg", "ZA", -26.20, 28.04),
    ("hub-atlanta", "Atlanta", "US", 33.75, -84.39),
]

_WAREHOUSES = [
    ("wh-madrid", "Madrid", "ES", 40.42, -3.70),
    ("wh-milan", "Milan", "IT", 45.46, 9.19),
    ("wh-dallas", "Dallas", "US", 32.78, -96.80),
    ("wh-toronto", "Toronto", "CA", 43.65, -79.38),
    ("wh-sydney", "Sydney", "AU", -33.87, 151.21),
    ("wh-seoul", "Seoul", "KR", 37.57, 126.98),
    ("wh-istanbul", "Istanbul", "TR", 41.01, 28.98),
    ("wh-lagos", "Lagos", "NG", 6.52, 3.38),
    ("wh-lima", "Lima", "PE", -12.05, -77.04),
    ("wh-jakarta", "Jakarta", "ID", -6.21, 106.85),
    ("wh-capetown", "Cape Town", "ZA", -33.92, 18.42),
    ("wh-vancouver", "Vancouver", "CA", 49.28, -123.12),
]


def _mk_node(tup, ntype: NodeType, capacity: int) -> Node:
    nid, name, country, lat, lon = tup
    return Node(
        id=nid, type=ntype, lat=lat, lon=lon, name=name, country=country,
        capacity=capacity, current_load=int(capacity * 0.3),
        status=Status.NORMAL,
    )


def _edge_params(mode: EdgeMode) -> tuple[float, float, float]:
    return {
        EdgeMode.SEA: (240.0, 0.18, 0.10),
        EdgeMode.RAIL: (48.0, 0.12, 0.20),
        EdgeMode.TRUCK: (12.0, 0.15, 0.35),
        EdgeMode.AIR: (6.0, 0.10, 1.20),
    }[mode]


def generate_graph(seed: int = 42) -> tuple[list[Node], list[Edge]]:
    rng = random.Random(seed)
    nodes: list[Node] = []
    for t in _PORTS:
        nodes.append(_mk_node(t, NodeType.PORT, 5000))
    for t in _HUBS:
        nodes.append(_mk_node(t, NodeType.HUB, 3000))
    for t in _WAREHOUSES:
        nodes.append(_mk_node(t, NodeType.WAREHOUSE, 1500))

    ports = [n for n in nodes if n.type == NodeType.PORT]
    hubs = [n for n in nodes if n.type == NodeType.HUB]
    whs = [n for n in nodes if n.type == NodeType.WAREHOUSE]

    edges: list[Edge] = []

    def add_edge(src: Node, dst: Node, mode: EdgeMode) -> None:
        mean, sigma, cost = _edge_params(mode)
        mean *= 0.8 + rng.random() * 0.4
        edges.append(Edge(
            id=f"{src.id}->{dst.id}:{mode.value}",
            source_node_id=src.id, target_node_id=dst.id,
            mode=mode, base_transit_mean_hours=mean,
            base_transit_sigma=sigma, cost_per_unit=cost,
        ))

    for i, a in enumerate(ports):
        for b in ports[i + 1:]:
            add_edge(a, b, EdgeMode.SEA)
            add_edge(b, a, EdgeMode.SEA)

    for p in ports:
        sorted_hubs = sorted(hubs, key=lambda h: (h.lat - p.lat) ** 2 + (h.lon - p.lon) ** 2)
        for h in sorted_hubs[: rng.randint(1, 2)]:
            add_edge(p, h, EdgeMode.RAIL)
            add_edge(h, p, EdgeMode.RAIL)

    for h in hubs:
        sorted_whs = sorted(whs, key=lambda w: (w.lat - h.lat) ** 2 + (w.lon - h.lon) ** 2)
        for w in sorted_whs[: rng.randint(2, 3)]:
            add_edge(h, w, EdgeMode.TRUCK)
            add_edge(w, h, EdgeMode.TRUCK)

    for _ in range(6):
        a, b = rng.sample(hubs, 2)
        add_edge(a, b, EdgeMode.AIR)
        add_edge(b, a, EdgeMode.AIR)

    return nodes, edges


def generate_shipments(
    nodes: list[Node], edges: list[Edge], count: int = 100, seed: int = 42
) -> list[Shipment]:
    rng = random.Random(seed)
    g = nx.DiGraph()
    for n in nodes:
        g.add_node(n.id)
    for e in edges:
        g.add_edge(e.source_node_id, e.target_node_id, weight=e.base_transit_mean_hours)

    ports = [n for n in nodes if n.type == NodeType.PORT]
    whs = [n for n in nodes if n.type == NodeType.WAREHOUSE]

    shipments: list[Shipment] = []
    attempts = 0
    while len(shipments) < count and attempts < count * 5:
        attempts += 1
        src = rng.choice(ports)
        dst = rng.choice(whs)
        try:
            path = nx.shortest_path(g, src.id, dst.id, weight="weight")
        except nx.NetworkXNoPath:
            continue
        if len(path) < 2:
            continue
        current_idx = rng.randint(0, max(0, len(path) - 2))
        priority = rng.choices(
            [Priority.STANDARD, Priority.EXPRESS, Priority.CRITICAL],
            weights=[0.6, 0.3, 0.1],
        )[0]
        deadline = datetime.now(timezone.utc) + timedelta(
            hours=rng.randint(48, 336)
        )
        shipments.append(Shipment(
            id=f"SHIP-{len(shipments):04d}",
            source_node_id=src.id,
            destination_node_id=dst.id,
            path=path,
            current_node_id=path[current_idx],
            priority=priority,
            sla_deadline=deadline,
            volume=rng.randint(1, 40),
        ))
    return shipments
