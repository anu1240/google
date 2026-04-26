import networkx as nx
from app.data.synthetic import generate_graph, generate_shipments
from app.models import NodeType, Status


def test_graph_has_expected_shape():
    nodes, edges = generate_graph(seed=42)
    assert 28 <= len(nodes) <= 40
    assert len(edges) >= len(nodes)
    types = {n.type for n in nodes}
    assert NodeType.PORT in types and NodeType.WAREHOUSE in types and NodeType.HUB in types


def test_graph_is_weakly_connected():
    nodes, edges = generate_graph(seed=42)
    g = nx.DiGraph()
    for n in nodes:
        g.add_node(n.id)
    for e in edges:
        g.add_edge(e.source_node_id, e.target_node_id)
    assert nx.is_weakly_connected(g)


def test_shipments_have_valid_paths():
    nodes, edges = generate_graph(seed=42)
    shipments = generate_shipments(nodes, edges, count=50, seed=42)
    node_ids = {n.id for n in nodes}
    edge_pairs = {(e.source_node_id, e.target_node_id) for e in edges}
    assert len(shipments) == 50
    for s in shipments:
        assert s.source_node_id in node_ids
        assert s.destination_node_id in node_ids
        assert s.current_node_id in s.path
        for a, b in zip(s.path, s.path[1:]):
            assert (a, b) in edge_pairs, f"invalid edge {a}->{b} in shipment {s.id}"
