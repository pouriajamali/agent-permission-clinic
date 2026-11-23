import argparse
import json
from pathlib import Path
import sys
import sqlite3

from .demo import storage_demo
from .runner import replay


def main():
    parser = argparse.ArgumentParser(description="Offline synthetic permission conformance; no wallet or secrets.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--corpus", type=Path, help="Custom synthetic corpus using clinic-synthetic-v1")
    mode.add_argument("--storage-demo", type=Path, metavar="DIRECTORY", help="Run a fake effect sequence in a fresh temporary SQLite database")
    parser.add_argument("--output", type=Path, help="Write JSON report (stdout by default)")
    args = parser.parse_args()
    try:
        report = storage_demo(args.storage_demo) if args.storage_demo else replay(args.corpus.read_bytes() if args.corpus else None)
        rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
        return 1 if report["mismatches"] else 0
    except (ValueError, KeyError, TypeError, OSError, sqlite3.Error) as exc:
        print("clinic: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
