import pytest

from backend.engine.rules import RuleHit
from backend.engine.scoring import noisy_or, severity


def hit(weight, score):
    return RuleHit("r", "R", score, weight, "why 1", ("t1",))


def test_no_hits_is_zero():
    assert noisy_or([]) == 0.0


def test_single_hit_is_weight_times_score():
    assert noisy_or([hit(0.8, 0.5)]) == pytest.approx(0.4)


def test_two_hits_combine_without_exceeding_one():
    # 1 - (1-0.8)(1-0.6) = 0.92
    assert noisy_or([hit(0.8, 1.0), hit(0.6, 1.0)]) == pytest.approx(0.92)


def test_many_strong_hits_stay_bounded():
    assert noisy_or([hit(0.9, 1.0)] * 20) <= 1.0


def test_combination_is_monotone():
    """Adding evidence can never lower a score."""
    base = noisy_or([hit(0.5, 1.0)])
    more = noisy_or([hit(0.5, 1.0), hit(0.3, 1.0)])
    assert more > base


def test_off_hours_alone_is_below_threshold():
    assert noisy_or([hit(0.25, 1.0)]) < 0.5


def test_amount_zscore_alone_is_below_threshold():
    assert noisy_or([hit(0.45, 1.0)]) < 0.5


def test_device_ring_alone_is_above_threshold():
    assert noisy_or([hit(0.85, 1.0)]) > 0.5


def test_two_weak_signals_can_together_clear_the_threshold():
    """Off-hours plus an outlier amount is more than either alone."""
    assert noisy_or([hit(0.25, 1.0), hit(0.45, 1.0)]) > 0.5


@pytest.mark.parametrize("score,expected", [
    (0.00, "low"), (0.10, "low"), (0.39, "low"),
    (0.40, "medium"), (0.45, "medium"), (0.64, "medium"),
    (0.65, "high"), (0.70, "high"), (0.84, "high"),
    (0.85, "critical"), (0.90, "critical"), (1.00, "critical"),
])
def test_severity_bands(score, expected):
    assert severity(score) == expected


def test_score_transactions_covers_every_transaction(demo_transactions):
    from backend.engine.context import Context
    from backend.engine.scoring import score_transactions

    ctx = Context.build(demo_transactions)
    scores, hits = score_transactions(ctx)
    assert set(scores) == {t.id for t in demo_transactions}
    assert all(0.0 <= v <= 1.0 for v in scores.values())
    # Transactions with no hits must score exactly zero, not a default.
    unhit = [tid for tid in scores if tid not in hits]
    assert all(scores[tid] == 0.0 for tid in unhit)


def test_score_transactions_ranks_fraud_above_clean(demo_transactions, ground_truth):
    from backend.engine.context import Context
    from backend.engine.scoring import score_transactions

    scores, _ = score_transactions(Context.build(demo_transactions))
    fraud = [scores[t] for t, lbl in ground_truth.items() if lbl != "clean"]
    clean = [scores[t] for t, lbl in ground_truth.items() if lbl == "clean"]
    assert sum(fraud) / len(fraud) > sum(clean) / len(clean)
