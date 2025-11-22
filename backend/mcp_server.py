from __future__ import annotations

from typing import List, Dict, Any

from fastmcp import FastMCP
from pydantic import ValidationError

from fraud_agent import FraudDetectionEngine
from models import Transaction, Case

mcp = FastMCP("fraud-investigation-agent")
engine = FraudDetectionEngine()


@mcp.tool
def analyze_transactions(transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Run fraud analysis on a batch of transactions and return detected fraud cases.

    Args:
        transactions: List of transaction objects with fields compatible with models.Transaction.

    Returns:
        List of fraud cases with risk scores, graph-based signals and transaction details.
    """
    tx_objs: List[Transaction] = []
    for t in transactions:
        try:
            tx_objs.append(Transaction(**t))
        except ValidationError as e:
            # In production you might raise fastmcp.ToolError; here we return partial results
            continue

    cases = engine.analyze_transactions(tx_objs)
    return [c.model_dump() for c in cases]


@mcp.tool
def summarize_case(case: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate an investigator-ready natural language summary for a fraud case.

    Args:
        case: A single case object (compatible with models.Case).

    Returns:
        Dict with `narrative` and `recommendation` plus the normalized case.
    """
    case_obj = Case(**case)
    summary = engine.summarize_case(case_obj)
    return summary.model_dump()


if __name__ == "__main__":
    # Run with: `fastmcp run backend/mcp_server.py`
    mcp.run()
