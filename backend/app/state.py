import asyncio
from app.models import Node, Edge, Shipment, Disruption
from app.data.synthetic import generate_graph, generate_shipments


class AppState:
    def __init__(self) -> None:
        self.nodes: dict[str, Node] = {}
        self.edges: dict[str, Edge] = {}
        self.shipments: dict[str, Shipment] = {}
        self.disruptions: dict[str, Disruption] = {}
        self.lock = asyncio.Lock()

    async def load_synthetic(self, seed: int = 42) -> None:
        nodes, edges = generate_graph(seed=seed)
        shipments = generate_shipments(nodes, edges, count=100, seed=seed)
        async with self.lock:
            self.nodes = {n.id: n for n in nodes}
            self.edges = {e.id: e for e in edges}
            self.shipments = {s.id: s for s in shipments}
            self.disruptions = {}

    async def add_disruption(self, d: Disruption) -> None:
        async with self.lock:
            self.disruptions[d.id] = d

    async def remove_disruption(self, disruption_id: str) -> None:
        async with self.lock:
            self.disruptions.pop(disruption_id, None)


state = AppState()
