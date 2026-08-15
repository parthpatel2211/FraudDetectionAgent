"""Batch orchestrator: transactions in, cases out.

Stateless by design. v1 held a fitted IsolationForest on the instance behind a
`_fitted` flag, so the first request a process ever served permanently defined
the model, later batches were scored against a stale fit, and a batch
introducing a new channel changed the one-hot feature width and crashed
score_samples outright. Nothing here is retained between calls.
"""

from __future__ import annotations

import hashlib

from backend.config import settings
from backend.engine.context import Context
from backend.engine.graph import build_similarity_graph, cluster, to_case_graph
from backend.engine.rules import RuleHit
from backend.engine.scoring import noisy_or, score_transactions, severity
from backend.models import AnalysisResult, Case, Signal, Transaction


class FraudDetector:
    """Safe to construct once at import and share across requests and threads."""

    def __init__(self, threshold: float | None = None) -> None:
        self.threshold = settings.RISK_THRESHOLD if threshold is None else threshold

    def analyze(self, txs: list[Transaction]) -> AnalysisResult:
        if not txs:
            return AnalysisResult(
                cases=[], transactions_analyzed=0,
                transactions_flagged=0, threshold=self.threshold,
            )

        ctx = Context.build(txs)
        scores, hits_by_tx = score_transactions(ctx)

        flagged = [t for t in ctx.txs if scores[t.id] >= self.threshold]
        if not flagged:
            return AnalysisResult(
                cases=[], transactions_analyzed=len(txs),
                transactions_flagged=0, threshold=self.threshold,
            )

        g = build_similarity_graph(flagged)
        by_id = {t.id: t for t in flagged}

        cases: list[Case] = []
        for member_ids in cluster(g):
            members = [by_id[i] for i in sorted(member_ids) if i in by_id]
            if not members:
                continue

            case_hits = self._collect_hits(members, hits_by_tx)
            risk = noisy_or(case_hits)
            sub = g.subgraph(member_ids)

            cases.append(Case(
                case_id=self._case_id(member_ids),
                customer_ids=sorted({t.customer_id for t in members}),
                account_ids=sorted({t.account_id for t in members}),
                transactions=members,
                risk_score=risk,
                severity=severity(risk),
                total_amount=round(sum(t.amount for t in members), 2),
                signals=self._to_signals(case_hits, set(member_ids)),
                graph=to_case_graph(members, scores, sub),
            ))

        cases.sort(key=lambda c: (-c.risk_score, c.case_id))
        return AnalysisResult(
            cases=cases,
            transactions_analyzed=len(txs),
            transactions_flagged=len(flagged),
            threshold=self.threshold,
        )

    @staticmethod
    def _collect_hits(
        members: list[Transaction], hits_by_tx: dict[str, list[RuleHit]]
    ) -> list[RuleHit]:
        """Deduplicate: one hit can implicate several transactions in the case."""
        seen: set[int] = set()
        out: list[RuleHit] = []
        for t in members:
            for h in hits_by_tx.get(t.id, []):
                if id(h) not in seen:
                    seen.add(id(h))
                    out.append(h)
        return out

    @staticmethod
    def _case_id(member_ids: set[str]) -> str:
        """Derived from membership, so the same ring keeps its id across runs."""
        digest = hashlib.sha1("|".join(sorted(member_ids)).encode()).hexdigest()
        return f"CASE-{digest[:10].upper()}"

    @staticmethod
    def _to_signals(hits: list[RuleHit], member_ids: set[str]) -> list[Signal]:
        """One signal per rule, aggregating every instance of that rule.

        A rule can fire several times in one case - once per customer in a ring,
        say. Displaying only the strongest instance while scoring all of them
        made the panel disagree with the score: the shared-device case showed
        evidence summing to 0.935 against a reported 0.981. Because noisy-OR is
        associative, folding each rule's instances into one contribution lets
        the displayed evidence reproduce the case score exactly.
        """
        grouped: dict[str, list[RuleHit]] = {}
        for h in hits:
            grouped.setdefault(h.rule, []).append(h)

        signals: list[Signal] = []
        for rule, rule_hits in grouped.items():
            strongest = max(rule_hits, key=lambda h: h.score)
            ids: set[str] = set()
            for h in rule_hits:
                ids |= set(h.tx_ids)

            signals.append(Signal(
                rule=rule,
                label=strongest.label,
                score=strongest.score,
                weight=strongest.weight,
                contribution=round(noisy_or(rule_hits), 4),
                instances=len(rule_hits),
                explanation=strongest.explanation,
                # Clipped to the case: a signal must not cite evidence the
                # analyst cannot see in front of them.
                tx_ids=sorted(ids & member_ids),
            ))

        signals.sort(key=lambda s: (-s.contribution, s.rule))
        return signals
