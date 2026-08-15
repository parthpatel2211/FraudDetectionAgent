from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Channel = Literal["WEB", "MOBILE", "POS", "ATM", "TRANSFER"]
Severity = Literal["low", "medium", "high", "critical"]
EntityKind = Literal["transaction", "customer", "account", "device", "ip", "merchant"]


class Transaction(BaseModel):
    id: str
    customer_id: str
    account_id: str
    merchant_id: str
    device_id: str | None = None
    ip_address: str | None = None
    amount: float = Field(gt=0)
    currency: str = "USD"
    timestamp: datetime
    channel: Channel = "WEB"
    country: str | None = None


class Signal(BaseModel):
    """A rule that fired, aggregated across every instance of it in the case.

    `contribution` is the noisy-OR of all instances of this rule, not just the
    strongest one. Because noisy-OR is associative, combining the displayed
    contributions reproduces the case's risk_score exactly - so an analyst can
    add the evidence up and arrive at the number they were shown.
    """

    rule: str
    label: str
    score: float = Field(ge=0, le=1, description="strength of the strongest instance")
    weight: float = Field(ge=0, le=1)
    contribution: float = Field(ge=0, le=1, description="noisy-OR over all instances")
    instances: int = Field(ge=1, default=1)
    explanation: str
    tx_ids: list[str]


class GraphNode(BaseModel):
    id: str
    kind: EntityKind
    label: str
    risk: float = Field(ge=0, le=1, default=0.0)
    amount: float | None = None


class GraphEdge(BaseModel):
    source: str
    target: str
    weight: float = Field(ge=0, le=1)
    reasons: list[str]


class CaseGraph(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class Case(BaseModel):
    case_id: str
    customer_ids: list[str]
    account_ids: list[str]
    transactions: list[Transaction]
    risk_score: float = Field(ge=0, le=1)
    severity: Severity
    total_amount: float
    signals: list[Signal]
    graph: CaseGraph


class AnalysisResult(BaseModel):
    cases: list[Case]
    transactions_analyzed: int
    transactions_flagged: int
    threshold: float


class CaseSummary(BaseModel):
    case_id: str
    narrative: str
    recommendation: str
    next_steps: list[str]
    source: Literal["llm", "template"]
