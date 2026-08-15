"""Measure the detector against the labelled demo dataset.

Prints a markdown threshold sweep and a per-ring breakdown. The output goes
verbatim into the README, so keep it copy-pasteable.

    python scripts/evaluate.py
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from backend.engine.detector import FraudDetector  # noqa: E402
from backend.models import Transaction  # noqa: E402

DATA = pathlib.Path(__file__).resolve().parent.parent / "data"
THRESHOLDS = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]


def _f1(precision: float, recall: float) -> float:
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)


def main() -> None:
    txs = [Transaction(**t) for t in json.loads((DATA / "demo_transactions.json").read_text())]
    truth: dict[str, str] = json.loads((DATA / "ground_truth.json").read_text())
    fraud = {k for k, v in truth.items() if v != "clean"}

    print(f"Dataset: {len(txs)} transactions, {len(fraud)} fraudulent "
          f"({len(fraud) / len(txs):.1%}) across 4 injected rings.\n")

    print("| Threshold | Flagged | Precision | Recall |    F1 | Cases |")
    print("|-----------|---------|-----------|--------|-------|-------|")

    for th in THRESHOLDS:
        result = FraudDetector(threshold=th).analyze(txs)
        flagged = {t.id for c in result.cases for t in c.transactions}
        tp = len(flagged & fraud)
        precision = tp / len(flagged) if flagged else 0.0
        recall = tp / len(fraud)
        print(f"| {th:>9.2f} | {len(flagged):>7} | {precision:>9.3f} | "
              f"{recall:>6.3f} | {_f1(precision, recall):>5.3f} | {len(result.cases):>5} |")

    default = FraudDetector()
    result = default.analyze(txs)
    flagged = {t.id for c in result.cases for t in c.transactions}

    print(f"\nPer-ring detection at the default threshold of {default.threshold}:\n")
    print("| Ring | Injected | Detected | Recall |")
    print("|------|----------|----------|--------|")
    for ring in ("ring_device", "ring_card_testing", "ring_travel", "ring_structuring"):
        members = {k for k, v in truth.items() if v == ring}
        hit = len(members & flagged)
        print(f"| `{ring}` | {len(members)} | {hit} | {hit / len(members):.0%} |")

    fp = sorted(flagged - fraud)
    print(f"\nFalse positives: {len(fp)}" + (f" ({', '.join(fp[:10])})" if fp else ""))
    missed = sorted(fraud - flagged)
    print(f"False negatives: {len(missed)}" + (f" ({', '.join(missed[:10])})" if missed else ""))

    print("\nCases opened:\n")
    print("| Case | Risk | Severity | Transactions | Total | Top signal |")
    print("|------|------|----------|--------------|-------|------------|")
    for c in result.cases:
        top = c.signals[0].label if c.signals else "-"
        print(f"| `{c.case_id}` | {c.risk_score:.3f} | {c.severity} | "
              f"{len(c.transactions)} | {c.total_amount:,.2f} | {top} |")


if __name__ == "__main__":
    main()
