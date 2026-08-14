import inspect
from datetime import UTC, datetime, timedelta

from backend.engine import rules as rules_mod
from backend.engine.context import Context
from backend.engine.rules import (
    rule_amount_zscore,
    rule_card_testing,
    rule_impossible_travel,
    rule_new_merchant_burst,
    rule_off_hours,
    rule_rapid_escalation,
    rule_shared_device_ring,
    rule_shared_ip_ring,
    rule_structuring,
    rule_velocity,
)
from backend.models import Transaction

T0 = datetime(2026, 3, 14, 9, 0, tzinfo=UTC)


def tx(id_, cust, minutes=0, *, device="DEV-1", ip="1.1.1.1", country="US",
       amount=100.0, merchant="M-1", account=None, channel="WEB", hours=0):
    return Transaction(
        id=id_, customer_id=cust, account_id=account or f"ACC-{cust}",
        merchant_id=merchant, device_id=device, ip_address=ip, amount=amount,
        timestamp=T0 + timedelta(minutes=minutes, hours=hours),
        channel=channel, country=country,
    )


# --------------------------------------------------------------- shared_device_ring

def test_shared_device_ring_fires_for_three_customers_on_one_device():
    ctx = Context.build([tx("a", "C1", 0), tx("b", "C2", 5), tx("c", "C3", 10)])
    hits = rule_shared_device_ring(ctx)
    assert len(hits) == 1
    assert hits[0].score == 1.0
    assert set(hits[0].tx_ids) == {"a", "b", "c"}
    assert "3 distinct customers" in hits[0].explanation


def test_shared_device_ring_silent_for_one_customer():
    ctx = Context.build([tx("a", "C1", 0), tx("b", "C1", 5)])
    assert rule_shared_device_ring(ctx) == []


def test_shared_device_ring_skips_hub_devices():
    """A shared kiosk with hundreds of transactions is not a ring."""
    ctx = Context.build([tx(f"t{i}", f"C{i}", i, device="DEV-KIOSK") for i in range(40)])
    assert rule_shared_device_ring(ctx) == []


# -------------------------------------------------------------- impossible_travel

def test_impossible_travel_fires_on_fast_country_change():
    ctx = Context.build([tx("a", "C1", 0, country="US"), tx("b", "C1", 25, country="SG")])
    hits = rule_impossible_travel(ctx)
    assert len(hits) == 1
    assert hits[0].score == 1.0
    assert set(hits[0].tx_ids) == {"a", "b"}


def test_impossible_travel_silent_after_six_hours():
    ctx = Context.build([tx("a", "C1", 0, country="US"), tx("b", "C1", 360, country="SG")])
    assert rule_impossible_travel(ctx) == []


def test_impossible_travel_ignores_unknown_country():
    ctx = Context.build([tx("a", "C1", 0, country=None), tx("b", "C1", 10, country="SG")])
    assert rule_impossible_travel(ctx) == []


def test_impossible_travel_decays_between_one_and_four_hours():
    ctx = Context.build([tx("a", "C1", 0, country="US"), tx("b", "C1", 150, country="SG")])
    hits = rule_impossible_travel(ctx)
    assert 0.0 < hits[0].score < 1.0


# ------------------------------------------------------------------- card_testing

def test_card_testing_fires_on_probes_then_large_charge():
    txs = [tx(f"s{i}", "C1", i, amount=2.0, merchant=f"M-{i}") for i in range(4)]
    txs.append(tx("big", "C1", 20, amount=1800.0))
    hits = rule_card_testing(Context.build(txs))
    assert len(hits) == 1
    assert "big" in hits[0].tx_ids
    assert "4" in hits[0].explanation


def test_card_testing_silent_without_the_cash_out():
    txs = [tx(f"s{i}", "C1", i, amount=2.0, merchant=f"M-{i}") for i in range(5)]
    assert rule_card_testing(Context.build(txs)) == []


def test_card_testing_silent_with_too_few_probes():
    txs = [tx("s0", "C1", 0, amount=2.0), tx("big", "C1", 10, amount=1800.0)]
    assert rule_card_testing(Context.build(txs)) == []


# -------------------------------------------------------------------- structuring

def test_structuring_fires_on_repeated_just_under_threshold_transfers():
    txs = [tx(f"t{i}", "C1", hours=i * 3, amount=9400.0, channel="TRANSFER") for i in range(4)]
    hits = rule_structuring(Context.build(txs))
    assert len(hits) == 1
    assert hits[0].score == 1.0
    assert len(hits[0].tx_ids) == 4


def test_structuring_silent_below_the_band():
    txs = [tx(f"t{i}", "C1", hours=i * 3, amount=500.0, channel="TRANSFER") for i in range(4)]
    assert rule_structuring(Context.build(txs)) == []


def test_structuring_silent_when_spread_over_days():
    txs = [tx(f"t{i}", "C1", hours=i * 30, amount=9400.0, channel="TRANSFER") for i in range(4)]
    assert rule_structuring(Context.build(txs)) == []


# --------------------------------------------------------------- rapid_escalation

def test_rapid_escalation_fires_on_climbing_amounts_at_one_merchant():
    txs = [
        tx("a", "C1", 0, amount=500.0, merchant="M-X"),
        tx("b", "C1", 5, amount=900.0, merchant="M-X"),
        tx("c", "C1", 10, amount=1600.0, merchant="M-X"),
    ]
    hits = rule_rapid_escalation(Context.build(txs))
    assert len(hits) == 1
    assert set(hits[0].tx_ids) == {"a", "b", "c"}


def test_rapid_escalation_silent_when_amounts_are_flat():
    txs = [tx(f"t{i}", "C1", i * 5, amount=500.0, merchant="M-X") for i in range(3)]
    assert rule_rapid_escalation(Context.build(txs)) == []


def test_rapid_escalation_silent_when_slow():
    txs = [
        tx("a", "C1", 0, amount=500.0, merchant="M-X"),
        tx("b", "C1", 120, amount=1600.0, merchant="M-X"),
    ]
    assert rule_rapid_escalation(Context.build(txs)) == []


# ----------------------------------------------------------------------- velocity

def test_velocity_fires_above_six_in_ten_minutes():
    txs = [tx(f"t{i}", "C1", i, merchant=f"M-{i}") for i in range(8)]
    hits = rule_velocity(Context.build(txs))
    assert len(hits) == 1
    assert "8 transactions" in hits[0].explanation


def test_velocity_silent_when_spread_out():
    txs = [tx(f"t{i}", "C1", i * 30, merchant=f"M-{i}") for i in range(8)]
    assert rule_velocity(Context.build(txs)) == []


# ------------------------------------------------------------------ amount_zscore

def test_amount_zscore_fires_on_a_far_outlier():
    txs = [tx(f"t{i}", "C1", i * 60, amount=50.0) for i in range(8)]
    txs.append(tx("spike", "C1", 600, amount=9000.0))
    hits = rule_amount_zscore(Context.build(txs))
    assert len(hits) == 1
    assert hits[0].tx_ids == ("spike",)


def test_amount_zscore_silent_on_uniform_amounts():
    txs = [tx(f"t{i}", "C1", i * 60, amount=50.0) for i in range(8)]
    assert rule_amount_zscore(Context.build(txs)) == []


def test_amount_zscore_silent_without_enough_history():
    txs = [tx("a", "C1", 0, amount=10.0), tx("b", "C1", 60, amount=9000.0)]
    assert rule_amount_zscore(Context.build(txs)) == []


# ----------------------------------------------------------------- shared_ip_ring

def test_shared_ip_ring_fires_for_four_customers():
    txs = [tx(f"t{i}", f"C{i}", i, device=f"DEV-{i}", ip="9.9.9.9") for i in range(4)]
    hits = rule_shared_ip_ring(Context.build(txs))
    assert len(hits) == 1
    assert "4 distinct customers" in hits[0].explanation


def test_shared_ip_ring_silent_for_two_customers():
    """Looser than the device rule: two customers behind one NAT is normal."""
    txs = [tx(f"t{i}", f"C{i}", i, device=f"DEV-{i}", ip="9.9.9.9") for i in range(2)]
    assert rule_shared_ip_ring(Context.build(txs)) == []


# ------------------------------------------------------------- new_merchant_burst

def test_new_merchant_burst_fires_on_three_unseen_merchants_in_an_hour():
    txs = [tx(f"t{i}", "C1", i * 10, merchant=f"M-NEW-{i}") for i in range(4)]
    hits = rule_new_merchant_burst(Context.build(txs))
    assert len(hits) == 1


def test_new_merchant_burst_silent_on_familiar_merchants():
    txs = [tx(f"t{i}", "C1", i * 10, merchant="M-USUAL") for i in range(4)]
    assert rule_new_merchant_burst(Context.build(txs)) == []


# ---------------------------------------------------------------------- off_hours

def test_off_hours_fires_between_one_and_four_utc():
    ctx = Context.build([tx("a", "C1", hours=-6)])  # 03:00 UTC
    hits = rule_off_hours(ctx)
    assert len(hits) == 1
    assert hits[0].score == 1.0


def test_off_hours_silent_during_the_day():
    ctx = Context.build([tx("a", "C1", 0)])  # 09:00 UTC
    assert rule_off_hours(ctx) == []


# ------------------------------------------------------------------------ registry

def test_every_rule_function_is_registered():
    defined = {
        n for n, _ in inspect.getmembers(rules_mod, inspect.isfunction)
        if n.startswith("rule_")
    }
    registered = {f.__name__ for f in rules_mod.ALL_RULES}
    assert defined == registered


def test_rule_meta_covers_every_registered_rule():
    assert set(rules_mod.RULE_META) == {f.__name__ for f in rules_mod.ALL_RULES}
    for meta in rules_mod.RULE_META.values():
        assert {"rule", "label", "weight", "description"} <= set(meta)
        assert 0 < meta["weight"] <= 1


def test_every_rule_is_silent_on_an_empty_batch():
    ctx = Context.build([])
    for fn in rules_mod.ALL_RULES:
        assert fn(ctx) == [], f"{fn.__name__} fired on an empty batch"


def test_every_rule_declares_weight_matching_its_meta():
    """A hit's weight must match the advertised weight, or explain_rules lies."""
    ctx = Context.build([
        tx("a", "C1", 0, country="US", device="DEV-S", ip="9.9.9.9"),
        tx("b", "C2", 20, country="SG", device="DEV-S", ip="9.9.9.9"),
        tx("c", "C3", 40, country="SG", device="DEV-S", ip="9.9.9.9"),
    ])
    for fn in rules_mod.ALL_RULES:
        for h in fn(ctx):
            assert h.weight == rules_mod.RULE_META[fn.__name__]["weight"]
            assert h.rule == rules_mod.RULE_META[fn.__name__]["rule"]


def test_every_hit_has_a_nonempty_explanation_with_a_digit():
    """Explanations must cite the numbers that triggered them."""
    txs = [tx(f"s{i}", "C1", i, amount=2.0, merchant=f"M-{i}") for i in range(4)]
    txs.append(tx("big", "C1", 20, amount=1800.0))
    ctx = Context.build(txs)
    for fn in rules_mod.ALL_RULES:
        for h in fn(ctx):
            assert h.explanation.strip()
            assert any(ch.isdigit() for ch in h.explanation), fn.__name__
