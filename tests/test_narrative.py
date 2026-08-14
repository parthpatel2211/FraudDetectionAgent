import pytest

from backend.engine.detector import FraudDetector
from backend.narrative.template import render_template


@pytest.fixture(scope="module")
def cases(demo_transactions):
    result = FraudDetector().analyze(demo_transactions)
    assert result.cases
    return result.cases


@pytest.fixture(scope="module")
def case(cases):
    return cases[0]


def test_template_is_marked_as_template(case):
    assert render_template(case).source == "template"


def test_template_carries_the_case_id(case):
    assert render_template(case).case_id == case.case_id


def test_template_mentions_the_top_signal(case):
    summary = render_template(case)
    assert case.signals[0].label.lower() in summary.narrative.lower()


def test_template_includes_amount_and_count(case):
    summary = render_template(case)
    assert str(len(case.transactions)) in summary.narrative
    assert f"{case.total_amount:,.2f}" in summary.narrative


def test_template_quotes_the_top_signal_explanation(case):
    """The evidence sentence must survive into the narrative verbatim."""
    assert case.signals[0].explanation in render_template(case).narrative


def test_template_names_the_customers(case):
    narrative = render_template(case).narrative
    assert all(cid in narrative for cid in case.customer_ids)


def test_template_next_steps_are_populated(case):
    summary = render_template(case)
    assert len(summary.next_steps) >= 2
    assert all(s.strip() for s in summary.next_steps)


def test_template_recommendation_is_populated(case):
    assert render_template(case).recommendation.strip()


def test_next_steps_scale_with_severity(cases):
    """A critical case must get at least as many actions as a lesser one."""
    by_sev = {c.severity: render_template(c) for c in cases}
    order = ["low", "medium", "high", "critical"]
    present = [s for s in order if s in by_sev]
    counts = [len(by_sev[s].next_steps) for s in present]
    assert counts == sorted(counts)


def test_critical_case_recommends_immediate_action(cases):
    critical = [c for c in cases if c.severity == "critical"]
    assert critical, "demo dataset should produce at least one critical case"
    steps = " ".join(render_template(critical[0]).next_steps).lower()
    assert "freeze" in steps or "suspend" in steps or "block" in steps


def test_template_is_deterministic(case):
    assert render_template(case).model_dump() == render_template(case).model_dump()


def test_template_works_for_every_case(cases):
    for c in cases:
        s = render_template(c)
        assert s.narrative.strip() and s.recommendation.strip() and s.next_steps
