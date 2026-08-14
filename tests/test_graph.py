from datetime import UTC, datetime, timedelta

from backend.engine.graph import (
    LINK_THRESHOLD,
    build_similarity_graph,
    cluster,
    to_case_graph,
)
from backend.models import Transaction

T0 = datetime(2026, 3, 14, 9, 0, tzinfo=UTC)


def tx(id_, cust, *, device=None, ip=None, merchant="M-1", minutes=0, account=None):
    return Transaction(
        id=id_, customer_id=cust, account_id=account or f"ACC-{cust}", merchant_id=merchant,
        device_id=device, ip_address=ip, amount=100.0,
        timestamp=T0 + timedelta(minutes=minutes), channel="WEB", country="US",
    )


def test_shared_merchant_alone_does_not_link():
    """The v1 bug: 40 unrelated customers at one merchant became a single case."""
    txs = [tx(f"t{i}", f"C{i}", merchant="M-POPULAR", minutes=i) for i in range(40)]
    g = build_similarity_graph(txs)
    assert g.number_of_edges() == 0
    assert len(cluster(g)) == 40


def test_merchant_hub_is_skipped_entirely():
    txs = [tx(f"t{i}", f"C{i}", merchant="M-HUB") for i in range(120)]
    assert build_similarity_graph(txs).number_of_edges() == 0


def test_shared_device_links():
    g = build_similarity_graph([tx("a", "C1", device="D1"), tx("b", "C2", device="D1")])
    assert g.has_edge("a", "b")
    assert g["a"]["b"]["weight"] >= LINK_THRESHOLD


def test_same_customer_and_account_links():
    g = build_similarity_graph([tx("a", "C1"), tx("b", "C1")])
    assert g.has_edge("a", "b")


def test_same_customer_alone_does_not_link():
    """Customer at 0.50 is under the 0.60 threshold without a second attribute."""
    txs = [
        tx("a", "C1", account="ACC-1", merchant="M-A"),
        tx("b", "C1", account="ACC-2", merchant="M-B"),
    ]
    assert build_similarity_graph(txs).number_of_edges() == 0


def test_ip_plus_merchant_links():
    txs = [
        tx("a", "C1", ip="9.9.9.9", merchant="M-X", account="ACC-1"),
        tx("b", "C2", ip="9.9.9.9", merchant="M-X", account="ACC-2"),
    ]
    g = build_similarity_graph(txs)
    assert g.has_edge("a", "b")


def test_edges_record_why_they_exist():
    g = build_similarity_graph([tx("a", "C1", device="D1"), tx("b", "C2", device="D1")])
    assert any("device_id=D1" in r for r in g["a"]["b"]["reasons"])


def test_two_separate_rings_stay_separate():
    ring_a = [tx(f"a{i}", f"A{i}", device="DEV-A") for i in range(3)]
    ring_b = [tx(f"b{i}", f"B{i}", device="DEV-B") for i in range(3)]
    clusters = cluster(build_similarity_graph(ring_a + ring_b))
    assert len([c for c in clusters if len(c) == 3]) == 2


def test_isolated_transactions_each_form_their_own_cluster():
    txs = [tx(f"t{i}", f"C{i}", merchant=f"M-{i}") for i in range(5)]
    assert len(cluster(build_similarity_graph(txs))) == 5


def test_empty_graph_clusters_to_nothing():
    assert cluster(build_similarity_graph([])) == []


def test_weights_never_exceed_one():
    """All five attributes shared at once sums past 1.0 and must be capped."""
    txs = [
        tx("a", "C1", device="D1", ip="9.9.9.9", merchant="M-X", account="ACC-1"),
        tx("b", "C1", device="D1", ip="9.9.9.9", merchant="M-X", account="ACC-1"),
    ]
    g = build_similarity_graph(txs)
    assert g["a"]["b"]["weight"] == 1.0


def test_to_case_graph_emits_transaction_and_entity_nodes():
    txs = [tx("a", "C1", device="D1", ip="9.9.9.9")]
    g = build_similarity_graph(txs)
    cg = to_case_graph(txs, {"a": 0.8}, g)
    kinds = {n.kind for n in cg.nodes}
    assert kinds == {"transaction", "customer", "account", "merchant", "device", "ip"}
    tx_node = next(n for n in cg.nodes if n.kind == "transaction")
    assert tx_node.risk == 0.8
    assert tx_node.amount == 100.0


def test_to_case_graph_has_no_duplicate_node_ids():
    txs = [tx("a", "C1", device="D1"), tx("b", "C1", device="D1")]
    cg = to_case_graph(txs, {"a": 0.5, "b": 0.5}, build_similarity_graph(txs))
    ids = [n.id for n in cg.nodes]
    assert len(ids) == len(set(ids))


def test_to_case_graph_edges_reference_existing_nodes():
    txs = [tx("a", "C1", device="D1"), tx("b", "C2", device="D1")]
    cg = to_case_graph(txs, {"a": 0.5, "b": 0.5}, build_similarity_graph(txs))
    ids = {n.id for n in cg.nodes}
    for e in cg.edges:
        assert e.source in ids and e.target in ids
