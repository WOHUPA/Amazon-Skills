#!/usr/bin/env python3
"""Compile a Theme Pack v2 palette into Codex's native codex-theme-v1 payload."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from theme_common import HEX_COLOR


NATIVE_PREFIX = "codex-theme-v1:"
DEFAULT_CODE_THEME_ID = "codex"
NATIVE_DEFAULTS = {
    "dark": {
        "contrast": 60,
        "diffAdded": "#40C977",
        "diffRemoved": "#FA423E",
    },
    "light": {
        "contrast": 45,
        "diffAdded": "#00A240",
        "diffRemoved": "#BA2623",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--theme-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--variant", choices=("dark", "light"))
    parser.add_argument("--code-theme-id")
    return parser.parse_args()


def compile_payload(
    theme: dict[str, Any], *, variant: str | None = None, code_theme_id: str | None = None
) -> dict[str, Any]:
    """Return the selector-free native Codex theme payload derived from Theme Pack data."""
    palette = theme.get("palette")
    if not isinstance(palette, dict):
        raise ValueError("Theme Pack palette is missing")
    required = {
        "accent", "canvas", "surface", "text", "textMuted", "border",
        "menu", "panel", "composer", "dialog",
    }
    missing = sorted(
        key for key in required
        if not isinstance(palette.get(key), str) or not HEX_COLOR.fullmatch(palette[key])
    )
    if missing:
        raise ValueError("Theme Pack palette has invalid native fields: " + ", ".join(missing))

    selected_variant = variant or theme.get("appearance")
    if selected_variant == "auto":
        raise ValueError("Native compilation of appearance=auto requires --variant")
    if selected_variant not in NATIVE_DEFAULTS:
        raise ValueError("Native theme variant must be dark or light")
    selected_code_theme = code_theme_id or DEFAULT_CODE_THEME_ID
    if (
        not isinstance(selected_code_theme, str)
        or not selected_code_theme.strip()
        or len(selected_code_theme) > 120
    ):
        raise ValueError("code theme ID must contain 1-120 characters")

    native_defaults = NATIVE_DEFAULTS[selected_variant]
    return {
        "codeThemeId": selected_code_theme.strip(),
        "variant": selected_variant,
        "theme": {
            "accent": palette["accent"].upper(),
            "contrast": native_defaults["contrast"],
            "fonts": {"code": None, "ui": None},
            "ink": palette["text"].upper(),
            "opaqueWindows": False,
            "semanticColors": {
                "diffAdded": native_defaults["diffAdded"],
                "diffRemoved": native_defaults["diffRemoved"],
                "skill": palette["accent"].upper(),
            },
            "surface": palette["canvas"].upper(),
        },
    }


def write_native_files(root: Path, payload: dict[str, Any], *, suffix: str = "") -> None:
    if suffix not in {"", "-dark", "-light"}:
        raise ValueError("native output suffix must be empty, -dark, or -light")
    root.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    compact = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    (root / f"native-theme{suffix}.json").write_text(serialized, encoding="utf-8")
    (root / f"native-share{suffix}.txt").write_text(NATIVE_PREFIX + compact + "\n", encoding="utf-8")


def load_theme(theme_dir: Path) -> dict[str, Any]:
    theme_path = theme_dir.expanduser().resolve(strict=True) / "theme.json"
    theme = json.loads(theme_path.read_text(encoding="utf-8"))
    if not isinstance(theme, dict) or theme.get("schemaVersion") != 2:
        raise ValueError("Native compilation requires Theme Pack v2")
    return theme


def atomic_compile(args: argparse.Namespace) -> tuple[Path, dict[str, Any]]:
    output = args.output_dir.expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing path: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}-", dir=output.parent))
    try:
        payload = compile_payload(
            load_theme(args.theme_dir), variant=args.variant, code_theme_id=args.code_theme_id
        )
        write_native_files(staging, payload)
        os.replace(staging, output)
        return output, payload
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main() -> int:
    try:
        output, payload = atomic_compile(parse_args())
    except (FileExistsError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "BLOCKED", "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({
        "status": "COMPLETE",
        "outputDir": str(output),
        "variant": payload["variant"],
        "codeThemeId": payload["codeThemeId"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
