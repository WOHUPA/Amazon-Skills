#!/usr/bin/env python3
"""Render an amazon-html-report/v1 JSON spec into a self-contained HTML report.

Usage:
    python scripts/render_report.py --spec <spec.json> --output <report.html> [options]

This CLI is the deterministic renderer entrypoint. All business values, references,
hashes and SVG geometry are computed in code; the model never hand-computes them.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from report_renderer import (
    AmazonHTMLReportError,
    build_document,
    load_and_validate,
    write_artifact_pair,
)


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(description="Render Amazon HTML report v1")
    parser.add_argument("--spec", type=Path, required=True, help="report spec JSON path")
    parser.add_argument("--output", type=Path, required=True, help="output HTML path")
    parser.add_argument(
        "--family",
        choices=["auto", "performance", "insight", "operations", "knowledge"],
        default=None,
        help="override layout family",
    )
    parser.add_argument("--validate-only", action="store_true", help="validate and exit")
    parser.add_argument("--overwrite", action="store_true", help="allow replacing existing output")
    parser.add_argument(
        "--receipt-path-mode",
        choices=["absolute", "relative"],
        default="absolute",
        help="receipt path encoding mode",
    )
    args = parser.parse_args()

    try:
        spec, validation = load_and_validate(args.spec, family_override=args.family)
    except AmazonHTMLReportError as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        envelope = {"ok": False, "error": str(exc), "status": "ERROR"}
        sys.stdout.write(json.dumps(envelope, ensure_ascii=False, sort_keys=True) + "\n")
        return 2

    if args.validate_only:
        envelope = {
            "ok": True,
            "status": spec["report"]["status"],
            "validation": validation,
            "output_path": None,
            "receipt_path": None,
        }
        sys.stdout.write(json.dumps(envelope, ensure_ascii=False, sort_keys=True) + "\n")
        return 0

    try:
        document, receipt, paths = write_artifact_pair(
            spec,
            output_path=args.output,
            overwrite=args.overwrite,
            receipt_path_mode=args.receipt_path_mode,
        )
    except AmazonHTMLReportError as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        envelope = {"ok": False, "error": str(exc), "status": "ERROR"}
        sys.stdout.write(json.dumps(envelope, ensure_ascii=False, sort_keys=True) + "\n")
        return 2

    envelope = {
        "ok": True,
        "status": spec["report"]["status"],
        "output_path": str(paths["html"]),
        "receipt_path": str(paths["receipt"]),
        "html_hash": receipt["html_hash"],
        "manifest_hash": receipt["manifest_hash"],
        "template_version": receipt["template_version"],
    }
    sys.stdout.write(json.dumps(envelope, ensure_ascii=False, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
