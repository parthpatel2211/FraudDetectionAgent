from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import List

import networkx as nx
import numpy as np
import pandas as pd
from openai import OpenAI
from sklearn.ensemble import IsolationForest

from config import settings
from models import Transaction, Case, FraudSignal, CaseSummary

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class FraudDetectionEngine:
    def __init__(self) -> None:
        self._clf = IsolationForest(
            n_estimators=200,
            contamination=0.02,
            random_state=42,
        )
        self._fitted = False
        self._client: OpenAI | None = None
        if settings.OPENAI_API_KEY:
            self._client = OpenAI(api_key=settings.OPENAI_API_KEY)

    # ---------- PUBLIC API ----------

    def analyze_transactions(self, txs: List[Transaction]) -> List[Case]:
        if not txs:
            return []

        df = self._to_dataframe(txs)
        features = self._build_features(df)

        if not self._fitted:
            logger.info("Fitting IsolationForest with initial batch")
            self._clf.fit(features)
            self._fitted = True

        anomaly_scores = -self._clf.score_samples(features)
        threshold = np.quantile(anomaly_scores, 0.98)

        df["anomaly_score"] = anomaly_scores
        df["is_anomaly"] = df["anomaly_score"] >= threshold

        anomalous = df[df["is_anomaly"]]
        if anomalous.empty:
            return []

        graph = self._build_graph(df)
        cases = self._cluster_to_cases(anomalous, graph, txs)
        return cases

    def summarize_case(self, case: Case) -> CaseSummary:
        narrative, recommendation = self._summarize_with_llm(case)
        return CaseSummary(case=case, narrative=narrative, recommendation=recommendation)

    # ---------- INTERNAL HELPERS ----------

    def _to_dataframe(self, txs: List[Transaction]) -> pd.DataFrame:
        data = []
        for t in txs:
            data.append(
                {
                    "id": t.id,
                    "customer_id": t.customer_id,
                    "account_id": t.account_id,
                    "merchant_id": t.merchant_id,
                    "device_id": t.device_id or "unknown_device",
                    "ip_address": t.ip_address or "unknown_ip",
                    "amount": t.amount,
                    "currency": t.currency,
                    "timestamp": t.timestamp,
                    "channel": t.channel,
                    "country": t.country or "unknown_country",
                }
            )
        df = pd.DataFrame(data)
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        return df

    def _build_features(self, df: pd.DataFrame) -> np.ndarray:
        # Basic numeric features; you can evolve this heavily in real use
        df = df.copy()
        df["hour"] = df["timestamp"].dt.hour
        # frequency per customer per hour
        freq = (
            df.groupby(["customer_id", df["timestamp"].dt.floor("1H")])["id"]
            .transform("count")
        )
        df["hourly_count"] = freq

        # Simple one-hot for channel (limit to top few)
        channels = pd.get_dummies(df["channel"], prefix="ch").astype(int)
        base = df[["amount", "hour", "hourly_count"]].astype(float)
        feat_df = pd.concat([base, channels], axis=1).fillna(0.0)
        return feat_df.values

    def _build_graph(self, df: pd.DataFrame) -> nx.Graph:
        g = nx.Graph()
        for _, row in df.iterrows():
            tx_node = f"tx:{row['id']}"
            cust_node = f"cust:{row['customer_id']}"
            acct_node = f"acct:{row['account_id']}"
            merch_node = f"merch:{row['merchant_id']}"
            dev_node = f"dev:{row['device_id']}"
            ip_node = f"ip:{row['ip_address']}"

            g.add_node(tx_node, type="transaction")
            # Edge types
            g.add_edge(tx_node, cust_node, type="customer")
            g.add_edge(tx_node, acct_node, type="account")
            g.add_edge(tx_node, merch_node, type="merchant")
            g.add_edge(tx_node, dev_node, type="device")
            g.add_edge(tx_node, ip_node, type="ip")
        return g

    def _cluster_to_cases(
        self,
        anomalous: pd.DataFrame,
        graph: nx.Graph,
        txs: List[Transaction],
    ) -> List[Case]:
        tx_by_id = {t.id: t for t in txs}
        cases: List[Case] = []

        # Build a subgraph of anomalous transaction nodes + their neighbors
        anomalous_tx_nodes = [f"tx:{tid}" for tid in anomalous["id"].tolist()]
        nodes_to_include = set(anomalous_tx_nodes)
        for tx_node in anomalous_tx_nodes:
            nodes_to_include.update(graph.neighbors(tx_node))

        sub = graph.subgraph(nodes_to_include).copy()
        for comp in nx.connected_components(sub):
            tx_ids = [
                n.split(":", 1)[1]
                for n in comp
                if isinstance(n, str) and n.startswith("tx:")
            ]
            if not tx_ids:
                continue

            comp_df = anomalous[anomalous["id"].isin(tx_ids)]
            risk_score = float(
                min(1.0, comp_df["anomaly_score"].mean() / (anomalous["anomaly_score"].max() + 1e-6))
            )

            customer_id = comp_df["customer_id"].mode().iat[0]
            account_id = comp_df["account_id"].mode().iat[0]

            signals: List[FraudSignal] = [
                FraudSignal(
                    name="graph-connected-anomalies",
                    score=risk_score,
                    explanation=(
                        "Cluster of anomalous transactions sharing customers, devices, or IPs."
                    ),
                )
            ]

            tx_objs = [tx_by_id[tid] for tid in tx_ids if tid in tx_by_id]
            case = Case(
                case_id=str(uuid.uuid4()),
                customer_id=customer_id,
                primary_account_id=account_id,
                transactions=tx_objs,
                risk_score=risk_score,
                signals=signals,
            )
            cases.append(case)

        return cases

    def _summarize_with_llm(self, case: Case) -> tuple[str, str]:
        # Fallback: rule-based summary if no API key
        if not self._client:
            total = sum(t.amount for t in case.transactions)
            n_tx = len(case.transactions)
            narrative = (
                f"{n_tx} suspicious transactions detected for customer {case.customer_id} "
                f"on account {case.primary_account_id}, total value {total:.2f}."
            )
            recommendation = (
                "Recommend temporarily restricting the account, contacting the customer, "
                "and escalating to Level 2 analyst for review."
            )
            return narrative, recommendation

        tx_descriptions = []
        for t in case.transactions:
            tx_descriptions.append(
                f"- {t.timestamp.isoformat()} | {t.amount:.2f} {t.currency} "
                f"at merchant {t.merchant_id} via {t.channel} from {t.country or 'unknown'}"
            )

        prompt = f"""
You are a senior fraud investigator at a bank.

Write a concise narrative (3–6 sentences) and a short recommended next action plan (1–3 sentences)
for the following fraud case.

Risk score: {case.risk_score:.2f}
Customer: {case.customer_id}
Primary account: {case.primary_account_id}
Signals:
{chr(10).join(f"- {s.name}: {s.score:.2f} – {s.explanation}" for s in case.signals)}

Transactions:
{chr(10).join(tx_descriptions)}

Return your answer as two sections:
Narrative:
...
Recommendation:
...
""".strip()

        resp = self._client.responses.create(
    model=settings.OPENAI_MODEL,
    input=prompt,
)

        # ----- SAFE OUTPUT EXTRACTION -----
        output_text = None

        # Newest API format
        if hasattr(resp, "output_text") and resp.output_text:
            output_text = resp.output_text

        # Old Responses output blocks
        elif hasattr(resp, "output") and resp.output:
            try:
                output_text = resp.output[0].content[0].text
            except Exception:
                pass

        # Messages format fallback
        if not output_text and hasattr(resp, "messages"):
            try:
                output_text = resp.messages[0]["content"][0]["text"]
            except Exception:
                pass

        # Last fallback
        if not output_text:
            output_text = str(resp)

        text = output_text


        narrative = ""
        recommendation = ""
        current = None
        for line in text.splitlines():
            line = line.strip()
            if line.lower().startswith("narrative"):
                current = "narrative"
                continue
            if line.lower().startswith("recommendation"):
                current = "recommendation"
                continue
            if not line:
                continue
            if current == "narrative":
                narrative += line + " "
            elif current == "recommendation":
                recommendation += line + " "

        return narrative.strip() or text, recommendation.strip() or "Review and act per fraud policy."
