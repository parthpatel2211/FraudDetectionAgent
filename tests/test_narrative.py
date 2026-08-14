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


# ------------------------------------------------------------------ Claude path
# Every test here runs offline against a mocked client. CI has no API key, so the
# suite also proves the service degrades correctly without one.

from dataclasses import replace  # noqa: E402
from unittest.mock import MagicMock  # noqa: E402

from backend.narrative import llm as llm_mod  # noqa: E402


def _parsed(narrative, recommendation, next_steps, stop_reason="end_turn"):
    """Mimic client.messages.parse(): a response carrying .parsed_output."""
    resp = MagicMock()
    resp.stop_reason = stop_reason
    resp.parsed_output = llm_mod.CaseSummaryOutput(
        narrative=narrative, recommendation=recommendation, next_steps=next_steps
    )
    client = MagicMock()
    client.messages.parse.return_value = resp
    return client


def test_llm_path_returns_structured_summary(case):
    client = _parsed(
        "Three customers shared one device inside 40 minutes.",
        "Freeze the accounts.",
        ["Freeze the accounts", "Call the customer"],
    )
    s = llm_mod.summarize(case, client=client)
    assert s.source == "llm"
    assert s.narrative == "Three customers shared one device inside 40 minutes."
    assert s.next_steps == ["Freeze the accounts", "Call the customer"]
    assert s.case_id == case.case_id


def test_llm_path_sends_the_configured_model_and_token_cap(case):
    client = _parsed("n", "r", ["s"])
    llm_mod.summarize(case, client=client)
    kwargs = client.messages.parse.call_args.kwargs
    assert kwargs["model"] == llm_mod.settings.ANTHROPIC_MODEL
    assert kwargs["max_tokens"] == llm_mod.settings.LLM_MAX_TOKENS
    assert kwargs["output_format"] is llm_mod.CaseSummaryOutput


def test_prompt_contains_the_evidence(case):
    client = _parsed("n", "r", ["s"])
    llm_mod.summarize(case, client=client)
    prompt = client.messages.parse.call_args.kwargs["messages"][0]["content"]
    assert case.case_id in prompt
    assert case.signals[0].explanation in prompt


def test_api_error_falls_back_to_template(case):
    client = MagicMock()
    client.messages.parse.side_effect = RuntimeError("upstream 529")
    s = llm_mod.summarize(case, client=client)
    assert s.source == "template"
    assert s.narrative.strip()


def test_refusal_falls_back_to_template(case):
    client = _parsed("n", "r", ["s"], stop_reason="refusal")
    assert llm_mod.summarize(case, client=client).source == "template"


def test_truncated_response_falls_back_to_template(case):
    """max_tokens means the structured output may be incomplete."""
    client = _parsed("n", "r", ["s"], stop_reason="max_tokens")
    assert llm_mod.summarize(case, client=client).source == "template"


def test_empty_fields_fall_back_to_template(case):
    client = _parsed("   ", "r", ["s"])
    assert llm_mod.summarize(case, client=client).source == "template"


def test_empty_next_steps_falls_back_to_template(case):
    client = _parsed("n", "r", [])
    assert llm_mod.summarize(case, client=client).source == "template"


def test_no_api_key_uses_template_without_touching_the_network(case, monkeypatch):
    # Settings is a frozen dataclass, so swap the whole object rather than a field.
    monkeypatch.setattr(
        llm_mod, "settings", replace(llm_mod.settings, ANTHROPIC_API_KEY=None)
    )
    monkeypatch.setattr(
        llm_mod, "_client", lambda: pytest.fail("must not build a client without a key")
    )
    assert llm_mod.summarize(case).source == "template"


def test_rate_limiter_blocks_after_budget():
    from backend.ratelimit import RateLimiter
    rl = RateLimiter(per_minute=2)
    assert rl.allow("1.2.3.4") and rl.allow("1.2.3.4")
    assert not rl.allow("1.2.3.4")
    assert rl.allow("5.6.7.8")


def test_rate_limiter_is_disabled_when_budget_is_zero():
    from backend.ratelimit import RateLimiter
    rl = RateLimiter(per_minute=0)
    assert all(rl.allow("1.2.3.4") for _ in range(50))
