"""Transaction similarity graph and case clustering.

v1 built a bipartite graph joining every transaction to its customer, account,
merchant, device and IP nodes, then took connected components as cases. Because
merchant is a hub attribute, two unrelated customers shopping at the same store
landed in the same component, and at any real scale a single popular merchant
collapsed the entire batch into one case.

Here the graph is transaction-to-transaction. A pair is linked only when the
attributes they share add up past LINK_THRESHOLD, and merchant contributes so
little (0.15) that it can never link a pair on its own. Buckets larger than
their HUB_CAP are skipped outright, since a value shared by hundreds of
transactions describes shared infrastructure rather than a ring.

Bucketing also keeps this near-linear: pairs are only ever compared inside a
shared-attribute bucket, never across the whole batch.
"""

from __future__ import annotations

import itertools
from collections import defaultdict

import networkx as nx

from backend.models import CaseGraph, GraphEdge, GraphNode, Transaction

EDGE_WEIGHTS: dict[str, float] = {
    "customer_id": 0.50,
    "account_id": 0.50,
    "device_id": 0.80,
    "ip_address": 0.50,
    "merchant_id": 0.15,
}

LINK_THRESHOLD = 0.60

HUB_CAPS: dict[str, int] = {
    "customer_id": 200,
    "account_id": 200,
    "device_id": 20,
    "ip_address": 50,
    "merchant_id": 50,
}

# Above this, greedy modularity gets expensive and the payoff is small, so fall
# back to plain connected components.
MAX_COMMUNITY_NODES = 1500


def build_similarity_graph(txs: list[Transaction]) -> nx.Graph:
    g = nx.Graph()
    for t in txs:
        g.add_node(t.id, amount=t.amount, customer_id=t.customer_id)

    pair_weights: dict[tuple[str, str], float] = defaultdict(float)
    pair_reasons: dict[tuple[str, str], list[str]] = defaultdict(list)

    for attr, weight in EDGE_WEIGHTS.items():
        buckets: dict[str, list[str]] = defaultdict(list)
        for t in txs:
            value = getattr(t, attr)
            if value:
                buckets[value].append(t.id)

        for value, ids in buckets.items():
            if len(ids) < 2 or len(ids) > HUB_CAPS[attr]:
                continue
            for a, b in itertools.combinations(sorted(ids), 2):
                pair_weights[(a, b)] += weight
                pair_reasons[(a, b)].append(f"{attr}={value}")

    for (a, b), w in pair_weights.items():
        if w >= LINK_THRESHOLD:
            g.add_edge(a, b, weight=min(1.0, w), reasons=pair_reasons[(a, b)])
    return g


def cluster(g: nx.Graph) -> list[set[str]]:
    """Communities where the graph is dense enough to have them, components otherwise."""
    if g.number_of_nodes() == 0:
        return []
    if g.number_of_edges() == 0:
        return [{n} for n in g.nodes]

    out: list[set[str]] = []
    for comp in nx.connected_components(g):
        if len(comp) <= 3 or len(comp) > MAX_COMMUNITY_NODES:
            out.append(set(comp))
            continue
        sub = g.subgraph(comp)
        try:
            communities = nx.community.greedy_modularity_communities(sub, weight="weight")
            out.extend(set(c) for c in communities)
        except (nx.NetworkXError, ZeroDivisionError, ValueError):
            out.append(set(comp))
    return out


def to_case_graph(
    txs: list[Transaction], scores: dict[str, float], g: nx.Graph
) -> CaseGraph:
    """Bipartite view for the UI: transactions plus the entities that bind them.

    The similarity edges from `g` are included alongside the entity edges, so a
    viewer can see both which transactions were linked and which shared
    attribute did the linking.
    """
    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []

    for t in txs:
        nodes[t.id] = GraphNode(
            id=t.id, kind="transaction", label=t.id,
            risk=scores.get(t.id, 0.0), amount=t.amount,
        )
        entities = [
            (f"cust:{t.customer_id}", "customer", t.customer_id),
            (f"acct:{t.account_id}", "account", t.account_id),
            (f"merch:{t.merchant_id}", "merchant", t.merchant_id),
        ]
        if t.device_id:
            entities.append((f"dev:{t.device_id}", "device", t.device_id))
        if t.ip_address:
            entities.append((f"ip:{t.ip_address}", "ip", t.ip_address))

        for node_id, kind, label in entities:
            nodes.setdefault(node_id, GraphNode(id=node_id, kind=kind, label=label))
            edges.append(GraphEdge(source=t.id, target=node_id, weight=0.4, reasons=[kind]))

    for a, b, data in g.edges(data=True):
        if a in nodes and b in nodes:
            edges.append(GraphEdge(
                source=a, target=b, weight=data["weight"], reasons=data.get("reasons", []),
            ))
    return CaseGraph(nodes=list(nodes.values()), edges=edges)
