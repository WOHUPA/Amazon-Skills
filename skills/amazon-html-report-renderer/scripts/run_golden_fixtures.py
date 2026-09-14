#!/usr/bin/env python3
"""Run the six anonymous Golden fixtures through the renderer and emit receipts.

Usage:
    python scripts/run_golden_fixtures.py [--format json|text] [--receipt-log PATH]

Every run re-renders all fixtures into a temp directory and writes a JSONL receipt
log at evals/golden-receipts.jsonl. Exit code 0 only when all cases PASS.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tests.run_golden import DEFAULT_RECEIPTS_PATH, main as run_golden_main


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(description="Run Golden fixtures")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    parser.add_argument("--receipt-log", type=Path, default=DEFAULT_RECEIPTS_PATH)
    args, _ = parser.parse_known_args()

    # Reuse the tests.run_golden runner; the receipt-log is controlled here.
    sys.argv = [sys.argv[0], "--receipt-log", str(args.receipt_log)]
    return run_golden_main()


if __name__ == "__main__":
    raise SystemExit(main())
