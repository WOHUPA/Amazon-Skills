"""Generate an offline HTML gallery and contact sheet for a Dream Skin pack."""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack-root", required=True, type=Path)
    parser.add_argument("--output-html", required=True, type=Path)
    parser.add_argument("--output-image", required=True, type=Path)
    return parser.parse_args()


def load_manifest(pack_root: Path) -> dict[str, Any]:
    candidates = sorted(pack_root.glob("*manifest*.json"))
    if len(candidates) != 1:
        raise ValueError(f"Expected one manifest JSON, found {len(candidates)}")
    with candidates[0].open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    if not isinstance(manifest.get("themes"), list) or not manifest["themes"]:
        raise ValueError("Manifest must contain a non-empty themes array")
    return manifest


def resolve_theme(pack_root: Path, entry: dict[str, Any]) -> dict[str, Any]:
    theme_id = str(entry.get("id", ""))
    theme_dir = (pack_root / str(entry.get("themeDir", ""))).resolve()
    themes_root = (pack_root / "themes").resolve()
    if theme_dir.parent != themes_root or theme_dir.name != theme_id:
        raise ValueError(f"Unsafe or mismatched theme path: {theme_id}")
    with (theme_dir / "theme.json").open("r", encoding="utf-8-sig") as handle:
        metadata = json.load(handle)
    if metadata.get("id") != theme_id:
        raise ValueError(f"Theme metadata ID mismatch: {theme_id}")
    image_path = (theme_dir / str(metadata.get("image", ""))).resolve()
    if image_path.parent != theme_dir or not image_path.is_file():
        raise ValueError(f"Theme image is invalid: {theme_id}")
    return {**entry, "metadata": metadata, "imagePath": image_path}


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def make_contact_sheet(themes: list[dict[str, Any]], output_path: Path) -> None:
    columns = 3
    tile_width, image_height, footer_height = 600, 338, 92
    rows = (len(themes) + columns - 1) // columns
    canvas = Image.new("RGB", (columns * tile_width, rows * (image_height + footer_height)), "#0b0910")
    draw = ImageDraw.Draw(canvas)
    title_font = load_font(27, bold=True)
    id_font = load_font(17)

    for index, theme in enumerate(themes):
        column, row = index % columns, index // columns
        x, y = column * tile_width, row * (image_height + footer_height)
        with Image.open(theme["imagePath"]) as source:
            tile = ImageOps.fit(source.convert("RGB"), (tile_width, image_height), method=Image.Resampling.LANCZOS)
        canvas.paste(tile, (x, y))
        accent = theme["metadata"].get("palette", {}).get("accent", "#6f5cff")
        draw.rectangle((x, y + image_height, x + tile_width, y + image_height + footer_height), fill="#14101b")
        draw.rectangle((x, y + image_height, x + 7, y + image_height + footer_height), fill=accent)
        draw.text((x + 24, y + image_height + 12), str(theme["name"]), font=title_font, fill="#f7f0ff")
        draw.text((x + 24, y + image_height + 53), str(theme["id"]), font=id_font, fill="#a89db8")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, "JPEG", quality=92, optimize=True)


def make_html(manifest: dict[str, Any], themes: list[dict[str, Any]], output_path: Path) -> None:
    cards: list[str] = []
    for theme in themes:
        image_url = f"../themes/{theme['id']}/{theme['metadata']['image']}"
        copy_text = f"导入主题 {theme['id']}"
        cards.append(
            f"""
            <article class="card" style="--accent:{html.escape(theme['metadata'].get('palette', {}).get('accent', '#6f5cff'))}">
              <img src="{html.escape(image_url)}" alt="{html.escape(str(theme['name']))}" loading="lazy">
              <div class="body">
                <div class="eyebrow">{html.escape(str(theme['character']))} · {html.escape(str(theme['technique']))}</div>
                <h2>{html.escape(str(theme['name']))}</h2>
                <p>{html.escape(str(theme['scene']))}</p>
                <code>{html.escape(str(theme['id']))}</code>
                <button type="button" data-copy={json.dumps(copy_text, ensure_ascii=False)}>复制导入指令</button>
              </div>
            </article>
            """
        )

    document = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(str(manifest.get('name', 'Codex 主题画廊')))}</title>
  <style>
    :root {{ color-scheme: dark; font-family: "Microsoft YaHei UI", system-ui, sans-serif; background:#09070d; color:#f8f3ff; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:radial-gradient(circle at 50% -10%,#241733 0,#0d0912 38%,#08060b 100%); }}
    header {{ max-width:1480px; margin:auto; padding:48px 28px 24px; }}
    .kicker {{ color:#c6b3db; letter-spacing:.16em; text-transform:uppercase; font-size:13px; }}
    h1 {{ margin:10px 0 8px; font-size:clamp(32px,4vw,52px); line-height:1.1; }}
    header p {{ margin:0; color:#a99fb3; font-size:16px; }}
    main {{ max-width:1480px; margin:auto; padding:20px 28px 64px; display:grid; grid-template-columns:repeat(auto-fit,minmax(360px,1fr)); gap:22px; }}
    .card {{ overflow:hidden; border:1px solid #2b2234; border-radius:18px; background:#130f18; box-shadow:0 22px 70px #0008; }}
    .card img {{ display:block; width:100%; aspect-ratio:16/9; object-fit:cover; background:#09070d; }}
    .body {{ padding:20px; border-top:3px solid var(--accent); }}
    .eyebrow {{ color:var(--accent); font-size:13px; font-weight:700; letter-spacing:.05em; }}
    h2 {{ margin:8px 0 8px; font-size:24px; }}
    .body p {{ min-height:48px; margin:0 0 14px; color:#bdb3c6; line-height:1.55; }}
    code {{ display:block; overflow:auto; padding:10px 12px; border-radius:9px; background:#09070d; color:#ded5e6; }}
    button {{ width:100%; margin-top:14px; padding:11px 14px; border:0; border-radius:10px; background:var(--accent); color:#100b15; font-weight:800; cursor:pointer; }}
    button:focus-visible {{ outline:3px solid #fff; outline-offset:3px; }}
  </style>
</head>
<body>
  <header>
    <div class="kicker">Codex Dream Skin · {len(themes)} themes</div>
    <h1>{html.escape(str(manifest.get('name', 'Codex 主题画廊')))}</h1>
    <p>点击复制精确导入指令；预览本身不会导入或切换任何主题。</p>
  </header>
  <main>{''.join(cards)}</main>
  <script>
    document.querySelectorAll('button[data-copy]').forEach((button) => {{
      button.addEventListener('click', async () => {{
        await navigator.clipboard.writeText(button.dataset.copy);
        button.textContent = '已复制';
      }});
    }});
  </script>
</body>
</html>
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(document, encoding="utf-8")


def main() -> int:
    args = parse_args()
    pack_root = args.pack_root.resolve()
    manifest = load_manifest(pack_root)
    themes = [resolve_theme(pack_root, entry) for entry in manifest["themes"]]
    make_contact_sheet(themes, args.output_image.resolve())
    make_html(manifest, themes, args.output_html.resolve())
    sys.stdout.write(
        json.dumps(
            {
                "status": "PREVIEW_ONLY",
                "count": len(themes),
                "html": str(args.output_html.resolve()),
                "contactSheet": str(args.output_image.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
