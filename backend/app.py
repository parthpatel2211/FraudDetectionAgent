from __future__ import annotations

import logging
from typing import List

from flask import Flask, jsonify, request
from flask_cors import CORS
from pydantic import ValidationError

from config import settings
from fraud_agent import FraudDetectionEngine
from models import Transaction, Case, CaseSummary

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

engine = FraudDetectionEngine()


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app)

    @app.route("/health", methods=["GET"])
    def health() -> tuple[dict, int]:
        return {"status": "ok"}, 200

    @app.route("/api/transactions/analyze", methods=["POST"])
    def analyze_transactions() -> tuple[dict, int]:
        try:
            payload = request.get_json(force=True)
            if not isinstance(payload, list):
                return {"error": "Expected a JSON array of transactions"}, 400

            txs: List[Transaction] = [Transaction(**item) for item in payload]
        except ValidationError as e:
            return {"error": "Invalid transaction payload", "details": e.errors()}, 400
        except Exception as e:
            logger.exception("Failed to parse request")
            return {"error": "Malformed request", "details": str(e)}, 400

        cases: List[Case] = engine.analyze_transactions(txs)
        return jsonify([c.model_dump() for c in cases]), 200

    @app.route("/api/cases/summary", methods=["POST"])
    def summarize_case() -> tuple[dict, int]:
        try:
            payload = request.get_json(force=True)
            case = Case(**payload)
        except ValidationError as e:
            logger.error("Case validation failed: %s", e.json())
            return {"error": "Invalid case payload", "details": e.errors()}, 400

        summary: CaseSummary = engine.summarize_case(case)
        return jsonify(summary.model_dump()), 200

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host=settings.HOST, port=settings.PORT, debug=settings.DEBUG)
