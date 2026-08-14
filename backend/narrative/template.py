"""Deterministic case narrative.

This is the floor the product stands on: no API key, no network, no cost, and
it always produces a usable summary. The Claude path in llm.py is an upgrade
over this, never a dependency of it - every failure mode there lands back here.

Everything it says is drawn from the case's own signals, so it cannot state
anything the detector did not actually find.
"""

from __future__ import annotations

from backend.models import Case, CaseSummary

_NEXT_STEPS: dict[str, list[str]] = {
    "low": [
        "Add the customer to passive monitoring for 30 days.",
        "No account restriction warranted at this risk level.",
    ],
    "medium": [
        "Queue the case for Level 1 analyst review within one business day.",
        "Flag the account for step-up authentication on the next login.",
        "Add the customer to passive monitoring for 30 days.",
    ],
    "high": [
        "Escalate to a Level 2 analyst for same-day review.",
        "Suspend outbound transfers on the listed accounts pending review.",
        "Contact the customer through a verified channel to confirm the activity.",
        "Preserve device and IP evidence for the case file.",
    ],
    "critical": [
        "Freeze the listed accounts immediately.",
        "Escalate to the financial-crime team within the hour.",
        "Contact the customer through a verified channel, never a channel used "
        "in the flagged transactions.",
        "Preserve device and IP evidence and prepare a regulatory filing "
        "assessment.",
        "Review every other account sharing the implicated devices or IPs.",
    ],
}

_RECOMMENDATION: dict[str, str] = {
    "low": "Monitor. The evidence is weak and does not justify restricting the account.",
    "medium": "Review within one business day and apply step-up authentication.",
    "high": "Restrict outbound movement and escalate to a Level 2 analyst today.",
    "critical": "Freeze the accounts now and escalate to the financial-crime team.",
}


def render_template(case: Case) -> CaseSummary:
    customers = ", ".join(case.customer_ids)
    accounts = ", ".join(case.account_ids)
    plural_c = "customer" if len(case.customer_ids) == 1 else "customers"
    plural_a = "account" if len(case.account_ids) == 1 else "accounts"

    sentences = [
        f"{len(case.transactions)} transactions totalling {case.total_amount:,.2f} USD "
        f"were grouped into case {case.case_id}, involving {plural_c} {customers} "
        f"on {plural_a} {accounts}.",
        # Three decimals, not two: a 0.999 shown as "1.00" reads as certainty.
        f"The case scores {case.risk_score:.3f} ({case.severity}), driven primarily by "
        f"{case.signals[0].label.lower()}." if case.signals else
        f"The case scores {case.risk_score:.3f} ({case.severity}).",
    ]

    for signal in case.signals[:2]:
        sentences.append(signal.explanation)

    if len(case.signals) > 2:
        others = ", ".join(s.label.lower() for s in case.signals[2:])
        sentences.append(f"Supporting signals: {others}.")

    return CaseSummary(
        case_id=case.case_id,
        narrative=" ".join(sentences),
        recommendation=_RECOMMENDATION[case.severity],
        next_steps=list(_NEXT_STEPS[case.severity]),
        source="template",
    )
