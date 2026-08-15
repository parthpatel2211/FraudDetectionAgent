import json
import pathlib

import pytest

from backend.app import create_app

DATA = pathlib.Path(__file__).resolve().parent.parent / "data"


@pytest.fixture(scope="module")
def raw_transactions():
    return json.loads((DATA / "demo_transactions.json").read_text())


@pytest.fixture
def client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


# ------------------------------------------------------------------------ health

def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.get_json()
    assert body["status"] == "ok"
    assert "llm" in body and isinstance(body["llm"], bool)
    assert body["threshold"] == 0.5


def test_demo_returns_transactions(client):
    r = client.get("/api/demo")
    assert r.status_code == 200
    assert len(r.get_json()["transactions"]) > 100


# ----------------------------------------------------------------------- analyze

def test_analyze_bare_array(client, raw_transactions):
    r = client.post("/api/analyze", json=raw_transactions)
    assert r.status_code == 200
    body = r.get_json()
    assert body["transactions_analyzed"] == len(raw_transactions)
    assert isinstance(body["cases"], list) and body["cases"]


def test_analyze_wrapped_object(client, raw_transactions):
    r = client.post("/api/analyze", json={"transactions": raw_transactions[:50]})
    assert r.status_code == 200


def test_analyze_empty_array_is_valid(client):
    r = client.post("/api/analyze", json=[])
    assert r.status_code == 200
    assert r.get_json()["cases"] == []


def test_analyze_response_is_json_serializable(client, raw_transactions):
    """Timestamps must serialize; a datetime leaking through would 500."""
    r = client.post("/api/analyze", json=raw_transactions)
    case = r.get_json()["cases"][0]
    assert isinstance(case["transactions"][0]["timestamp"], str)
    assert case["graph"]["nodes"] and case["graph"]["edges"]


def test_analyze_rejects_non_list(client):
    r = client.post("/api/analyze", json={"nope": 1})
    assert r.status_code == 400
    assert "error" in r.get_json()


def test_analyze_rejects_invalid_transaction(client):
    r = client.post("/api/analyze", json=[{"id": "x"}])
    assert r.status_code == 400
    assert r.get_json()["details"]


def test_analyze_rejects_list_of_non_objects(client):
    r = client.post("/api/analyze", json=["not", "objects"])
    assert r.status_code == 400


def test_analyze_rejects_garbage_body(client):
    r = client.post("/api/analyze", data="not json", content_type="application/json")
    assert r.status_code == 400


def test_analyze_rejects_oversized_batch(client, monkeypatch):
    from backend import app as app_mod
    monkeypatch.setattr(app_mod, "MAX_TRANSACTIONS", 3)
    r = client.post("/api/analyze", json=[{"id": str(i)} for i in range(10)])
    assert r.status_code == 413
    assert "limit" in r.get_json()["error"].lower()


# --------------------------------------------------------------------- summarize

def test_summarize_roundtrip(client, raw_transactions):
    """A case emitted by /analyze must be accepted by /summarize unchanged."""
    cases = client.post("/api/analyze", json=raw_transactions).get_json()["cases"]
    r = client.post("/api/summarize", json=cases[0])
    assert r.status_code == 200
    body = r.get_json()
    assert body["narrative"] and body["recommendation"] and body["next_steps"]
    assert body["source"] in {"llm", "template"}
    assert body["case_id"] == cases[0]["case_id"]


def test_summarize_rejects_a_bare_string_without_500(client):
    r = client.post("/api/summarize", json="a string, not a case")
    assert r.status_code == 400


def test_summarize_rejects_a_list_without_500(client):
    r = client.post("/api/summarize", json=[1, 2, 3])
    assert r.status_code == 400


def test_summarize_rejects_incomplete_case(client):
    r = client.post("/api/summarize", json={"case_id": "CASE-1"})
    assert r.status_code == 400
    assert r.get_json()["details"]


def test_summarize_rate_limit_degrades_to_template(client, raw_transactions, monkeypatch):
    """Over budget must return a usable summary, not an error."""
    from backend import app as app_mod
    from backend.ratelimit import RateLimiter

    monkeypatch.setattr(app_mod, "limiter", RateLimiter(per_minute=1))
    monkeypatch.setattr(app_mod, "LLM_ENABLED", True)

    case = client.post("/api/analyze", json=raw_transactions).get_json()["cases"][0]
    first = client.post("/api/summarize", json=case)
    second = client.post("/api/summarize", json=case)

    assert first.status_code == 200 and second.status_code == 200
    assert second.get_json()["rate_limited"] is True
    assert second.get_json()["source"] == "template"
    assert second.get_json()["narrative"]


def test_rate_limit_not_applied_when_llm_disabled(client, raw_transactions, monkeypatch):
    """Template summaries are free, so never ration them."""
    from backend import app as app_mod
    from backend.ratelimit import RateLimiter

    monkeypatch.setattr(app_mod, "limiter", RateLimiter(per_minute=1))
    monkeypatch.setattr(app_mod, "LLM_ENABLED", False)

    case = client.post("/api/analyze", json=raw_transactions).get_json()["cases"][0]
    for _ in range(3):
        body = client.post("/api/summarize", json=case).get_json()
        assert "rate_limited" not in body


# -------------------------------------------------------------------- misc/infra

def test_unknown_route_returns_json_404_not_html(client):
    r = client.get("/api/nope")
    assert r.status_code == 404
    assert r.is_json


def test_wrong_method_returns_json_405(client):
    r = client.get("/api/analyze")
    assert r.status_code == 405
    assert r.is_json


def test_no_cors_header_by_default(client):
    """Same-origin in production; the Vite proxy covers dev."""
    r = client.get("/api/health")
    assert "Access-Control-Allow-Origin" not in r.headers
