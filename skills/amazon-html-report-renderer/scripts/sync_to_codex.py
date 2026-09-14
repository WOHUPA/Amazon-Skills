#!/usr/bin/env python3
"""Sync the amazon-html-report-renderer skill from a source copy to the Codex skills directory.

Codex discovers skills under `~/.codex/skills/<skill-name>/SKILL.md`. On this machine the
project folder `skill-work` itself is a Windows junction to
`~/.codex/skills/amazon-html-report-renderer` (which is a junction to `D:\\DevData\\.codex`
on the real disk), so editing the project IS editing the installed skill. This script is
the safety net for that setup: when the source and the target resolve to the same physical
directory it reports "in-sync via junction" and exits cleanly; when the source is an
independent copy (e.g. a git checkout) it mirrors files and verifies hashes.

    python scripts/sync_to_codex.py                # sync to ~/.codex/skills/<name>
    python scripts/sync_to_codex.py --dry-run      # preview what would change
    python scripts/sync_to_codex.py --target DIR   # sync to an explicit target
    python scripts/sync_to_codex.py --json         # machine-readable summary

Safety rules:
- Only writes into the resolved target skill directory (or --target).
- Never deletes files; --prune additionally removes target files that are absent
  in the source (excluding caches) - opt-in only.
- Every copied file is re-hashed after the copy and the result must match.
- Exit code 0 = sync clean or completed; 2 = verification failure / error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

EXCLUDE_DIRS = {"__pycache__", "node_modules", ".git"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo"}
EXCLUDE_FILES = {".DS_Store"}


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def should_exclude(rel_path: Path) -> bool:
    parts = rel_path.parts
    if any(part in EXCLUDE_DIRS for part in parts):
        return True
    if rel_path.name in EXCLUDE_FILES:
        return True
    return rel_path.suffix.lower() in EXCLUDE_SUFFIXES


def skill_name_from_frontmatter(skill_root: Path) -> str | None:
    """Read the `name` field from SKILL.md YAML frontmatter (the Codex skill id)."""
    try:
        text = (skill_root / "SKILL.md").read_text(encoding="utf-8-sig")
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    for line in text[3:end].splitlines():
        if line.startswith("name:"):
            value = line.split(":", 1)[1].strip().strip("\"'")
            return value or None
    return None


def default_target(skill_root: Path) -> Path:
    """Resolve ~/.codex/skills/<skill-name>, following a junction if present."""
    home = Path(os.environ.get("USERPROFILE") or Path.home())
    name = skill_name_from_frontmatter(skill_root) or skill_root.name
    return home / ".codex" / "skills" / name


def collect_source_files(skill_root: Path) -> list[Path]:
    files = []
    for path in sorted(skill_root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(skill_root)
        if not should_exclude(rel):
            files.append(path)
    return files


def plan_sync(source_files: list[Path], skill_root: Path, target_root: Path) -> list[dict]:
    changes = []
    for src in source_files:
        rel = src.relative_to(skill_root)
        dst = target_root / rel
        if dst.exists():
            if sha256_file(src) == sha256_file(dst):
                changes.append({"rel": rel.as_posix(), "action": "same"})
                continue
            changes.append({"rel": rel.as_posix(), "action": "update"})
        else:
            changes.append({"rel": rel.as_posix(), "action": "create"})
    return changes


def prune_target(skill_root: Path, target_root: Path, *, dry_run: bool = False) -> list[Path]:
    """Opt-in: remove target files absent from the source (caches excluded)."""
    removed = []
    if not target_root.exists():
        return removed
    source_rels = {
        src.relative_to(skill_root).as_posix()
        for src in collect_source_files(skill_root)
    }
    for dst in sorted(target_root.rglob("*")):
        if not dst.is_file():
            continue
        rel = dst.relative_to(target_root)
        if should_exclude(rel):
            continue
        if rel.as_posix() not in source_rels:
            if not dry_run:
                dst.unlink()
            removed.append(rel)
    return removed


def verify_sync(source_files: list[Path], skill_root: Path, target_root: Path) -> list[str]:
    failures = []
    for src in source_files:
        rel = src.relative_to(skill_root)
        dst = target_root / rel
        if not dst.exists():
            failures.append(f"missing after sync: {rel.as_posix()}")
            continue
        if sha256_file(src) != sha256_file(dst):
            failures.append(f"hash mismatch after sync: {rel.as_posix()}")
    return failures


def emit_json(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    sys.stdout.flush()


def main() -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(
        description="Sync the project skill to the Codex skills directory."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="skill source directory (default: this script's parent's parent)",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=None,
        help="target skill directory (default: ~/.codex/skills/<skill-name>)",
    )
    parser.add_argument("--dry-run", action="store_true", help="preview changes only")
    parser.add_argument("--prune", action="store_true", help="remove target files absent in source")
    parser.add_argument("--json", action="store_true", help="emit a single JSON object on stdout")
    args = parser.parse_args()

    # Keep the junction view of the source (do not resolve through it): the project
    # folder may itself be a junction to the Codex install, which must be detected
    # by comparing physical locations below.
    skill_root = (args.source or Path(__file__).absolute().parent.parent)
    skill_md = skill_root / "SKILL.md"
    if not skill_md.exists():
        message = f"SKILL.md not found in source: {skill_root}"
        if args.json:
            emit_json({"ok": False, "error": message})
        else:
            print(f"ERROR: {message}")
        return 2

    target_root = (args.target or default_target(skill_root))
    skill_real = skill_root.resolve()
    target_real = target_root.resolve()

    if skill_real == target_real:
        # The project folder is (or points to) the installed skill itself.
        if args.json:
            emit_json(
                {
                    "ok": True,
                    "in_sync_via_junction": True,
                    "skill": skill_root.name,
                    "source": str(skill_real),
                    "target": str(target_real),
                    "note": "source and target are the same physical directory; edits take effect immediately",
                }
            )
        else:
            print(f"in-sync via junction: {skill_real}")
            print("source and target are the same physical directory; edits take effect immediately")
        return 0

    source_files = collect_source_files(skill_root)
    changes = plan_sync(source_files, skill_root, target_root)

    to_change = [c for c in changes if c["action"] != "same"]
    removed = (
        prune_target(skill_root, target_root, dry_run=False)
        if args.prune and not args.dry_run
        else []
    )
    removed_preview = (
        prune_target(skill_root, target_root, dry_run=True)
        if args.prune and args.dry_run
        else []
    )

    if args.dry_run:
        if args.json:
            emit_json(
                {
                    "ok": True,
                    "dry_run": True,
                    "skill": skill_root.name,
                    "source": str(skill_root),
                    "target": str(target_root),
                    "files": len(source_files),
                    "same": sum(1 for c in changes if c["action"] == "same"),
                    "to_change": len(to_change),
                    "changes": [c for c in changes if c["action"] != "same"],
                    "prune_removals": [p.as_posix() for p in removed_preview],
                }
            )
        else:
            print(f"[dry-run] source: {skill_root}")
            print(f"[dry-run] target: {target_root}")
            print(f"[dry-run] {len(source_files)} files, {len(to_change)} would change")
            for change in to_change:
                print(f"  {change['action']:6s} {change['rel']}")
            for rel in removed_preview:
                print(f"  prune {rel.as_posix()}")
        return 0

    if to_change:
        target_root.mkdir(parents=True, exist_ok=True)
        for change in to_change:
            src = skill_root / change["rel"]
            dst = target_root / change["rel"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(src.read_bytes())
            if not args.json:
                print(f"  {change['action']:6s} {change['rel']}")

    failures = verify_sync(source_files, skill_root, target_root)
    if args.json:
        emit_json(
            {
                "ok": not failures,
                "skill": skill_root.name,
                "source": str(skill_root),
                "target": str(target_root),
                "files": len(source_files),
                "same": sum(1 for c in changes if c["action"] == "same"),
                "changed": len(to_change),
                "pruned": len(removed),
                "verification_failures": failures,
            }
        )
    else:
        print(f"synced: {len(to_change)} changed, {sum(1 for c in changes if c['action'] == 'same')} identical")
        if removed:
            print(f"pruned: {len(removed)} file(s)")
        if failures:
            for failure in failures:
                print(f"ERROR: {failure}")
            return 2
        print(f"OK: all {len(source_files)} files verified identical to {target_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
