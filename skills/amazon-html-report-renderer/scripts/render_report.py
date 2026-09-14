#!/usr/bin/env python3
"""Render a validated Amazon report specification as a self-contained HTML file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from report_renderer import RenderError, execute_render


class JsonArgumentParser(argparse.ArgumentParser):
    """Raise structured errors so stdout remains a single JSON object."""

    def error(self, message: str) -> None:
        raise RenderError("CLI_ARGUMENT_ERROR", message, "cli")


def configure_stdio() -> None:
    """Keep machine output valid on Windows consoles with legacy code pages."""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def parse_args() -> argparse.Namespace:
    parser = JsonArgumentParser(
        description="Render amazon-html-report/v1 JSON to a self-contained offline HTML report."
    )
    parser.add_argument("--spec", required=True, type=Path, help="amazon-html-report/v1 JSON")
    parser.add_argument("--output", required=True, type=Path, help="target .html file")
    parser.add_argument(
        "--family",
        choices=("auto", "performance", "insight", "operations", "knowledge"),
        default="auto",
        help="layout family override",
    )
    parser.add_argument("--validate-only", action="store_true", help="validate without writing")
    parser.add_argument("--overwrite", action="store_true", help="replace existing artifacts")
    parser.add_argument("--receipt-path-mode", choices=("absolute", "relative"), default="absolute",
                        help="receipt artifact paths; relative paths are based on the receipt directory")
    return parser.parse_args()


def emit(payload: dict[str, object]) -> None:
    """Emit exactly one compact, machine-readable JSON object."""

    sys.stdout.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    sys.stdout.flush()


def main() -> int:
    configure_stdio()
    try:
        args = parse_args()
        result = execute_render(
            spec_path=args.spec,
            output_path=args.output,
            family_override=args.family,
            validate_only=args.validate_only,
            overwrite=args.overwrite,
            receipt_path_mode=args.receipt_path_mode,
        )
    except RenderError as exc:
        emit(
            {
                "ok": False,
                "status": "BLOCKED",
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "path": exc.path,
                },
            }
        )
        return 2
    except Exception as exc:  # Fail closed without leaking input data or a traceback.
        emit(
            {
                "ok": False,
                "status": "BLOCKED",
                "error": {
                    "code": "INTERNAL_RENDER_ERROR",
                    "message": type(exc).__name__,
                    "path": "renderer",
                },
            }
        )
        return 3

    emit(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
