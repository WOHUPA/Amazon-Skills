#!/usr/bin/env python3
"""Validate Codex Theme Pack v2 without executing theme-provided code."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

from compile_native_theme import NATIVE_PREFIX, compile_payload as compile_native_payload

from theme_common import (
    HEX_COLOR,
    SEMANTIC_ICON_SLOTS,
    THEME_ID,
    contrast_ratio,
    ensure_relative_asset,
    read_image_size,
    validate_safe_svg,
)


TOP_LEVEL = {"schemaVersion", "id", "name", "appearance", "assets", "palette", "materials", "layout", "art", "compatibility", "provenance"}
ASSET_KEYS = {"homeBackground", "taskBackground", "icons"}
PALETTE_KEYS = {"accent", "accentContrast", "canvas", "surface", "surfaceElevated", "text", "textMuted", "border", "menu", "panel", "composer", "dialog"}
MATERIAL_KEYS = {"panelOpacity", "composerOpacity", "dialogOpacity", "radius", "shadow", "blur"}
LAYOUT_KEYS = {"mode", "sidebarWidth", "contentMaxWidth", "composerOffset", "density"}
ART_KEYS = {"focusX", "focusY", "safeArea", "homeIntensity", "taskIntensity"}
COMPATIBILITY_KEYS = {"codexMinVersion", "rendererFingerprint", "generatorVersion"}
PROVENANCE_KEYS = {"generator", "source", "template"}
EXECUTABLE_SUFFIXES = {".bat", ".cmd", ".com", ".dll", ".exe", ".js", ".msi", ".ps1", ".vbs"}
FORBIDDEN_TERMS = {"css", "selector", "script", "runtime", "repository", "install", "injector", "javascript"}
VERSION = re.compile(r"^\d+(?:\.\d+){1,3}$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--theme-dir", required=True, type=Path)
    return parser.parse_args()


def is_reparse(path: Path) -> bool:
    try:
        stat = os.lstat(path)
    except OSError:
        return False
    return path.is_symlink() or bool(getattr(stat, "st_file_attributes", 0) & 0x400)


def assert_no_reparse(root: Path, path: Path) -> None:
    current = root
    if is_reparse(current):
        raise ValueError(f"theme root cannot be a link or reparse point: {current}")
    relative = path.relative_to(root)
    for part in relative.parts:
        current = current / part
        if current.exists() and is_reparse(current):
            raise ValueError(f"theme assets cannot use links or reparse points: {current}")


def check_exact_keys(value: dict[str, Any], expected: set[str], label: str, errors: list[str]) -> None:
    missing = sorted(expected - set(value))
    unknown = sorted(set(value) - expected)
    if missing:
        errors.append(f"{label} missing fields: {', '.join(missing)}")
    if unknown:
        errors.append(f"{label} has unknown fields: {', '.join(unknown)}")


def number_between(value: Any, minimum: float, maximum: float) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and minimum <= value <= maximum


def resolve_asset(root: Path, relative: str) -> Path:
    ensure_relative_asset(relative)
    target = root / relative
    assert_no_reparse(root, target)
    resolved = target.resolve(strict=True)
    if root != resolved and root not in resolved.parents:
        raise ValueError(f"asset escapes theme root: {relative}")
    return resolved


def validate_background(root: Path, relative: str | None, errors: list[str], warnings: list[str]) -> None:
    if relative is None:
        return
    try:
        path = resolve_asset(root, relative)
        if path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
            raise ValueError(f"background must be PNG or JPEG: {relative}")
        if path.stat().st_size > 20 * 1024 * 1024:
            raise ValueError(f"background exceeds 20 MB: {relative}")
        width, height = read_image_size(path)
        if width < 1600 or height < 900 or abs(width / height - 16 / 9) > 0.03:
            raise ValueError(f"background must be at least 1600x900 and approximately 16:9: {relative} ({width}x{height})")
        if width > 7680 or height > 4320:
            warnings.append(f"large background may waste memory: {relative} ({width}x{height})")
    except (OSError, ValueError) as error:
        errors.append(str(error))


def validate_icons(root: Path, icons: Any, errors: list[str]) -> None:
    if not isinstance(icons, dict):
        errors.append("assets.icons must be an object")
        return
    check_exact_keys(icons, SEMANTIC_ICON_SLOTS, "assets.icons", errors)
    for slot, relative in icons.items():
        try:
            if slot not in SEMANTIC_ICON_SLOTS or not isinstance(relative, str):
                continue
            path = resolve_asset(root, relative)
            if path.stat().st_size > 256 * 1024:
                raise ValueError(f"icon exceeds 256 KB: {relative}")
            if path.suffix.lower() == ".svg":
                validate_safe_svg(path)
            elif path.suffix.lower() != ".png":
                raise ValueError(f"icon must be safe SVG or PNG: {relative}")
        except (OSError, ValueError) as error:
            errors.append(str(error))


def validate_native_outputs(root: Path, theme: dict[str, Any], errors: list[str]) -> None:
    appearance = theme.get("appearance")
    variants = ("dark", "light") if appearance == "auto" else (appearance,)
    for variant in variants:
        if variant not in {"dark", "light"}:
            continue
        suffix = f"-{variant}" if appearance == "auto" else ""
        json_path = root / f"native-theme{suffix}.json"
        share_path = root / f"native-share{suffix}.txt"
        for path in (json_path, share_path):
            if not path.is_file():
                errors.append(f"missing required native output: {path.name}")
        if not json_path.is_file() or not share_path.is_file():
            continue
        try:
            expected = compile_native_payload(theme, variant=variant)
            actual = json.loads(json_path.read_text(encoding="utf-8"))
            if actual != expected:
                errors.append(f"native output does not match Theme Pack data: {json_path.name}")
            share = share_path.read_text(encoding="utf-8").strip()
            if not share.startswith(NATIVE_PREFIX):
                errors.append(f"native share prefix is invalid: {share_path.name}")
            else:
                shared_payload = json.loads(share.removeprefix(NATIVE_PREFIX))
                if shared_payload != expected:
                    errors.append(f"native share does not match Theme Pack data: {share_path.name}")
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
            errors.append(f"invalid native output for {variant}: {error}")


def validate(theme_dir: Path) -> dict[str, object]:
    root = theme_dir.expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []
    ratios: dict[str, float] = {}
    if not root.is_dir():
        return result([f"theme directory not found: {root}"], warnings, ratios)
    try:
        assert_no_reparse(root, root)
    except ValueError as error:
        errors.append(str(error))

    for required in ("theme.json", "preview.html", "README.md"):
        if not (root / required).is_file():
            errors.append(f"missing required file: {required}")
    for item in root.rglob("*"):
        if item.is_file() and item.suffix.lower() in EXECUTABLE_SUFFIXES:
            errors.append(f"executable file is not allowed: {item.relative_to(root)}")

    theme_path = root / "theme.json"
    if not theme_path.is_file():
        return result(errors, warnings, ratios)
    try:
        theme = json.loads(theme_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return result(errors + [f"invalid theme.json: {error}"], warnings, ratios)
    if not isinstance(theme, dict):
        return result(errors + ["theme.json root must be an object"], warnings, ratios)

    check_exact_keys(theme, TOP_LEVEL, "theme", errors)
    if theme.get("schemaVersion") != 2:
        errors.append("schemaVersion must equal 2")
    if not isinstance(theme.get("id"), str) or not THEME_ID.fullmatch(theme["id"]):
        errors.append("id must be a 1-48 character kebab-case identifier")
    if not isinstance(theme.get("name"), str) or not 1 <= len(theme["name"].strip()) <= 80:
        errors.append("name must contain 1-80 characters")
    if theme.get("appearance") not in {"dark", "light", "auto"}:
        errors.append("appearance must be dark, light, or auto")

    assets = theme.get("assets")
    if isinstance(assets, dict):
        check_exact_keys(assets, ASSET_KEYS, "assets", errors)
        for field in ("homeBackground", "taskBackground"):
            if assets.get(field) is not None and not isinstance(assets.get(field), str):
                errors.append(f"assets.{field} must be null or a relative path")
            elif isinstance(assets.get(field), str):
                validate_background(root, assets[field], errors, warnings)
        validate_icons(root, assets.get("icons"), errors)
    else:
        errors.append("assets must be an object")

    palette = theme.get("palette")
    if isinstance(palette, dict):
        check_exact_keys(palette, PALETTE_KEYS, "palette", errors)
        if all(isinstance(palette.get(key), str) and HEX_COLOR.fullmatch(palette[key]) for key in PALETTE_KEYS):
            ratios = {
                "textOnSurface": round(contrast_ratio(palette["text"], palette["surface"]), 2),
                "mutedOnSurface": round(contrast_ratio(palette["textMuted"], palette["surface"]), 2),
                "accentContrast": round(contrast_ratio(palette["accentContrast"], palette["accent"]), 2),
            }
            if ratios["textOnSurface"] < 4.5:
                errors.append("text/surface contrast must be at least 4.5:1")
            if ratios["mutedOnSurface"] < 3:
                errors.append("textMuted/surface contrast must be at least 3:1")
            if ratios["accentContrast"] < 4.5:
                errors.append("accentContrast/accent contrast must be at least 4.5:1")
        else:
            errors.append("all palette fields must use #RRGGBB")
    else:
        errors.append("palette must be an object")

    materials = theme.get("materials")
    if isinstance(materials, dict):
        check_exact_keys(materials, MATERIAL_KEYS, "materials", errors)
        for field in ("panelOpacity", "composerOpacity", "dialogOpacity"):
            if not number_between(materials.get(field), 0.25, 1):
                errors.append(f"materials.{field} must be between 0.25 and 1")
        if not isinstance(materials.get("radius"), int) or not 0 <= materials["radius"] <= 28:
            errors.append("materials.radius must be an integer from 0 to 28")
        if materials.get("shadow") not in {"none", "soft", "strong"}:
            errors.append("materials.shadow must be none, soft, or strong")
        if not isinstance(materials.get("blur"), int) or not 0 <= materials["blur"] <= 24:
            errors.append("materials.blur must be an integer from 0 to 24")
    else:
        errors.append("materials must be an object")

    layout = theme.get("layout")
    if isinstance(layout, dict):
        check_exact_keys(layout, LAYOUT_KEYS, "layout", errors)
        if layout.get("mode") not in {"native", "compact", "cinematic", "focus"}:
            errors.append("layout.mode is unsupported")
        if not isinstance(layout.get("sidebarWidth"), int) or not 200 <= layout["sidebarWidth"] <= 320:
            errors.append("layout.sidebarWidth must be an integer from 200 to 320")
        if not isinstance(layout.get("contentMaxWidth"), int) or not 720 <= layout["contentMaxWidth"] <= 1280:
            errors.append("layout.contentMaxWidth must be an integer from 720 to 1280")
        if not isinstance(layout.get("composerOffset"), int) or not -48 <= layout["composerOffset"] <= 48:
            errors.append("layout.composerOffset must be an integer from -48 to 48")
        if layout.get("density") not in {"compact", "comfortable", "spacious"}:
            errors.append("layout.density is unsupported")
        if layout.get("mode") == "native" and layout != {
            "mode": "native",
            "sidebarWidth": 240,
            "contentMaxWidth": 920,
            "composerOffset": 0,
            "density": "comfortable",
        }:
            errors.append(
                "native layout must use canonical 240/920/0/comfortable values; "
                "native mode does not apply custom geometry"
            )
    else:
        errors.append("layout must be an object")

    art = theme.get("art")
    if isinstance(art, dict):
        check_exact_keys(art, ART_KEYS, "art", errors)
        for field in ("focusX", "focusY", "homeIntensity", "taskIntensity"):
            if not number_between(art.get(field), 0, 1):
                errors.append(f"art.{field} must be between 0 and 1")
        if art.get("safeArea") not in {"left", "right", "center", "none"}:
            errors.append("art.safeArea is unsupported")
    else:
        errors.append("art must be an object")

    compatibility = theme.get("compatibility")
    if isinstance(compatibility, dict):
        check_exact_keys(compatibility, COMPATIBILITY_KEYS, "compatibility", errors)
        if not isinstance(compatibility.get("codexMinVersion"), str) or not VERSION.fullmatch(compatibility["codexMinVersion"]):
            errors.append("compatibility.codexMinVersion must be a numeric dotted version")
        if compatibility.get("rendererFingerprint") != "codex-theme-studio-v2":
            errors.append("compatibility.rendererFingerprint is unsupported")
        if not isinstance(compatibility.get("generatorVersion"), str) or not VERSION.fullmatch(compatibility["generatorVersion"]):
            errors.append("compatibility.generatorVersion must be a numeric dotted version")
    else:
        errors.append("compatibility must be an object")

    provenance = theme.get("provenance")
    if isinstance(provenance, dict):
        check_exact_keys(provenance, PROVENANCE_KEYS, "provenance", errors)
        if provenance.get("generator") != "codex-theme-generator":
            errors.append("provenance.generator must equal codex-theme-generator")
        if provenance.get("source") not in {"generated", "provided", "none", "migrated"}:
            errors.append("provenance.source is unsupported")
        if provenance.get("template") not in {"immersive-dark", "clear-light", "obsidian-gold"}:
            errors.append("provenance.template is unsupported")
    else:
        errors.append("provenance must be an object")

    forbidden = find_forbidden_keys(theme)
    if forbidden:
        errors.append("forbidden executable or runtime fields: " + ", ".join(sorted(forbidden)))
    validate_native_outputs(root, theme, errors)
    return result(errors, warnings, ratios)


def find_forbidden_keys(value: object, prefix: str = "") -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if str(key).lower() in FORBIDDEN_TERMS:
                found.add(path)
            found.update(find_forbidden_keys(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.update(find_forbidden_keys(child, f"{prefix}[{index}]"))
    return found


def result(errors: list[str], warnings: list[str], ratios: dict[str, float]) -> dict[str, object]:
    status = "COMPLETE" if not errors else "BLOCKED"
    return {"schemaVersion": 2, "reportType": "codex-theme-validation", "status": status,
            "publishable": status == "COMPLETE", "errors": errors, "warnings": warnings,
            "contrastRatios": ratios}


def main() -> int:
    report = validate(parse_args().theme_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
