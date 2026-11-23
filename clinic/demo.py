"""Replay a deterministic fake effect sequence inside a fresh local database."""
from pathlib import Path
import tempfile

from .storage import Store


def storage_demo(directory):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=directory) as temporary:
        if not Path(temporary).resolve().is_relative_to(directory):
            raise ValueError("temporary database escaped demo directory")
        store = Store(Path(temporary) / "demo.sqlite3")
        store.initialize()
        base = dict(request_id="demo-A", permission_id="permit-1", actor="agent-A", tool="synthetic-transfer",
                    asset="SYN", unit="credit", destination="merchant-A", amount=6)
        other = dict(base, request_id="demo-B")
        last = dict(base, request_id="demo-C", amount=4)
        trace = []
        def step(name, expected, operation):
            result = operation()
            trace.append(dict(step=name, expected=expected, actual=result["reason"], match=result["reason"] == expected))
        step("first reservation", "ALLOW", lambda: store.reserve(base, now=1000))
        step("aggregate quota rejection", "QUOTA", lambda: store.reserve(other, now=1000))
        step("consume first", "CONSUMED", lambda: store.execute(base, now=1000))
        step("duplicate resolves same effect", "REPLAY", lambda: store.execute(base, now=1000))
        step("remaining four", "ALLOW", lambda: store.reserve(last, now=1000))
        step("consume remaining four", "CONSUMED", lambda: store.execute(last, now=1000))
        snapshot = store.snapshot()
        return dict(mode="synthetic-storage-demo", profile=snapshot["profile"], traces=trace,
                    mismatches=sum(not row["match"] for row in trace), snapshot=snapshot,
                    limits=["Same-database synthetic effects only; no wallet, external ledger or service verifier.",
                            "Sequential demo is not race evidence; use the separate process/crash test suite."])
