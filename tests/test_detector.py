from datetime import UTC, datetime, timedelta

from backend.engine.detector import FraudDetector
from backend.models import Transaction

T0 = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)


def clean_tx(i):
    return Transaction(
        id=f"c{i}", customer_id=f"C{i}", account_id=f"ACC-{i}", merchant_id=f"M-{i % 5}",
        device_id=f"DEV-{i}", ip_address=f"10.0.0.{i}", amount=40.0 + i,
        timestamp=T0 + timedelta(hours=i), channel="POS", country="US",
    )


def test_empty_batch_returns_empty_result():
    r = FraudDetector().analyze([])
    assert r.cases == []
    assert r.transactions_analyzed == 0
    assert r.transactions_flagged == 0


def test_clean_batch_produces_no_cases():
    """The v1 bug: quantile thresholding always invented a case."""
    r = FraudDetector().analyze([clean_tx(i) for i in range(12)])
    assert r.cases == []
    assert r.transactions_flagged == 0
    assert r.transactions_analyzed == 12


def test_detector_is_stateless_across_calls():
    """The v1 bug: _fitted latched on the first batch and a new channel crashed scoring."""
    d = FraudDetector()
    web = [clean_tx(i) for i in range(6)]
    atm = [
        clean_tx(i).model_copy(update={"id": f"x{i}", "channel": "ATM"})
        for i in range(6)
    ]
    first = d.analyze(web).model_dump(mode="json")
    d.analyze(atm)
    assert d.analyze(web).model_dump(mode="json") == first


def test_two_detectors_agree():
    txs = [clean_tx(i) for i in range(6)]
    a = FraudDetector().analyze(txs).model_dump(mode="json")
    b = FraudDetector().analyze(txs).model_dump(mode="json")
    assert a == b


def test_case_ids_are_stable_across_runs(demo_transactions):
    a = {c.case_id for c in FraudDetector().analyze(demo_transactions).cases}
    b = {c.case_id for c in FraudDetector().analyze(demo_transactions).cases}
    assert a == b


def test_all_four_rings_are_detected(demo_transactions, ground_truth):
    r = FraudDetector().analyze(demo_transactions)
    flagged = {t.id for c in r.cases for t in c.transactions}
    for ring in ("ring_device", "ring_card_testing", "ring_travel", "ring_structuring"):
        members = {k for k, v in ground_truth.items() if v == ring}
        assert flagged & members, f"{ring} completely missed"


def test_recall_and_precision_meet_bar(demo_transactions, ground_truth):
    r = FraudDetector().analyze(demo_transactions)
    flagged = {t.id for c in r.cases for t in c.transactions}
    fraud = {k for k, v in ground_truth.items() if v != "clean"}
    tp = len(flagged & fraud)
    recall = tp / len(fraud)
    precision = tp / len(flagged) if flagged else 0.0
    assert recall >= 0.80, f"recall {recall:.2f}"
    assert precision >= 0.70, f"precision {precision:.2f}"


def test_scores_are_absolute_not_batch_relative(demo_transactions):
    """The v1 bug: risk_score = mean / batch_max, so the top case was always ~1.0."""
    full = FraudDetector().analyze(demo_transactions)
    assert full.cases
    assert all(0.0 <= c.risk_score <= 1.0 for c in full.cases)
    # A batch-relative score forces the maximum to 1.0 every time.
    assert not all(c.risk_score == 1.0 for c in full.cases)


def test_a_cases_score_survives_removing_other_cases(demo_transactions, ground_truth):
    """Removing unrelated transactions must not move a surviving case's score."""
    full = FraudDetector().analyze(demo_transactions)
    device_case = next(
        c for c in full.cases
        if all(ground_truth[t.id] == "ring_device" for t in c.transactions)
    )
    subset = [
        t for t in demo_transactions
        if ground_truth[t.id] in ("ring_device", "clean")
    ]
    reduced = FraudDetector().analyze(subset)
    same = next(c for c in reduced.cases if c.case_id == device_case.case_id)
    assert same.risk_score == device_case.risk_score


def test_cases_are_sorted_by_risk_descending(demo_transactions):
    cases = FraudDetector().analyze(demo_transactions).cases
    assert [c.risk_score for c in cases] == sorted(
        (c.risk_score for c in cases), reverse=True
    )


def test_case_fields_are_populated(demo_transactions):
    case = FraudDetector().analyze(demo_transactions).cases[0]
    assert case.customer_ids and case.account_ids
    assert case.transactions
    assert case.signals
    assert case.severity in {"low", "medium", "high", "critical"}
    assert case.total_amount == round(sum(t.amount for t in case.transactions), 2)
    assert case.graph.nodes and case.graph.edges


def test_signals_are_sorted_by_contribution(demo_transactions):
    for case in FraudDetector().analyze(demo_transactions).cases:
        contribs = [s.contribution for s in case.signals]
        assert contribs == sorted(contribs, reverse=True)


def test_signal_tx_ids_stay_inside_their_case(demo_transactions):
    """A signal must not cite evidence from transactions outside the case."""
    for case in FraudDetector().analyze(demo_transactions).cases:
        member_ids = {t.id for t in case.transactions}
        for s in case.signals:
            assert set(s.tx_ids) <= member_ids


def test_displayed_signals_reconstruct_the_case_score(demo_transactions):
    """An analyst adding up the shown evidence must arrive at the shown score.

    Before signals aggregated per rule, the panel showed only the strongest
    instance of each while the score counted every instance: the shared-device
    case displayed evidence worth 0.935 against a reported 0.981.
    """
    from backend.engine.scoring import noisy_or

    for case in FraudDetector().analyze(demo_transactions).cases:
        survival = 1.0
        for s in case.signals:
            survival *= 1 - s.contribution
        assert abs((1 - survival) - case.risk_score) < 0.002, case.case_id

    # Guard the maths itself, not just this dataset.
    assert noisy_or([]) == 0.0


def test_signals_report_how_many_times_a_rule_fired(demo_transactions):
    cases = FraudDetector().analyze(demo_transactions).cases
    counts = [s.instances for c in cases for s in c.signals]
    assert all(n >= 1 for n in counts)
    assert any(n > 1 for n in counts), "expected at least one repeated rule"


def test_no_duplicate_rules_within_a_case(demo_transactions):
    for case in FraudDetector().analyze(demo_transactions).cases:
        rules = [s.rule for s in case.signals]
        assert len(rules) == len(set(rules))


def test_every_transaction_appears_in_at_most_one_case(demo_transactions):
    cases = FraudDetector().analyze(demo_transactions).cases
    seen: set[str] = set()
    for c in cases:
        ids = {t.id for t in c.transactions}
        assert not (ids & seen), "a transaction appeared in two cases"
        seen |= ids


def test_threshold_is_configurable():
    txs = [clean_tx(i) for i in range(12)]
    assert FraudDetector(threshold=0.0).analyze(txs).transactions_flagged == 12
    assert FraudDetector(threshold=0.99).analyze(txs).transactions_flagged == 0


def test_result_reports_the_threshold_it_used():
    assert FraudDetector(threshold=0.42).analyze([clean_tx(0)]).threshold == 0.42
