"""Seeded synthetic transaction generator with ground-truth fraud labels.

Every value derives from `random.Random(seed)` and a fixed base timestamp, so
output is byte-stable across runs and machines. That matters for two reasons:
the committed fixtures must not churn in git, and the detector's precision and
recall tests assert against fixed numbers.

Run directly to regenerate the committed fixtures:

    python data/generate.py
"""

from __future__ import annotations

import json
import math
import pathlib
import random
from datetime import UTC, datetime, timedelta

BASE = datetime(2026, 3, 14, 9, 0, tzinfo=UTC)
HERE = pathlib.Path(__file__).resolve().parent

RINGS = (
    "ring_device",
    "ring_card_testing",
    "ring_travel",
    "ring_structuring",
)

COUNTRIES = ["US", "GB", "CA", "DE", "AU", "IN"]
CHANNELS = ["WEB", "MOBILE", "POS", "ATM"]
MERCHANT_POOL = [
    "M-GROCER", "M-COFFEE", "M-FUEL", "M-PHARMACY", "M-STREAMING",
    "M-AIRLINE", "M-HARDWARE", "M-BOOKS", "M-RESTAURANT", "M-TRANSIT",
    "M-GYM", "M-CLOTHING", "M-ELECTRONICS", "M-PETSHOP", "M-BAKERY",
]


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _tx(
    id_: str,
    customer_id: str,
    account_id: str,
    merchant_id: str,
    amount: float,
    when: datetime,
    *,
    device_id: str | None,
    ip_address: str | None,
    channel: str,
    country: str,
) -> dict:
    return {
        "id": id_,
        "customer_id": customer_id,
        "account_id": account_id,
        "merchant_id": merchant_id,
        "device_id": device_id,
        "ip_address": ip_address,
        "amount": round(amount, 2),
        "currency": "USD",
        "timestamp": _iso(when),
        "channel": channel,
        "country": country,
    }


def _clean_traffic(rng: random.Random, n: int) -> list[dict]:
    """Forty customers with stable habits: home country, own device, usual merchants."""
    customers = []
    for i in range(40):
        cid = f"CUST-{i:03d}"
        customers.append({
            "id": cid,
            "account": f"ACC-{i:03d}",
            "country": rng.choice(COUNTRIES),
            "device": f"DEV-{i:03d}",
            "ip": f"203.0.{i // 8}.{(i % 8) * 20 + 3}",
            "merchants": rng.sample(MERCHANT_POOL, rng.randint(3, 6)),
            "mu": math.log(rng.uniform(8, 180)),
        })

    out: list[dict] = []
    for k in range(n):
        c = rng.choice(customers)
        # Daytime-weighted: pick an hour in 8..21 so off-hours stays a real signal.
        day = rng.randint(0, 13)
        when = BASE + timedelta(
            days=day,
            hours=rng.randint(8, 21) - 9,
            minutes=rng.randint(0, 59),
            seconds=rng.randint(0, 59),
        )
        out.append(_tx(
            f"TX-C{k:05d}",
            c["id"], c["account"], rng.choice(c["merchants"]),
            min(rng.lognormvariate(c["mu"], 0.45), 900.0),
            when,
            device_id=c["device"], ip_address=c["ip"],
            channel=rng.choice(CHANNELS), country=c["country"],
        ))
    return out


def _ring_device(rng: random.Random) -> list[dict]:
    """Three customers on one device inside 40 minutes, amounts climbing."""
    device, ip = "DEV-SHARED-01", "198.51.100.7"
    out: list[dict] = []
    amounts = [600, 850, 1150, 1400, 1700, 1950, 2300, 2600, 2900]
    for k, amount in enumerate(amounts):
        cid = f"MULE-{k % 3:02d}"
        out.append(_tx(
            f"TX-D{k:03d}",
            cid, f"ACC-{cid}", "M-ELECTRONICS",
            amount + rng.uniform(-15, 15),
            BASE + timedelta(days=3, minutes=4 * k + rng.randint(0, 2)),
            device_id=device, ip_address=ip, channel="WEB", country="US",
        ))
    return out


def _ring_card_testing(rng: random.Random) -> list[dict]:
    """Eight tiny probes across eight merchants, then three real charges."""
    cid, device, ip = "VICTIM-01", "DEV-TEST-09", "198.51.100.42"
    out: list[dict] = []
    for k in range(8):
        out.append(_tx(
            f"TX-T{k:03d}",
            cid, f"ACC-{cid}", MERCHANT_POOL[k],
            rng.uniform(1.0, 3.5),
            BASE + timedelta(days=5, minutes=90 + k + rng.randint(0, 1)),
            device_id=device, ip_address=ip, channel="WEB", country="US",
        ))
    for k in range(3):
        out.append(_tx(
            f"TX-T1{k:02d}",
            cid, f"ACC-{cid}", "M-ELECTRONICS",
            rng.uniform(1900, 2400),
            BASE + timedelta(days=5, minutes=105 + 4 * k),
            device_id=device, ip_address=ip, channel="WEB", country="US",
        ))
    return out


def _ring_travel(rng: random.Random) -> list[dict]:
    """One customer alternating US and SG faster than any flight."""
    cid = "TRAVEL-01"
    out: list[dict] = []
    minute = 0
    for k, country in enumerate(["US", "SG", "US", "SG"]):
        out.append(_tx(
            f"TX-G{k:03d}",
            cid, f"ACC-{cid}", "M-AIRLINE",
            rng.uniform(180, 640),
            BASE + timedelta(days=7, minutes=minute),
            device_id=f"DEV-{cid}", ip_address="198.51.100.88",
            channel="WEB", country=country,
        ))
        minute += rng.randint(18, 35)
    return out


def _ring_structuring(rng: random.Random) -> list[dict]:
    """Six transfers parked just under a 10,000 reporting threshold."""
    cid = "STRUCT-01"
    out: list[dict] = []
    for k in range(6):
        out.append(_tx(
            f"TX-S{k:03d}",
            cid, f"ACC-{cid}", "M-TRANSIT",
            rng.uniform(9100, 9850),
            BASE + timedelta(days=9, hours=k * 3, minutes=rng.randint(0, 40)),
            device_id=f"DEV-{cid}", ip_address="198.51.100.51",
            channel="TRANSFER", country="US",
        ))
    return out


def generate(seed: int = 42, n_normal: int = 440) -> tuple[list[dict], dict[str, str]]:
    """Return (transactions, {tx_id: ring_label}).

    Labels are `clean` or one of RINGS. The two are returned separately and the
    label never appears on the transaction, so nothing downstream can cheat by
    reading it.
    """
    rng = random.Random(seed)

    labelled: list[tuple[dict, str]] = []
    labelled += [(t, "clean") for t in _clean_traffic(rng, n_normal)]
    labelled += [(t, "ring_device") for t in _ring_device(rng)]
    labelled += [(t, "ring_card_testing") for t in _ring_card_testing(rng)]
    labelled += [(t, "ring_travel") for t in _ring_travel(rng)]
    labelled += [(t, "ring_structuring") for t in _ring_structuring(rng)]

    rng.shuffle(labelled)
    transactions = [t for t, _ in labelled]
    ground_truth = {t["id"]: label for t, label in labelled}
    return transactions, ground_truth


if __name__ == "__main__":
    txs, gt = generate()
    (HERE / "demo_transactions.json").write_text(json.dumps(txs, indent=2) + "\n")
    (HERE / "ground_truth.json").write_text(json.dumps(gt, indent=2) + "\n")
    counts: dict[str, int] = {}
    for label in gt.values():
        counts[label] = counts.get(label, 0) + 1
    print(f"wrote {len(txs)} transactions to data/demo_transactions.json")
    for label, n in sorted(counts.items()):
        print(f"  {label:<20} {n}")
