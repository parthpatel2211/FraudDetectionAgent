"""Claude-generated case narratives.

v1 called the LLM with a free-text prompt, then reconstructed the answer by
scanning lines for "Narrative:" and "Recommendation:" prefixes behind a stack of
hasattr() checks against three different response shapes. Any wording drift
silently produced an empty narrative, and an API hiccup produced an HTTP 500.

This uses structured outputs instead: the response is validated against a
Pydantic schema by the SDK, so there is nothing to parse and nothing to drift.
Every failure path - no key, refusal, truncation, incomplete fields, transport
error - returns the deterministic template summary rather than an error.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from backend.config import settings
from backend.models import Case, CaseSummary
from backend.narrative.template import render_template

logger = logging.getLogger(__name__)


class CaseSummaryOutput(BaseModel):
    """The schema Claude is constrained to fill."""

    narrative: str = Field(
        description="3-6 sentences describing what happened and why it is suspicious."
    )
    recommendation: str = Field(
        description="1-2 sentences on the recommended disposition."
    )
    next_steps: list[str] = Field(
        description="2-5 concrete actions for the analyst, most urgent first."
    )


SYSTEM = (
    "You are a senior financial-crime investigator writing case notes for a "
    "Level 2 analyst. Ground every claim in the evidence provided: cite the "
    "amounts, timestamps, and entity identifiers you were given. Never invent "
    "facts that are not in the evidence. Describe risk and what the evidence "
    "shows; do not assert that fraud has occurred or that anyone is guilty."
)

MAX_TX_IN_PROMPT = 40


def _build_prompt(case: Case) -> str:
    signals = "\n".join(
        f"- {s.label} (contribution {s.contribution:.2f}): {s.explanation}"
        for s in case.signals
    )
    shown = case.transactions[:MAX_TX_IN_PROMPT]
    txs = "\n".join(
        f"- {t.timestamp.isoformat()} | {t.amount:,.2f} {t.currency} | "
        f"merchant {t.merchant_id} | {t.channel} | {t.country or 'unknown'} | "
        f"device {t.device_id or 'none'} | ip {t.ip_address or 'none'}"
        for t in shown
    )
    omitted = len(case.transactions) - len(shown)
    more = "" if omitted <= 0 else f"\n(+{omitted} further transactions omitted)"

    return (
        f"Case {case.case_id}\n"
        f"Risk score: {case.risk_score:.3f} ({case.severity})\n"
        f"Customers: {', '.join(case.customer_ids)}\n"
        f"Accounts: {', '.join(case.account_ids)}\n"
        f"Total value: {case.total_amount:,.2f} USD\n\n"
        f"Detection signals:\n{signals}\n\n"
        f"Transactions:\n{txs}{more}\n\n"
        "Write the case summary."
    )


def _client():
    from anthropic import Anthropic

    return Anthropic(
        api_key=settings.ANTHROPIC_API_KEY,
        timeout=settings.LLM_TIMEOUT_SECONDS,
        max_retries=1,
    )


def summarize(case: Case, client=None) -> CaseSummary:
    """Return an LLM summary, or the template summary if anything goes wrong."""
    if client is None:
        if not settings.ANTHROPIC_API_KEY:
            return render_template(case)
        try:
            client = _client()
        except Exception:
            logger.exception("Anthropic client construction failed")
            return render_template(case)

    try:
        response = client.messages.parse(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=settings.LLM_MAX_TOKENS,
            system=SYSTEM,
            messages=[{"role": "user", "content": _build_prompt(case)}],
            output_format=CaseSummaryOutput,
        )

        stop = getattr(response, "stop_reason", None)
        if stop == "refusal":
            logger.warning("Model declined to summarize %s", case.case_id)
            return render_template(case)
        if stop == "max_tokens":
            # Structured output is only guaranteed complete on a clean stop.
            logger.warning("Summary for %s hit the token cap", case.case_id)
            return render_template(case)

        parsed = response.parsed_output
        narrative = parsed.narrative.strip()
        recommendation = parsed.recommendation.strip()
        steps = [s.strip() for s in parsed.next_steps if s and s.strip()]
        if not (narrative and recommendation and steps):
            raise ValueError("model returned an incomplete summary")

    except Exception:
        logger.warning(
            "LLM summary failed for %s; falling back to template",
            case.case_id, exc_info=True,
        )
        return render_template(case)

    return CaseSummary(
        case_id=case.case_id,
        narrative=narrative,
        recommendation=recommendation,
        next_steps=steps,
        source="llm",
    )
