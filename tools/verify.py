"""Run the real suite and retain machine-readable outcomes and environment."""
import argparse
import json
from pathlib import Path
import platform
import sqlite3
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class Result(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.passed = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.passed.append(test.id())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    result = unittest.TextTestRunner(verbosity=2, resultclass=Result).run(suite)
    report = dict(python=sys.version, os=platform.platform(), sqlite=sqlite3.sqlite_version,
                  storage_profile="sqlite-delete-full-v1", elapsed_seconds=time.perf_counter() - started,
                  tests_run=result.testsRun, passed=result.passed,
                  failures=[dict(test=str(t), trace=trace) for t, trace in result.failures],
                  errors=[dict(test=str(t), trace=trace) for t, trace in result.errors],
                  successful=result.wasSuccessful(),
                  limits=["Abrupt process-exit crash injection, not physical power loss or filesystem fault injection.",
                          "Local SQLite synthetic effects only; no external-effect atomicity or upstream compatibility claim."])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
