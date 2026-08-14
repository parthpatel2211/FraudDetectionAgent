from data.generate import RINGS, generate


def test_generate_is_deterministic():
    a, ga = generate(seed=7)
    b, gb = generate(seed=7)
    assert a == b and ga == gb


def test_all_four_rings_present():
    _, gt = generate(seed=42)
    assert set(RINGS) <= set(gt.values())


def test_majority_is_clean():
    txs, gt = generate(seed=42)
    clean = sum(1 for v in gt.values() if v == "clean")
    assert clean / len(txs) > 0.80


def test_every_tx_has_ground_truth():
    txs, gt = generate(seed=42)
    assert {t["id"] for t in txs} == set(gt)


def test_rings_are_not_contiguous():
    """Shuffled, so a detector cannot exploit ordering."""
    txs, gt = generate(seed=42)
    labels = [gt[t["id"]] for t in txs]
    ring_positions = [i for i, v in enumerate(labels) if v == "ring_device"]
    assert max(ring_positions) - min(ring_positions) > len(ring_positions)


def test_every_transaction_validates_against_the_model():
    from backend.models import Transaction
    txs, _ = generate(seed=42)
    parsed = [Transaction(**t) for t in txs]
    assert len(parsed) == len(txs)


def test_different_seeds_differ():
    a, _ = generate(seed=1)
    b, _ = generate(seed=2)
    assert a != b


def test_device_ring_shares_one_device_across_customers():
    txs, gt = generate(seed=42)
    ring = [t for t in txs if gt[t["id"]] == "ring_device"]
    assert len({t["device_id"] for t in ring}) == 1
    assert len({t["customer_id"] for t in ring}) == 3


def test_travel_ring_changes_country_quickly():
    txs, gt = generate(seed=42)
    ring = [t for t in txs if gt[t["id"]] == "ring_travel"]
    assert len({t["country"] for t in ring}) == 2
    assert len({t["customer_id"] for t in ring}) == 1


def test_structuring_amounts_sit_under_the_threshold():
    txs, gt = generate(seed=42)
    ring = [t for t in txs if gt[t["id"]] == "ring_structuring"]
    assert all(8500 <= t["amount"] < 10000 for t in ring)
    assert all(t["channel"] == "TRANSFER" for t in ring)


def test_card_testing_has_small_probes_then_large_charges():
    txs, gt = generate(seed=42)
    ring = [t for t in txs if gt[t["id"]] == "ring_card_testing"]
    small = [t for t in ring if t["amount"] < 5]
    large = [t for t in ring if t["amount"] >= 500]
    assert len(small) >= 3 and len(large) >= 1
