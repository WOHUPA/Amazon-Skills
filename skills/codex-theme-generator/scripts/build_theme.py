#!/usr/bin/env python3
"""Build an atomic Codex Theme Pack v2 with native-safe layout and preview."""

from __future__ import annotations

import argparse
import html
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from bundle_theme import create_bundle
from compile_native_theme import compile_payload as compile_native_payload, write_native_files

from theme_common import (
    POSITION,
    SEMANTIC_ICON_SLOTS,
    THEME_ID,
    best_contrast,
    normalize_hex,
    read_image_size,
    validate_safe_svg,
)


GENERATOR_VERSION = "2.7.0"
SAFE_LAYOUT = {"mode": "native", "sidebarWidth": 240, "contentMaxWidth": 920,
               "composerOffset": 0, "density": "comfortable"}

TEMPLATES: dict[str, dict[str, Any]] = {
    "immersive-dark": {
        "palette": {
            "canvas": "#090B10", "surface": "#151923", "surfaceElevated": "#202633",
            "text": "#F6F8FC", "textMuted": "#AAB4C4", "border": "#354052",
            "menu": "#111722", "panel": "#151B27", "composer": "#1A2230", "dialog": "#202938",
        },
        "materials": {"panelOpacity": 0.58, "composerOpacity": 0.68, "dialogOpacity": 0.76,
                      "radius": 16, "shadow": "strong", "blur": 12},
        "layout": SAFE_LAYOUT,
        "art": {"homeIntensity": 0.92, "taskIntensity": 0.28},
    },
    "clear-light": {
        "palette": {
            "canvas": "#EDF3F8", "surface": "#FFFFFF", "surfaceElevated": "#F8FBFD",
            "text": "#17202B", "textMuted": "#586779", "border": "#CCD7E3",
            "menu": "#F5F9FC", "panel": "#FFFFFF", "composer": "#FFFFFF", "dialog": "#FFFFFF",
        },
        "materials": {"panelOpacity": 1.0, "composerOpacity": 1.0, "dialogOpacity": 1.0,
                      "radius": 14, "shadow": "soft", "blur": 0},
        "layout": SAFE_LAYOUT,
        "art": {"homeIntensity": 0.88, "taskIntensity": 0.22},
    },
    "obsidian-gold": {
        "palette": {
            "canvas": "#080807", "surface": "#171510", "surfaceElevated": "#242016",
            "text": "#FFF8E7", "textMuted": "#C7B993", "border": "#5B4C27",
            "menu": "#12100C", "panel": "#18150E", "composer": "#201B11", "dialog": "#292116",
        },
        "materials": {"panelOpacity": 0.62, "composerOpacity": 0.72, "dialogOpacity": 0.80,
                      "radius": 12, "shadow": "strong", "blur": 10},
        "layout": SAFE_LAYOUT,
        "art": {"homeIntensity": 0.90, "taskIntensity": 0.26},
    },
}

DEFAULT_ICON_PATHS = {
    "newTask": "M12 5v14M5 12h14", "search": "M20 20l-4.4-4.4M10.5 18a7.5 7.5 0 1 1 0-15 7.5 7.5 0 0 1 0 15",
    "projects": "M3 7h7l2 2h9v10H3z", "history": "M4 12a8 8 0 1 0 2.3-5.7L4 8M4 4v4h4M12 7v5l3 2",
    "attach": "M8 12.5l6.7-6.7a4 4 0 1 1 5.7 5.7l-8.5 8.5a6 6 0 0 1-8.5-8.5L12 3",
    "send": "M3 11.5 21 3l-6.5 18-3.5-7zM11 14 21 3", "settings": "M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7M19 12l2-1-2-3-2 .2-1-2.2-3 1-1 2 1 .2-2-2-1-3 2-1 2 1 .2 2.2 3 1 1-1 2 2 3 2-1 .2 1 2 3 2 1z",
    "skills": "M12 3l2.2 5.1L20 10l-4 3.5 1.2 5.5L12 16l-5.2 3L8 13.5 4 10l5.8-1.9z",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--id", required=True, dest="theme_id")
    parser.add_argument("--name", required=True)
    parser.add_argument("--appearance", choices=("dark", "light", "auto"), default="dark")
    parser.add_argument("--pair", action="store_true", help="build <id>-dark and <id>-light below themes/")
    parser.add_argument("--template", choices=("auto", *TEMPLATES), default="auto")
    parser.add_argument("--layout", choices=("native", "compact", "cinematic", "focus"))
    parser.add_argument("--codex-version", help="exact host version required for an experimental layout")
    parser.add_argument("--accent", default="#7C8CFF")
    parser.add_argument("--background", type=Path, help="use one background for home and task")
    parser.add_argument("--home-background", type=Path)
    parser.add_argument("--task-background", type=Path)
    parser.add_argument("--background-position", default="70% 40%")
    parser.add_argument("--safe-area", choices=("left", "right", "center", "none"), default="left")
    parser.add_argument("--icon-dir", type=Path)
    parser.add_argument("--source", choices=("generated", "provided", "none", "migrated"))
    parser.add_argument("--codex-min-version", default="26.715")
    parser.add_argument("--bundle-output", type=Path)
    parser.add_argument("--series-id", default="custom")
    parser.add_argument("--series-name", default="自定义主题")
    return parser.parse_args()


def selected_template(appearance: str, requested: str) -> str:
    if requested != "auto":
        return requested
    return "clear-light" if appearance == "light" else "immersive-dark"


def validate_identity(theme_id: str, name: str, position: str) -> None:
    if not THEME_ID.fullmatch(theme_id):
        raise ValueError("theme id must be 1-48 lowercase letters, numbers, or hyphens")
    if not name.strip() or len(name.strip()) > 80:
        raise ValueError("theme name must contain 1-80 characters")
    if not POSITION.fullmatch(position):
        raise ValueError("background position must look like '70% 40%'")


def host_adapter_registry_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise FileNotFoundError("LOCALAPPDATA is unavailable; Codex Theme Studio cannot be detected")
    candidate = Path(local_app_data) / "CodexThemeStudio" / "engine" / "assets" / "host-adapters.json"
    if not candidate.is_file():
        raise FileNotFoundError(
            "Codex Theme Studio is not installed; experimental layouts require its trusted host adapter registry"
        )
    return candidate


def studio_client_path() -> Path | None:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        return None
    return Path(local_app_data) / "Programs" / "Codex Theme Studio" / "CodexThemeStudio.exe"


def assert_layout_approved(mode: str, codex_version: str | None) -> None:
    if mode == "native":
        return
    if not codex_version:
        raise ValueError(
            f"experimental layout {mode} requires an exact --codex-version and COMPLETE layout matrix"
        )
    registry = json.loads(host_adapter_registry_path().read_text(encoding="utf-8"))
    matches = [
        item for item in registry.get("adapters", [])
        if codex_version in item.get("codexVersions", [])
    ]
    status = (
        matches[0].get("layoutMatrix", {}).get(mode, {}).get("status")
        if len(matches) == 1 else None
    )
    if status != "COMPLETE":
        raise ValueError(
            f"experimental layout {mode} is not COMPLETE in the {codex_version} host layout matrix"
        )


def copy_background(source: Path | None, destination: Path, file_name: str) -> str | None:
    if source is None:
        return None
    source = source.expanduser().resolve(strict=True)
    if source.stat().st_size > 20 * 1024 * 1024:
        raise ValueError(f"background exceeds 20 MB: {source}")
    width, height = read_image_size(source)
    if width < 1600 or height < 900 or abs(width / height - 16 / 9) > 0.03:
        raise ValueError(f"background must be at least 1600x900 and approximately 16:9; got {width}x{height}")
    extension = ".png" if source.suffix.lower() == ".png" else ".jpg"
    relative = f"assets/{file_name}{extension}"
    shutil.copy2(source, destination / relative)
    return relative


def write_default_icon(path: Path, slot: str) -> None:
    path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="{DEFAULT_ICON_PATHS[slot]}"/></svg>\n',
        encoding="utf-8",
    )


def build_icons(root: Path, icon_dir: Path | None) -> dict[str, str]:
    icon_root = root / "assets" / "icons"
    icon_root.mkdir(parents=True, exist_ok=True)
    icons: dict[str, str] = {}
    custom_root = icon_dir.expanduser().resolve(strict=True) if icon_dir else None
    for slot in sorted(SEMANTIC_ICON_SLOTS):
        custom = None
        if custom_root:
            for extension in (".svg", ".png"):
                candidate = custom_root / f"{slot}{extension}"
                if candidate.is_file():
                    custom = candidate
                    break
        if custom:
            if custom.stat().st_size > 256 * 1024:
                raise ValueError(f"icon exceeds 256 KB: {custom}")
            if custom.suffix.lower() == ".svg":
                validate_safe_svg(custom)
            relative = f"assets/icons/{slot}{custom.suffix.lower()}"
            shutil.copy2(custom, root / relative)
        else:
            relative = f"assets/icons/{slot}.svg"
            write_default_icon(root / relative, slot)
        icons[slot] = relative
    return icons


def build_payload(root: Path, args: argparse.Namespace, *, theme_id: str, name: str, appearance: str) -> dict[str, Any]:
    template_name = selected_template(appearance, args.template)
    preset = json.loads(json.dumps(TEMPLATES[template_name]))
    accent = normalize_hex("#D7AE55" if template_name == "obsidian-gold" and args.accent == "#7C8CFF" else args.accent)
    assets_root = root / "assets"
    assets_root.mkdir(parents=True, exist_ok=True)
    shared = args.background
    home = copy_background(args.home_background or shared, root, "home-background")
    task = copy_background(args.task_background or shared, root, "task-background")
    icons = build_icons(root, args.icon_dir)
    palette = {"accent": accent, "accentContrast": best_contrast(accent), **preset["palette"]}
    layout = preset["layout"]
    if args.layout:
        assert_layout_approved(args.layout, getattr(args, "codex_version", None))
        layout["mode"] = args.layout
    source = args.source or ("provided" if home or task or args.icon_dir else "none")
    return {
        "schemaVersion": 2,
        "id": theme_id,
        "name": name.strip(),
        "appearance": appearance,
        "assets": {"homeBackground": home, "taskBackground": task, "icons": icons},
        "palette": palette,
        "materials": preset["materials"],
        "layout": layout,
        "art": {
            "focusX": int(args.background_position.split()[0][:-1]) / 100,
            "focusY": int(args.background_position.split()[1][:-1]) / 100,
            "safeArea": args.safe_area,
            **preset["art"],
        },
        "compatibility": {
            "codexMinVersion": args.codex_min_version,
            "rendererFingerprint": "codex-theme-studio-v2",
            "generatorVersion": GENERATOR_VERSION,
        },
        "provenance": {"generator": "codex-theme-generator", "source": source, "template": template_name},
    }


def render_preview(theme: dict[str, Any]) -> str:
    palette, materials, layout, assets, art = (
        theme["palette"], theme["materials"], theme["layout"], theme["assets"], theme["art"]
    )
    home = f"url('{assets['homeBackground']}')" if assets["homeBackground"] else "radial-gradient(circle at 70% 25%, color-mix(in srgb,var(--accent) 34%,transparent),transparent 45%)"
    icon = assets["icons"]["newTask"]
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(theme['name'])} · Codex Theme Studio</title><style>
:root{{--accent:{palette['accent']};--accent-ink:{palette['accentContrast']};--canvas:{palette['canvas']};--surface:{palette['surface']};--raised:{palette['surfaceElevated']};--text:{palette['text']};--muted:{palette['textMuted']};--border:{palette['border']};--menu:{palette['menu']};--panel:{palette['panel']};--composer:{palette['composer']};--radius:{materials['radius']}px;--panel-alpha:{materials['panelOpacity']};}}
*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;color:var(--text);font:15px/1.5 Inter,'Segoe UI',sans-serif;background:linear-gradient(rgb(0 0 0/{1-art['homeIntensity']:.2f}),rgb(0 0 0/{1-art['homeIntensity']:.2f})),{home},var(--canvas);background-size:cover;background-position:{art['focusX']*100:.0f}% {art['focusY']*100:.0f}%}}.shell{{min-height:100vh;display:grid;grid-template-columns:{layout['sidebarWidth']}px 1fr}}aside{{padding:22px 16px;border-right:1px solid var(--border);background:color-mix(in srgb,var(--menu) calc(var(--panel-alpha)*100%),transparent)}}main{{padding:40px}}.content{{max-width:{layout['contentMaxWidth']}px;margin:auto}}nav{{display:grid;gap:8px;margin-top:28px}}nav div,.card,.composer{{border:1px solid var(--border);border-radius:var(--radius);background:color-mix(in srgb,var(--panel) calc(var(--panel-alpha)*100%),transparent);box-shadow:0 12px 40px rgb(0 0 0/.12)}}nav div{{padding:10px 12px}}nav img{{width:18px;vertical-align:-4px;margin-right:9px}}h1{{font-size:42px;margin:18vh 0 10px}}.muted{{color:var(--muted)}}.badge{{color:var(--accent)}}.card{{padding:22px;margin-top:28px}}.composer{{padding:15px 16px;margin-top:18px;display:flex;justify-content:space-between}}button{{border:0;border-radius:10px;padding:8px 14px;background:var(--accent);color:var(--accent-ink)}}
</style></head><body><div class="shell"><aside><strong>Codex Theme Studio</strong><p class="muted">{html.escape(layout['mode'])}</p><nav><div><img src="{icon}">新任务</div><div>项目</div><div>技能</div></nav></aside><main><div class="content"><span class="badge">{html.escape(theme['appearance'])}</span><h1>{html.escape(theme['name'])}</h1><p class="muted">Theme Pack v2 全量静态预览</p><section class="card">背景、语义图标、菜单、面板和布局均来自同一主题包。</section><div class="composer"><span class="muted">Ask Codex anything…</span><button>发送</button></div></div></main></div></body></html>"""


def render_readme(theme: dict[str, Any]) -> str:
    return f"""# {theme['name']}

- Theme ID: `{theme['id']}`
- Schema: `Theme Pack v2`
- Appearance: `{theme['appearance']}`
- Layout: `{theme['layout']['mode']}`
- Generator: `codex-theme-generator {GENERATOR_VERSION}`

此主题包包含背景、语义图标、面板材质、完整配色和白名单布局预设。主题包不包含任意 CSS、JavaScript 或 DOM selector；由 Codex Theme Studio 验证后应用。
"""


def write_theme(root: Path, theme: dict[str, Any]) -> None:
    (root / "theme.json").write_text(json.dumps(theme, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (root / "preview.html").write_text(render_preview(theme), encoding="utf-8")
    (root / "README.md").write_text(render_readme(theme), encoding="utf-8")
    if theme["appearance"] == "auto":
        for variant in ("dark", "light"):
            write_native_files(
                root,
                compile_native_payload(theme, variant=variant),
                suffix=f"-{variant}",
            )
    else:
        write_native_files(root, compile_native_payload(theme))


def atomic_build(args: argparse.Namespace) -> tuple[Path, list[str], Path | None]:
    output = args.output_dir.expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing path: {output}")
    bundle_output = args.bundle_output.expanduser().resolve() if args.bundle_output else None
    if bundle_output and bundle_output.exists():
        raise FileExistsError(f"refusing to overwrite existing path: {bundle_output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}-", dir=output.parent))
    bundle_staging: Path | None = None
    built_ids: list[str] = []
    try:
        if args.pair:
            themes_root = staging / "themes"
            themes_root.mkdir()
            variants = ((f"{args.theme_id}-dark", f"{args.name} 深色", "dark"),
                        (f"{args.theme_id}-light", f"{args.name} 浅色", "light"))
            for theme_id, name, appearance in variants:
                validate_identity(theme_id, name, args.background_position)
                theme_root = themes_root / theme_id
                theme_root.mkdir()
                theme = build_payload(theme_root, args, theme_id=theme_id, name=name, appearance=appearance)
                write_theme(theme_root, theme)
                built_ids.append(theme_id)
        else:
            validate_identity(args.theme_id, args.name, args.background_position)
            theme = build_payload(staging, args, theme_id=args.theme_id, name=args.name, appearance=args.appearance)
            write_theme(staging, theme)

        from validate_theme import validate
        validation_roots = [staging / "themes" / item for item in built_ids] if args.pair else [staging]
        reports = [validate(item) for item in validation_roots]
        if any(report["status"] != "COMPLETE" for report in reports):
            raise ValueError("generated theme failed validation: " + json.dumps(reports, ensure_ascii=False))
        final_ids = built_ids or [args.theme_id]
        if bundle_output:
            theme_roots = (
                [(item, staging / "themes" / item) for item in final_ids]
                if args.pair
                else [(args.theme_id, staging)]
            )
            bundle_staging = create_bundle(
                bundle_output,
                bundle_id=f"{args.series_id}-{args.theme_id}",
                name=args.name,
                series_id=args.series_id,
                series_name=args.series_name,
                themes=theme_roots,
            )
        os.replace(staging, output)
        if bundle_output and bundle_staging:
            try:
                os.replace(bundle_staging, bundle_output)
            except Exception:
                shutil.rmtree(output, ignore_errors=True)
                raise
        return output, final_ids, bundle_output
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        if bundle_staging:
            bundle_staging.unlink(missing_ok=True)
        raise


def main() -> int:
    try:
        output, theme_ids, bundle_output = atomic_build(parse_args())
    except (FileExistsError, FileNotFoundError, OSError, ValueError) as error:
        print(json.dumps({
            "status": "BLOCKED",
            "packStatus": "BLOCKED",
            "bundleStatus": "BLOCKED",
            "error": str(error),
            "importStatus": "NOT_RUN",
            "activationStatus": "NOT_RUN",
        }, ensure_ascii=False))
        return 2
    studio_client = studio_client_path()
    print(json.dumps({
        "status": "COMPLETE",
        "packStatus": "COMPLETE",
        "themeDir": str(output),
        "themeIds": theme_ids,
        "bundlePath": str(bundle_output) if bundle_output else None,
        "bundleStatus": "COMPLETE" if bundle_output else "NOT_REQUESTED",
        "studioDetected": bool(studio_client and studio_client.is_file()),
        "handoffStatus": "READY",
        "importStatus": "NOT_RUN",
        "activationStatus": "NOT_RUN",
        "notRun": ["import", "activate", "runtimeVerify"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
