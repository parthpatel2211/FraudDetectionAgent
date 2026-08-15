"""Fraud engine exposed as an MCP server.

Lets Claude investigate cases conversationally: load a dataset, analyze it,
inspect why the detector fired, and write up the case. It wraps the exact same
FraudDetector and narrative code the HTTP API uses - no duplicated logic, so
the two surfaces can never disagree.

v1 caught ValidationError per row and `continue`d, so a malformed transaction
was silently dropped and the caller was told nothing: the analysis just quietly
covered fewer rows than were sent. Every tool here raises ToolError naming the
offending index instead.

Run locally:

    fastmcp run backend/mcp_server.py

fastmcp is a dev-only dependency and never ships to the serverless bundle.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import ValidationError

from backend.config import settings
from backend.engine.detector import FraudDetector
from backend.engine.rules import RULE_META
from backend.engine.scoring import CRITICAL, HIGH, MEDIUM
from backend.models import Case, Transaction
from backend.narrative.llm import summarize

DATA_DIR = pathlib.Path(__file__).resolve().parent.parent / "data"
MAX_TRANSACTIONS = settings.MAX_TRANSACTIONS_PER_REQUEST

mcp = FastMCP("fraud-investigation-agent")
detector = FraudDetector()


def analyze_transactions(transactions: list[dict[str, Any]]) -> dict[str, Any]:
    """Run fraud detection over a batch of transactions and return the cases found.

    Scores every transaction against ten explainable rules, groups the flagged
    ones into cases using a shared-attribute similarity graph, and returns each
    case with its risk score, contributing signals, and the evidence behind them.

    Args:
        transactions: Transaction objects. Required fields: id, customer_id,
            account_id, merchant_id, amount, timestamp. Optional: device_id,
            ip_address, currency, channel (WEB/MOBILE/POS/ATM/TRANSFER), country.

    Returns:
        cases (each with case_id, risk_score, severity, signals, transactions,
        graph), plus transactions_analyzed, transactions_flagged, and the
        threshold used. An empty cases list means the batch looks clean - that
        is a real result, not a failure.

    Raises:
        ToolError: if the input is not a list, exceeds the batch limit, or any
            transaction fails validation. Invalid rows are never skipped
            silently - the error names the offending index.
    """
    if not isinstance(transactions, list):
        raise ToolError(f"Expected a list of transactions, got {type(transactions).__name__}.")

    if len(transactions) > MAX_TRANSACTIONS:
        raise ToolError(
            f"Batch of {len(transactions)} exceeds the {MAX_TRANSACTIONS} transaction limit."
        )

    parsed: list[Transaction] = []
    for index, item in enumerate(transactions):
        if not isinstance(item, dict):
            raise ToolError(
                f"Transaction at index {index} is a {type(item).__name__}, not an object."
            )
        try:
            parsed.append(Transaction(**item))
        except ValidationError as exc:
            raise ToolError(
                f"Transaction at index {index} (id={item.get('id', '<missing>')!r}) "
                f"is not valid: {exc.errors()}"
            ) from exc

    return detector.analyze(parsed).model_dump(mode="json")


def summarize_case(case: dict[str, Any]) -> dict[str, Any]:
    """Write an investigator-ready narrative for one fraud case.

    Produces a plain-language account of what happened, a recommended
    disposition, and concrete next steps scaled to the case severity. Uses
    Claude when an API key is configured and a deterministic template
    otherwise; the `source` field says which produced this summary.

    Args:
        case: A case object exactly as returned by analyze_transactions - pass
            one straight through without reshaping it.

    Returns:
        case_id, narrative, recommendation, next_steps, and source
        ("llm" or "template").

    Raises:
        ToolError: if the object is not a valid case.
    """
    if not isinstance(case, dict):
        raise ToolError(f"Expected a case object, got {type(case).__name__}.")
    try:
        parsed = Case(**case)
    except ValidationError as exc:
        raise ToolError(f"Not a valid case object: {exc.errors()}") from exc

    return summarize(parsed).model_dump(mode="json")


def load_demo_dataset() -> dict[str, Any]:
    """Load the bundled synthetic dataset for demonstration and testing.

    470 transactions across 40 customers over 14 days, with four fraud rings
    deliberately injected: a shared device used by three customers, a
    card-testing sequence, an impossible-travel pattern, and a run of
    structured transfers just under a reporting threshold. Feed the result
    straight into analyze_transactions.

    Returns:
        transactions (the list) and count.
    """
    payload = json.loads((DATA_DIR / "demo_transactions.json").read_text())
    return {"transactions": payload, "count": len(payload)}


def explain_rules() -> dict[str, Any]:
    """Describe the detection rules, their weights, and how scores combine.

    Use this to explain why a case scored the way it did, or to answer
    questions about what the detector can and cannot catch.

    Returns:
        rules (rule, label, weight, description for each of the ten),
        the aggregation formula, the flag threshold, and the severity bands.
        Weight is a rule's maximum contribution to a transaction's risk; rules
        weighted below the threshold cannot open a case on their own.
    """
    return {
        "rules": [
            {
                "rule": meta["rule"],
                "label": meta["label"],
                "weight": meta["weight"],
                "description": meta["description"],
            }
            for meta in sorted(RULE_META.values(), key=lambda m: -m["weight"])
        ],
        "aggregation": (
            "Risk is combined with noisy-OR: risk = 1 - product(1 - weight * score) "
            "over every rule that fired. The result is absolute and bounded in [0, 1], "
            "so a score means the same thing regardless of what else was in the batch."
        ),
        "risk_threshold": settings.RISK_THRESHOLD,
        "severity_bands": {
            "critical": f">= {CRITICAL}",
            "high": f">= {HIGH}",
            "medium": f">= {MEDIUM}",
            "low": f"< {MEDIUM}",
        },
    }


# Registered explicitly rather than via @mcp.tool so the module stays a normal
# importable Python module: the decorator replaces each name with a FunctionTool
# wrapper, which is not callable and makes the functions awkward to test or reuse.
TOOLS = (analyze_transactions, summarize_case, load_demo_dataset, explain_rules)
for _tool in TOOLS:
    mcp.tool(_tool)


if __name__ == "__main__":
    mcp.run()
