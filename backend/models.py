from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class Transaction(BaseModel):
    id: str
    customer_id: str
    account_id: str
    merchant_id: str
    device_id: Optional[str] = None
    ip_address: Optional[str] = None
    amount: float
    currency: str = "USD"
    timestamp: datetime
    channel: str = Field(description="e.g. POS, WEB, MOBILE")
    country: Optional[str] = None


class FraudSignal(BaseModel):
    name: str
    score: float = Field(ge=0, le=1)
    explanation: str


class Case(BaseModel):
    case_id: str
    customer_id: str
    primary_account_id: str
    transactions: List[Transaction]
    risk_score: float = Field(ge=0, le=1)
    signals: List[FraudSignal]


class CaseSummary(BaseModel):
    case: Case
    narrative: str
    recommendation: str
