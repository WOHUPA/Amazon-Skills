"""Shared validation helpers for Codex Theme Pack v2."""

from __future__ import annotations

import re
import struct
import xml.etree.ElementTree as ET
from pathlib import Path


HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
THEME_ID = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,46}[a-z0-9])?$")
POSITION = re.compile(r"^(?:100|[0-9]{1,2})% (?:100|[0-9]{1,2})%$")
SEMANTIC_ICON_SLOTS = {
    "newTask", "search", "projects", "history", "attach", "send", "settings", "skills",
}
SAFE_SVG_ELEMENTS = {"svg", "g", "path", "circle", "rect", "line", "polyline", "polygon"}
SAFE_SVG_ATTRIBUTES = {
    "viewBox", "width", "height", "fill", "stroke", "stroke-width", "stroke-linecap",
    "stroke-linejoin", "d", "cx", "cy", "r", "x", "y", "x1", "y1", "x2", "y2",
    "rx", "ry", "points", "opacity", "transform",
}


def normalize_hex(value: str) -> str:
    """Return an uppercase #RRGGBB color or raise ValueError."""
    if not HEX_COLOR.fullmatch(value):
        raise ValueError(f"invalid color: {value}; expected #RRGGBB")
    return value.upper()


def rgb(value: str) -> tuple[int, int, int]:
    value = normalize_hex(value)
    return tuple(int(value[index : index + 2], 16) for index in (1, 3, 5))


def relative_luminance(value: str) -> float:
    def linear(channel: int) -> float:
        normalized = channel / 255
        return normalized / 12.92 if normalized <= 0.04045 else ((normalized + 0.055) / 1.055) ** 2.4

    red, green, blue = rgb(value)
    return 0.2126 * linear(red) + 0.7152 * linear(green) + 0.0722 * linear(blue)


def contrast_ratio(first: str, second: str) -> float:
    lighter, darker = sorted((relative_luminance(first), relative_luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def best_contrast(color: str) -> str:
    black = contrast_ratio(color, "#000000")
    white = contrast_ratio(color, "#FFFFFF")
    return "#000000" if black >= white else "#FFFFFF"


def read_image_size(path: Path) -> tuple[int, int]:
    """Read PNG or JPEG dimensions using only the Python standard library."""
    with path.open("rb") as stream:
        signature = stream.read(24)
        if signature.startswith(b"\x89PNG\r\n\x1a\n"):
            return struct.unpack(">II", signature[16:24])

        if signature[:2] != b"\xff\xd8":
            raise ValueError("background must be PNG or JPEG")

        stream.seek(2)
        while True:
            marker_start = stream.read(1)
            if not marker_start:
                break
            if marker_start != b"\xff":
                continue
            marker = stream.read(1)
            while marker == b"\xff":
                marker = stream.read(1)
            if marker in {b"\xd8", b"\xd9"}:
                continue
            length_data = stream.read(2)
            if len(length_data) != 2:
                break
            segment_length = struct.unpack(">H", length_data)[0]
            if marker and marker[0] in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                segment = stream.read(5)
                if len(segment) != 5:
                    break
                height, width = struct.unpack(">HH", segment[1:5])
                return width, height
            stream.seek(segment_length - 2, 1)

    raise ValueError("could not read image dimensions")


def ensure_relative_asset(value: str, *, prefix: str = "assets/") -> str:
    """Validate a forward-slash relative asset path without traversal."""
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("asset path must be a non-empty forward-slash relative path")
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts or not value.startswith(prefix):
        raise ValueError(f"asset path must remain below {prefix}")
    return value


def validate_safe_svg(path: Path) -> None:
    """Reject scripts, external resources, event handlers, and unknown SVG markup."""
    if path.stat().st_size > 256 * 1024:
        raise ValueError(f"SVG icon exceeds 256 KB: {path.name}")
    try:
        root = ET.fromstring(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ET.ParseError) as error:
        raise ValueError(f"invalid SVG icon {path.name}: {error}") from error
    for node in root.iter():
        element = node.tag.rsplit("}", 1)[-1]
        if element not in SAFE_SVG_ELEMENTS:
            raise ValueError(f"unsupported SVG element <{element}> in {path.name}")
        for attribute, value in node.attrib.items():
            name = attribute.rsplit("}", 1)[-1]
            if name not in SAFE_SVG_ATTRIBUTES or name.lower().startswith("on"):
                raise ValueError(f"unsupported SVG attribute {name} in {path.name}")
            if "url(" in value.lower() or "javascript:" in value.lower() or "data:" in value.lower():
                raise ValueError(f"external SVG value is not allowed in {path.name}")
