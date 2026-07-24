#!/usr/bin/env python3
"""Create deterministic, data-only Codex Theme Bundle v1 archives."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable


BUNDLE_SCHEMA_VERSION = 1
BUNDLE_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_BUNDLE_ID_LENGTH = 80


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_bundle_identity(bundle_id: str, name: str, series_id: str, series_name: str) -> None:
    for label, value in (("bundle id", bundle_id), ("series id", series_id)):
        if len(value) > MAX_BUNDLE_ID_LENGTH or not BUNDLE_ID.fullmatch(value):
            raise ValueError(f"{label} must be lowercase letters, numbers, or hyphens")
    for label, value in (("bundle name", name), ("series name", series_name)):
        if not value.strip() or len(value.strip()) > 80:
            raise ValueError(f"{label} must contain 1-80 characters")


def create_bundle(
    destination: Path,
    *,
    bundle_id: str,
    name: str,
    series_id: str,
    series_name: str,
    themes: Iterable[tuple[str, Path]],
) -> Path:
    """Build a Bundle v1 beside the requested destination without overwriting it."""
    destination = destination.expanduser().resolve()
    if destination.suffix.lower() != ".codextheme":
        raise ValueError("bundle output must use the .codextheme extension")
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite existing path: {destination}")
    _validate_bundle_identity(bundle_id, name, series_id, series_name)

    theme_entries: list[dict[str, str]] = []
    source_files: list[tuple[Path, str]] = []
    seen_ids: set[str] = set()
    for theme_id, source_root in themes:
        if theme_id in seen_ids:
            raise ValueError(f"duplicate theme id in bundle: {theme_id}")
        seen_ids.add(theme_id)
        source_root = source_root.resolve(strict=True)
        theme_entries.append({"id": theme_id, "path": f"themes/{theme_id}"})
        for file_path in sorted(path for path in source_root.rglob("*") if path.is_file()):
            relative = file_path.relative_to(source_root).as_posix()
            source_files.append((file_path, f"themes/{theme_id}/{relative}"))

    if not theme_entries:
        raise ValueError("bundle must contain at least one theme")

    file_entries = [
        {"path": archive_path, "size": source.stat().st_size, "sha256": _sha256(source)}
        for source, archive_path in source_files
    ]
    manifest = {
        "schemaVersion": BUNDLE_SCHEMA_VERSION,
        "bundleId": bundle_id,
        "name": name.strip(),
        "series": {"id": series_id, "name": series_name.strip()},
        "themes": theme_entries,
        "files": file_entries,
    }

    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.stem}-",
        suffix=".codextheme.tmp",
        dir=destination.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(
            temporary,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=6,
        ) as archive:
            archive.writestr(
                "bundle.json",
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            )
            for source, archive_path in source_files:
                archive.write(source, archive_path)
        return temporary
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
