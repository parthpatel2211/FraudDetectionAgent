from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from backend.models import Transaction


@dataclass
class Context:
    """Indexes computed once per batch and shared by every rule.

    Each bucket list is sorted by timestamp, which lets the time-window rules
    use a two-pointer scan instead of comparing every pair.
    """

    txs: list[Transaction]
    by_customer: dict[str, list[Transaction]] = field(default_factory=dict)
    by_account: dict[str, list[Transaction]] = field(default_factory=dict)
    by_device: dict[str, list[Transaction]] = field(default_factory=dict)
    by_ip: dict[str, list[Transaction]] = field(default_factory=dict)
    by_merchant: dict[str, list[Transaction]] = field(default_factory=dict)

    @classmethod
    def build(cls, txs: list[Transaction]) -> Context:
        ordered = sorted(txs, key=lambda t: t.timestamp)
        buckets: dict[str, dict[str, list[Transaction]]] = {
            k: defaultdict(list)
            for k in ("customer", "account", "device", "ip", "merchant")
        }
        for t in ordered:
            buckets["customer"][t.customer_id].append(t)
            buckets["account"][t.account_id].append(t)
            buckets["merchant"][t.merchant_id].append(t)
            if t.device_id:
                buckets["device"][t.device_id].append(t)
            if t.ip_address:
                buckets["ip"][t.ip_address].append(t)

        return cls(
            txs=ordered,
            by_customer=dict(buckets["customer"]),
            by_account=dict(buckets["account"]),
            by_device=dict(buckets["device"]),
            by_ip=dict(buckets["ip"]),
            by_merchant=dict(buckets["merchant"]),
        )
