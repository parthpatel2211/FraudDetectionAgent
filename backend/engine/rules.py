"""Explainable fraud rules.

Each rule is a pure function of the batch Context returning zero or more
RuleHits. A hit carries the transactions it implicates and an explanation that
must contain the concrete numbers that triggered it - the UI renders those
strings verbatim as the case's evidence, so a vague explanation is a bug.

Weights are the rule's maximum contribution to a transaction's risk under the
noisy-OR combination in scoring.py. They are calibrated so that a single weak
signal (off_hours at 0.25) cannot on its own clear the 0.5 flag threshold,
while a single strong one (shared_device_ring at 0.85) can.
"""

from __future__ import annotations

import statistics
from collections.abc import Callable
from dataclasses import dataclass

from backend.engine.context import Context

# Buckets bigger than these are hubs - a public terminal, a corporate NAT - and
# their size is evidence of shared infrastructure, not of a fraud ring.
HUB_MAX_DEVICE = 20
HUB_MAX_IP = 50

# Structuring band: high enough to be worth reporting, low enough to dodge a
# 10,000 threshold.
STRUCTURING_LOW = 8500.0
STRUCTURING_HIGH = 10000.0

CARD_TEST_PROBE_MAX = 5.0
CARD_TEST_CASHOUT_MIN = 500.0
CARD_TEST_WINDOW_MIN = 120

VELOCITY_WINDOW_MIN = 10
VELOCITY_BASELINE = 5

ESCALATION_GAP_MIN = 15
NEW_MERCHANT_WINDOW_MIN = 60


@dataclass(frozen=True)
class RuleHit:
    rule: str
    label: str
    score: float          # 0..1, how strongly this instance fired
    weight: float         # 0..1, this rule's maximum contribution to risk
    explanation: str      # must contain the concrete numbers that triggered it
    tx_ids: tuple[str, ...]


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def _minutes(a, b) -> float:
    return abs((b - a).total_seconds()) / 60


# --------------------------------------------------------------------------- rules


def rule_shared_device_ring(ctx: Context) -> list[RuleHit]:
    hits: list[RuleHit] = []
    for device, items in ctx.by_device.items():
        if len(items) > HUB_MAX_DEVICE:
            continue
        customers = {t.customer_id for t in items}
        if len(customers) < 2:
            continue
        hits.append(RuleHit(
            rule="shared_device_ring",
            label="Shared device across customers",
            score=_clamp((len(customers) - 1) / 2),
            weight=0.85,
            explanation=(
                f"Device {device} was used by {len(customers)} distinct customers "
                f"({', '.join(sorted(customers))}) across {len(items)} transactions."
            ),
            tx_ids=tuple(t.id for t in items),
        ))
    return hits


def rule_impossible_travel(ctx: Context) -> list[RuleHit]:
    hits: list[RuleHit] = []
    for cid, items in ctx.by_customer.items():
        for prev, cur in zip(items, items[1:], strict=False):
            if not prev.country or not cur.country or prev.country == cur.country:
                continue
            gap_h = (cur.timestamp - prev.timestamp).total_seconds() / 3600
            if gap_h >= 4:
                continue
            hits.append(RuleHit(
                rule="impossible_travel",
                label="Geographically impossible sequence",
                score=1.0 if gap_h <= 1 else _clamp((4 - gap_h) / 3),
                weight=0.90,
                explanation=(
                    f"Customer {cid} transacted in {prev.country} then {cur.country} "
                    f"{gap_h * 60:.0f} minutes apart."
                ),
                tx_ids=(prev.id, cur.id),
            ))
    return hits


def rule_card_testing(ctx: Context) -> list[RuleHit]:
    """Small probes to confirm a card still works, then the real charge."""
    hits: list[RuleHit] = []
    for cid, items in ctx.by_customer.items():
        probes = [t for t in items if t.amount < CARD_TEST_PROBE_MAX]
        if len(probes) < 3:
            continue
        cashouts = [
            t for t in items
            if t.amount >= CARD_TEST_CASHOUT_MIN
            and any(
                0 <= (t.timestamp - p.timestamp).total_seconds() / 60 <= CARD_TEST_WINDOW_MIN
                for p in probes
            )
        ]
        if not cashouts:
            continue
        window_probes = [
            p for p in probes
            if any(
                0 <= (c.timestamp - p.timestamp).total_seconds() / 60 <= CARD_TEST_WINDOW_MIN
                for c in cashouts
            )
        ]
        largest = max(t.amount for t in cashouts)
        hits.append(RuleHit(
            rule="card_testing",
            label="Card testing followed by cash-out",
            score=_clamp(len(window_probes) / 5),
            weight=0.80,
            explanation=(
                f"Customer {cid} made {len(window_probes)} probe transactions under "
                f"{CARD_TEST_PROBE_MAX:.0f} USD, then {len(cashouts)} charge(s) up to "
                f"{largest:,.2f} USD within {CARD_TEST_WINDOW_MIN} minutes."
            ),
            tx_ids=tuple(t.id for t in window_probes + cashouts),
        ))
    return hits


def rule_structuring(ctx: Context) -> list[RuleHit]:
    """Repeated amounts parked just below a reporting threshold."""
    hits: list[RuleHit] = []
    for cid, items in ctx.by_customer.items():
        band = [t for t in items if STRUCTURING_LOW <= t.amount < STRUCTURING_HIGH]
        if len(band) < 3:
            continue
        left = 0
        best: list = []
        for right in range(len(band)):
            while (band[right].timestamp - band[left].timestamp).total_seconds() > 24 * 3600:
                left += 1
            window = band[left:right + 1]
            if len(window) > len(best):
                best = window
        if len(best) < 3:
            continue
        total = sum(t.amount for t in best)
        hits.append(RuleHit(
            rule="structuring",
            label="Amounts just under a reporting threshold",
            score=_clamp(len(best) / 4),
            weight=0.75,
            explanation=(
                f"Customer {cid} moved {total:,.2f} USD across {len(best)} transactions "
                f"of {STRUCTURING_LOW:,.0f}-{STRUCTURING_HIGH:,.0f} USD within 24 hours."
            ),
            tx_ids=tuple(t.id for t in best),
        ))
    return hits


def rule_rapid_escalation(ctx: Context) -> list[RuleHit]:
    """Amounts climbing fast at one merchant: probing a limit before cashing out."""
    hits: list[RuleHit] = []
    groups: dict[tuple[str, str], list] = {}
    for t in ctx.txs:
        groups.setdefault((t.customer_id, t.merchant_id), []).append(t)

    for (cid, merchant), items in groups.items():
        if len(items) < 2:
            continue
        run = [items[0]]
        for prev, cur in zip(items, items[1:], strict=False):
            close = _minutes(prev.timestamp, cur.timestamp) <= ESCALATION_GAP_MIN
            if close and cur.amount > prev.amount:
                run.append(cur)
                continue
            if len(run) >= 2 and run[-1].amount >= 2 * run[0].amount:
                hits.append(_escalation_hit(cid, merchant, run))
            run = [cur]
        if len(run) >= 2 and run[-1].amount >= 2 * run[0].amount:
            hits.append(_escalation_hit(cid, merchant, run))
    return hits


def _escalation_hit(cid: str, merchant: str, run: list) -> RuleHit:
    return RuleHit(
        rule="rapid_escalation",
        label="Escalating amounts at one merchant",
        score=_clamp((len(run) - 1) / 3),
        weight=0.70,
        explanation=(
            f"Customer {cid} escalated from {run[0].amount:,.2f} to {run[-1].amount:,.2f} USD "
            f"at merchant {merchant} across {len(run)} transactions in "
            f"{_minutes(run[0].timestamp, run[-1].timestamp):.0f} minutes."
        ),
        tx_ids=tuple(t.id for t in run),
    )


def rule_velocity(ctx: Context) -> list[RuleHit]:
    hits: list[RuleHit] = []
    for cid, items in ctx.by_customer.items():
        left = 0
        best: list = []
        for right in range(len(items)):
            while (
                items[right].timestamp - items[left].timestamp
            ).total_seconds() > VELOCITY_WINDOW_MIN * 60:
                left += 1
            window = items[left:right + 1]
            if len(window) > len(best):
                best = window
        if len(best) <= VELOCITY_BASELINE:
            continue
        hits.append(RuleHit(
            rule="velocity",
            label="Abnormal transaction velocity",
            score=_clamp((len(best) - VELOCITY_BASELINE) / 10),
            weight=0.65,
            explanation=(
                f"Customer {cid} made {len(best)} transactions within "
                f"{VELOCITY_WINDOW_MIN} minutes."
            ),
            tx_ids=tuple(t.id for t in best),
        ))
    return hits


def rule_amount_zscore(ctx: Context) -> list[RuleHit]:
    """Amount far above the customer's own baseline, measured leave-one-out.

    The baseline deliberately excludes the transaction under test. Including it
    lets a single large outlier inflate the mean and standard deviation it is
    being compared against - it masks itself. With population standard deviation
    the z-score of any point is bounded by (n-1)/sqrt(n), so an in-sample z > 3
    test cannot fire at all below eleven transactions.
    """
    hits: list[RuleHit] = []
    for cid, items in ctx.by_customer.items():
        if len(items) < 4:
            continue
        for t in items:
            others = [o.amount for o in items if o.id != t.id]
            mean_o = statistics.fmean(others)
            sd_o = statistics.pstdev(others)

            if sd_o > 0:
                z = (t.amount - mean_o) / sd_o
                if z <= 3:
                    continue
                score = _clamp((z - 3) / 5)
                detail = f"{z:.1f} standard deviations above"
            else:
                # Every other amount is identical, so there is no spread to
                # measure against. Fall back to a plain multiple of the baseline.
                ratio = t.amount / mean_o if mean_o else 0.0
                if ratio < 5:
                    continue
                score = _clamp((ratio - 5) / 10)
                detail = f"{ratio:.0f}x"

            hits.append(RuleHit(
                rule="amount_zscore",
                label="Amount far outside customer baseline",
                score=score,
                # Below the flag threshold on purpose. A single unusually large
                # purchase is a routine event - a laptop, a flight, a deposit -
                # and opening a case on it alone is a false-positive machine.
                # It should raise an existing case's score, not create one.
                weight=0.45,
                explanation=(
                    f"Transaction of {t.amount:,.2f} USD is {detail} customer {cid}'s "
                    f"baseline of {mean_o:,.2f} USD (computed excluding this transaction)."
                ),
                tx_ids=(t.id,),
            ))
    return hits


def rule_shared_ip_ring(ctx: Context) -> list[RuleHit]:
    """Looser than the device rule: households and NAT legitimately share an IP."""
    hits: list[RuleHit] = []
    for ip, items in ctx.by_ip.items():
        if len(items) > HUB_MAX_IP:
            continue
        customers = {t.customer_id for t in items}
        if len(customers) < 3:
            continue
        hits.append(RuleHit(
            rule="shared_ip_ring",
            label="Shared IP across customers",
            score=_clamp((len(customers) - 2) / 3),
            weight=0.55,
            explanation=(
                f"IP {ip} served {len(customers)} distinct customers "
                f"across {len(items)} transactions."
            ),
            tx_ids=tuple(t.id for t in items),
        ))
    return hits


def rule_new_merchant_burst(ctx: Context) -> list[RuleHit]:
    hits: list[RuleHit] = []
    for cid, items in ctx.by_customer.items():
        seen: set[str] = set()
        firsts = []
        for t in items:
            if t.merchant_id not in seen:
                seen.add(t.merchant_id)
                firsts.append(t)
        if len(firsts) < 3:
            continue
        left = 0
        best: list = []
        for right in range(len(firsts)):
            while (
                firsts[right].timestamp - firsts[left].timestamp
            ).total_seconds() > NEW_MERCHANT_WINDOW_MIN * 60:
                left += 1
            window = firsts[left:right + 1]
            if len(window) > len(best):
                best = window
        if len(best) < 3:
            continue
        hits.append(RuleHit(
            rule="new_merchant_burst",
            label="Burst of first-time merchants",
            score=_clamp((len(best) - 2) / 4),
            weight=0.45,
            explanation=(
                f"Customer {cid} transacted with {len(best)} merchants never seen before "
                f"within {NEW_MERCHANT_WINDOW_MIN} minutes."
            ),
            tx_ids=tuple(t.id for t in best),
        ))
    return hits


def rule_off_hours(ctx: Context) -> list[RuleHit]:
    """Weak on its own by design - 0.25 cannot clear the 0.5 flag threshold."""
    hits: list[RuleHit] = []
    for t in ctx.txs:
        if t.timestamp.hour not in (1, 2, 3, 4):
            continue
        hits.append(RuleHit(
            rule="off_hours",
            label="Off-hours activity",
            score=1.0,
            weight=0.25,
            explanation=(
                f"Transaction posted at {t.timestamp.strftime('%H:%M')} UTC, "
                f"inside the 01:00-05:00 low-activity window."
            ),
            tx_ids=(t.id,),
        ))
    return hits


# ------------------------------------------------------------------------ registry

ALL_RULES: list[Callable[[Context], list[RuleHit]]] = [
    rule_shared_device_ring,
    rule_impossible_travel,
    rule_card_testing,
    rule_structuring,
    rule_rapid_escalation,
    rule_velocity,
    rule_amount_zscore,
    rule_shared_ip_ring,
    rule_new_merchant_burst,
    rule_off_hours,
]

RULE_META: dict[str, dict] = {
    "rule_shared_device_ring": {
        "rule": "shared_device_ring",
        "label": "Shared device across customers",
        "weight": 0.85,
        "description": (
            "One device fingerprint used by two or more customers. Devices with more "
            f"than {HUB_MAX_DEVICE} transactions are treated as shared terminals and skipped."
        ),
    },
    "rule_impossible_travel": {
        "rule": "impossible_travel",
        "label": "Geographically impossible sequence",
        "weight": 0.90,
        "description": (
            "Consecutive transactions by one customer in different countries less than "
            "four hours apart. Full score under one hour, decaying to zero at four."
        ),
    },
    "rule_card_testing": {
        "rule": "card_testing",
        "label": "Card testing followed by cash-out",
        "weight": 0.80,
        "description": (
            f"Three or more transactions under {CARD_TEST_PROBE_MAX:.0f} USD followed within "
            f"{CARD_TEST_WINDOW_MIN} minutes by a charge of at least "
            f"{CARD_TEST_CASHOUT_MIN:.0f} USD."
        ),
    },
    "rule_structuring": {
        "rule": "structuring",
        "label": "Amounts just under a reporting threshold",
        "weight": 0.75,
        "description": (
            f"Three or more transactions between {STRUCTURING_LOW:,.0f} and "
            f"{STRUCTURING_HIGH:,.0f} USD by one customer within 24 hours."
        ),
    },
    "rule_rapid_escalation": {
        "rule": "rapid_escalation",
        "label": "Escalating amounts at one merchant",
        "weight": 0.70,
        "description": (
            "Strictly increasing amounts at one merchant with gaps under "
            f"{ESCALATION_GAP_MIN} minutes, ending at least double where they started."
        ),
    },
    "rule_velocity": {
        "rule": "velocity",
        "label": "Abnormal transaction velocity",
        "weight": 0.65,
        "description": (
            f"More than {VELOCITY_BASELINE} transactions by one customer inside any "
            f"{VELOCITY_WINDOW_MIN}-minute sliding window."
        ),
    },
    "rule_amount_zscore": {
        "rule": "amount_zscore",
        "label": "Amount far outside customer baseline",
        "weight": 0.45,
        "description": (
            "Amount more than three standard deviations above the customer's own baseline, "
            "computed leave-one-out so a large transaction cannot mask itself by inflating "
            "the statistics it is measured against. Needs four transactions of history. "
            "Weighted below the flag threshold: a large purchase alone is not a case."
        ),
    },
    "rule_shared_ip_ring": {
        "rule": "shared_ip_ring",
        "label": "Shared IP across customers",
        "weight": 0.55,
        "description": (
            "One IP serving three or more customers. Looser than the device rule because "
            f"households and NAT legitimately share addresses. Skipped above {HUB_MAX_IP} "
            "transactions."
        ),
    },
    "rule_new_merchant_burst": {
        "rule": "new_merchant_burst",
        "label": "Burst of first-time merchants",
        "weight": 0.45,
        "description": (
            "Three or more never-before-seen merchants for one customer within "
            f"{NEW_MERCHANT_WINDOW_MIN} minutes."
        ),
    },
    "rule_off_hours": {
        "rule": "off_hours",
        "label": "Off-hours activity",
        "weight": 0.25,
        "description": (
            "Transaction between 01:00 and 05:00 UTC. Deliberately weak: it cannot clear "
            "the flag threshold alone and only matters alongside other evidence."
        ),
    },
}
