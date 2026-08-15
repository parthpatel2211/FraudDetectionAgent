"""Risk aggregation.

The v1 engine scored a case as `component_mean / batch_max`, which made every
score relative to whatever else happened to be in the request. The highest-risk
case always landed near 1.0 and the UI always read "Critical", regardless of
how suspicious the batch actually was.

Noisy-OR fixes that. Each rule hit is treated as independent evidence with its
own failure probability, so the combined score is absolute, bounded in [0, 1],
and monotone: adding evidence can never lower a score, and no amount of weak
evidence can saturate it the way a sum would.

    risk = 1 - product(1 - weight_i * score_i)
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from backend.engine.context import Context
from backend.engine.rules import ALL_RULES, RuleHit

CRITICAL = 0.85
HIGH = 0.65
MEDIUM = 0.40


def noisy_or(hits: Sequence[RuleHit]) -> float:
    survival = 1.0
    for h in hits:
        survival *= 1.0 - (h.weight * h.score)
    return round(1.0 - survival, 6)


def severity(score: float) -> str:
    if score >= CRITICAL:
        return "critical"
    if score >= HIGH:
        return "high"
    if score >= MEDIUM:
        return "medium"
    return "low"


def score_transactions(ctx: Context) -> tuple[dict[str, float], dict[str, list[RuleHit]]]:
    """Return per-transaction risk and the hits that produced it.

    Every transaction in the batch appears in the score map, scoring 0.0 when
    no rule touched it, so callers never have to distinguish "clean" from
    "missing".
    """
    hits_by_tx: dict[str, list[RuleHit]] = defaultdict(list)
    for rule in ALL_RULES:
        for h in rule(ctx):
            for tid in h.tx_ids:
                hits_by_tx[tid].append(h)

    scores = {t.id: 0.0 for t in ctx.txs}
    for tid, hits in hits_by_tx.items():
        scores[tid] = noisy_or(hits)
    return scores, dict(hits_by_tx)
