"""HTTP surface.

Hardened against the ways v1 could be made to return a 500 or exhaust memory:
every handler validates its own body shape before touching the engine, there is
a hard cap on batch size, and the error handlers return JSON rather than
Flask's HTML error pages (a JSON client parsing an HTML 404 is its own bug).
"""

from __future__ import annotations

import json
import logging
import pathlib

from flask import Flask, jsonify, request
from flask_cors import CORS
from pydantic import ValidationError

from backend.config import settings
from backend.engine.detector import FraudDetector
from backend.models import Case, Transaction
from backend.narrative.llm import summarize
from backend.narrative.template import render_template
from backend.ratelimit import RateLimiter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_DIR = pathlib.Path(__file__).resolve().parent.parent / "data"
MAX_BODY_BYTES = 16 * 1024 * 1024

# Module-level so tests can monkeypatch them without rebuilding the app.
MAX_TRANSACTIONS = settings.MAX_TRANSACTIONS_PER_REQUEST
LLM_ENABLED = bool(settings.ANTHROPIC_API_KEY)

detector = FraudDetector()          # stateless; safe to share across requests
limiter = RateLimiter(settings.LLM_RATE_LIMIT_PER_MINUTE)


def _client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    return forwarded.split(",")[0].strip() or request.remote_addr or "unknown"


def _errors(exc: Exception) -> list[dict]:
    return exc.errors() if isinstance(exc, ValidationError) else [{"msg": str(exc)}]


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_BODY_BYTES

    # Same-origin in production (SPA and API share the Vercel domain) and the
    # Vite proxy covers local dev, so CORS is opt-in via ALLOWED_ORIGINS only.
    if settings.ALLOWED_ORIGINS:
        CORS(app, resources={r"/api/*": {"origins": settings.ALLOWED_ORIGINS}})

    @app.errorhandler(404)
    def not_found(_):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(405)
    def bad_method(_):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(413)
    def too_large(_):
        return jsonify({"error": "Request body too large"}), 413

    @app.errorhandler(Exception)
    def unhandled(exc):
        logger.exception("Unhandled error")
        return jsonify({"error": "Internal server error"}), 500

    @app.get("/api/health")
    def health():
        return jsonify({
            "status": "ok",
            "llm": LLM_ENABLED,
            "model": settings.ANTHROPIC_MODEL if LLM_ENABLED else None,
            "threshold": settings.RISK_THRESHOLD,
            "max_transactions": MAX_TRANSACTIONS,
        })

    @app.get("/api/demo")
    def demo():
        payload = json.loads((DATA_DIR / "demo_transactions.json").read_text())
        return jsonify({"transactions": payload})

    @app.post("/api/analyze")
    def analyze():
        payload = request.get_json(silent=True)
        if payload is None:
            return jsonify({"error": "Body must be valid JSON"}), 400

        if isinstance(payload, dict):
            payload = payload.get("transactions")
        if not isinstance(payload, list):
            return jsonify({
                "error": "Expected a JSON array of transactions, or an object "
                         "with a 'transactions' array"
            }), 400

        # Checked before parsing so an oversized batch costs no work.
        if len(payload) > MAX_TRANSACTIONS:
            return jsonify({
                "error": f"Batch exceeds the {MAX_TRANSACTIONS} transaction limit "
                         f"({len(payload)} received)"
            }), 413

        try:
            txs = [Transaction(**item) for item in payload]
        except (ValidationError, TypeError) as e:
            return jsonify({
                "error": "Invalid transaction payload", "details": _errors(e),
            }), 400

        result = detector.analyze(txs)
        return jsonify(result.model_dump(mode="json")), 200

    @app.post("/api/summarize")
    def summarize_case():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "Body must be a case object"}), 400

        try:
            case = Case(**payload)
        except (ValidationError, TypeError) as e:
            return jsonify({
                "error": "Invalid case payload", "details": _errors(e),
            }), 400

        # Only ration the paid path. Template summaries cost nothing.
        if LLM_ENABLED and not limiter.allow(_client_ip()):
            body = render_template(case).model_dump(mode="json")
            body["rate_limited"] = True
            return jsonify(body), 200

        return jsonify(summarize(case).model_dump(mode="json")), 200

    return app


if __name__ == "__main__":
    create_app().run(host=settings.HOST, port=settings.PORT, debug=settings.DEBUG)
