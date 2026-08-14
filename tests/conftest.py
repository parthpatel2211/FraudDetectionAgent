import json
import pathlib

import pytest

from backend.models import Transaction

DATA = pathlib.Path(__file__).resolve().parent.parent / "data"


@pytest.fixture(scope="session")
def demo_transactions() -> list[Transaction]:
    raw = json.loads((DATA / "demo_transactions.json").read_text())
    return [Transaction(**t) for t in raw]


@pytest.fixture(scope="session")
def ground_truth() -> dict[str, str]:
    return json.loads((DATA / "ground_truth.json").read_text())
