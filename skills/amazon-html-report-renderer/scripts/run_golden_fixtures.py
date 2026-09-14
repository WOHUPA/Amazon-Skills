#!/usr/bin/env python3
"""Run the six deterministic Golden fixtures in the optimizer JSON contract."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = SKILL_ROOT / "tests" / "run_golden.py"


def load_runner() -> ModuleType:
    """Load the canonical runner without creating a duplicate test implementation."""

    module_spec = importlib.util.spec_from_file_location("amazon_html_golden_runner", RUNNER_PATH)
    if module_spec is None or module_spec.loader is None:
        raise RuntimeError("Golden runner could not be loaded")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def build_report() -> dict[str, Any]:
    """Map canonical string case IDs to the optimizer's stable integer contract."""

    module = load_runner()
    cases = module.load_json(module.CASES_PATH)
    case_receipts = [module.run_case(case) for case in cases]
    results = [
        {
            "id": index,
            "case_id": receipt["case_id"],
            "status": receipt["status"],
        }
        for index, receipt in enumerate(case_receipts, start=1)
    ]
    passed = sum(result["status"] == "PASS" for result in results)
    failed = len(results) - passed
    return {
        "status": "PASS" if failed == 0 and len(results) == 6 else "FAIL",
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "results": results,
    }


def main() -> int:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="运行六组 Amazon HTML Golden fixtures")
    parser.add_argument("--format", choices=("json",), default="json")
    parser.parse_args()
    try:
        report = build_report()
    except Exception as exc:  # The CLI boundary must remain one valid JSON object.
        report = {
            "status": "FAIL",
            "total": 1,
            "passed": 0,
            "failed": 1,
            "results": [{"id": 1, "status": "FAIL"}],
            "error": type(exc).__name__,
        }
    sys.stdout.write(json.dumps(report, ensure_ascii=False, sort_keys=True) + "\n")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
