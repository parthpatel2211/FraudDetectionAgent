import json
import pathlib

import pytest
from fastmcp.exceptions import ToolError

from backend import mcp_server

DATA = pathlib.Path(__file__).resolve().parent.parent / "data"


@pytest.fixture(scope="module")
def raw_transactions():
    return json.loads((DATA / "demo_transactions.json").read_text())


def test_analyze_returns_result_shape(raw_transactions):
    out = mcp_server.analyze_transactions(raw_transactions)
    assert set(out) >= {"cases", "transactions_analyzed", "transactions_flagged", "threshold"}
    assert out["transactions_analyzed"] == len(raw_transactions)
    assert out["cases"]


def test_analyze_output_is_json_serializable(raw_transactions):
    """MCP transports JSON; a stray datetime would break the tool call."""
    json.dumps(mcp_server.analyze_transactions(raw_transactions))


def test_invalid_transaction_raises_rather_than_silently_skipping():
    """The v1 bug: a bad row was dropped with `continue` and never surfaced."""
    with pytest.raises(ToolError) as e:
        mcp_server.analyze_transactions([{"id": "broken"}])
    msg = str(e.value)
    assert "0" in msg  # names the offending index
    assert "broken" in msg or "valid" in msg.lower()


def test_invalid_row_among_valid_rows_still_raises(raw_transactions):
    payload = raw_transactions[:5] + [{"id": "bad"}]
    with pytest.raises(ToolError) as e:
        mcp_server.analyze_transactions(payload)
    assert "5" in str(e.value)


def test_analyze_rejects_non_list():
    with pytest.raises(ToolError):
        mcp_server.analyze_transactions({"not": "a list"})


def test_analyze_rejects_oversized_batch(monkeypatch):
    monkeypatch.setattr(mcp_server, "MAX_TRANSACTIONS", 3)
    with pytest.raises(ToolError) as e:
        mcp_server.analyze_transactions([{"id": str(i)} for i in range(10)])
    assert "limit" in str(e.value).lower()


def test_analyze_empty_list_is_valid():
    out = mcp_server.analyze_transactions([])
    assert out["cases"] == [] and out["transactions_analyzed"] == 0


def test_summarize_case_roundtrip(raw_transactions):
    case = mcp_server.analyze_transactions(raw_transactions)["cases"][0]
    out = mcp_server.summarize_case(case)
    assert out["narrative"] and out["recommendation"] and out["next_steps"]
    assert out["source"] in {"llm", "template"}


def test_summarize_rejects_garbage():
    with pytest.raises(ToolError):
        mcp_server.summarize_case({"case_id": "nope"})


def test_summarize_rejects_non_dict():
    with pytest.raises(ToolError):
        mcp_server.summarize_case("a string")


def test_load_demo_dataset_returns_transactions():
    out = mcp_server.load_demo_dataset()
    assert len(out["transactions"]) > 100
    assert out["count"] == len(out["transactions"])


def test_explain_rules_lists_all_ten():
    rules = mcp_server.explain_rules()["rules"]
    assert len(rules) == 10
    assert all({"rule", "label", "weight", "description"} <= set(r) for r in rules)


def test_explain_rules_matches_the_engine():
    from backend.engine.rules import RULE_META
    names = {r["rule"] for r in mcp_server.explain_rules()["rules"]}
    assert names == {m["rule"] for m in RULE_META.values()}


def test_explain_rules_reports_the_threshold():
    out = mcp_server.explain_rules()
    assert out["risk_threshold"] == 0.5
    assert "noisy-OR" in out["aggregation"] or "noisy_or" in out["aggregation"]


def test_every_tool_is_registered_with_fastmcp():
    """A function that isn't registered is invisible to Claude."""
    import asyncio
    registered = set(asyncio.run(mcp_server.mcp.get_tools()))
    assert registered == {
        "analyze_transactions", "summarize_case", "load_demo_dataset", "explain_rules",
    }


def test_registered_tools_match_the_declared_list():
    import asyncio
    registered = set(asyncio.run(mcp_server.mcp.get_tools()))
    assert registered == {fn.__name__ for fn in mcp_server.TOOLS}


def test_every_tool_has_a_docstring():
    """Docstrings become the tool descriptions Claude reads to choose a tool."""
    for fn in mcp_server.TOOLS:
        assert fn.__doc__ and len(fn.__doc__.strip()) > 60, fn.__name__


def test_registered_descriptions_are_populated():
    import asyncio
    tools = asyncio.run(mcp_server.mcp.get_tools())
    for name, tool in tools.items():
        assert tool.description and len(tool.description.strip()) > 60, name
