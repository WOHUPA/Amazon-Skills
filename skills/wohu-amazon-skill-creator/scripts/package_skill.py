#!/usr/bin/env python3
"""
Skill Packager - Creates a distributable .skill file of a skill folder

Usage:
    python utils/package_skill.py <path/to/skill-folder> [output-directory]

Example:
    python utils/package_skill.py skills/public/my-skill
    python utils/package_skill.py skills/public/my-skill ./dist
"""

import fnmatch
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.quick_validate import validate_skill

# Patterns to exclude when packaging skills.
EXCLUDE_DIRS = {"__pycache__", "node_modules"}
EXCLUDE_GLOBS = {"*.pyc"}
EXCLUDE_FILES = {".DS_Store"}


def should_exclude(rel_path: Path) -> bool:
    """Check if a path should be excluded from packaging."""
    parts = rel_path.parts
    if any(part in EXCLUDE_DIRS for part in parts):
        return True
    name = rel_path.name
    if name in EXCLUDE_FILES:
        return True
    return any(fnmatch.fnmatch(name, pat) for pat in EXCLUDE_GLOBS)


def package_skill(skill_path, output_dir=None):
    """
    Package a skill folder into a .skill file.

    Args:
        skill_path: Path to the skill folder
        output_dir: Optional output directory for the .skill file (defaults to current directory)

    Returns:
        Path to the created .skill file, or None if error
    """
    skill_path = Path(skill_path).resolve()

    # Validate skill folder exists
    if not skill_path.exists():
        print(f"ERROR: Skill folder not found: {skill_path}")
        return None

    if not skill_path.is_dir():
        print(f"ERROR: Path is not a directory: {skill_path}")
        return None

    # Validate SKILL.md exists
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        print(f"ERROR: SKILL.md not found in {skill_path}")
        return None

    try:
        skill_md.read_text(encoding="utf-8-sig")
    except UnicodeError as exc:
        print(f"ERROR: SKILL.md must use UTF-8 encoding: {exc}")
        return None
    except OSError as exc:
        print(f"ERROR: Cannot read SKILL.md: {exc}")
        return None

    # Run validation before packaging
    print("Validating skill...")
    valid, message = validate_skill(skill_path)
    if not valid:
        print(f"ERROR: Validation failed: {message}")
        print("   Please fix the validation errors before packaging.")
        return None
    print(f"OK: {message}\n")

    # Determine output location
    skill_name = skill_path.name
    if output_dir:
        output_path = Path(output_dir).resolve()
        output_path.mkdir(parents=True, exist_ok=True)
    else:
        output_path = Path.cwd()

    skill_filename = output_path / f"{skill_name}.skill"

    # Create the .skill file (zip format)
    try:
        expected_entries: set[str] = set()
        with zipfile.ZipFile(skill_filename, "w", zipfile.ZIP_DEFLATED) as zipf:
            # Walk through the skill directory, excluding build artifacts
            for file_path in skill_path.rglob("*"):
                if not file_path.is_file():
                    continue
                arcname = file_path.relative_to(skill_path.parent)
                if should_exclude(arcname):
                    print(f"  Skipped: {arcname}")
                    continue
                expected_entries.add(arcname.as_posix())
                zipf.write(file_path, arcname)
                print(f"  Added: {arcname}")

        with zipfile.ZipFile(skill_filename, "r") as zipf:
            archive_entries = set(zipf.namelist())
        missing_entries = sorted(expected_entries - archive_entries)
        cache_entries = sorted(
            name for name in archive_entries
            if "__pycache__" in name or name.endswith(".pyc")
        )
        if missing_entries or cache_entries:
            raise RuntimeError(
                f"Archive verification failed: missing={missing_entries}, cache={cache_entries}"
            )

        print(f"\nOK: Successfully packaged skill to: {skill_filename}")
        return skill_filename

    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile) as exc:
        print(f"ERROR: Error creating .skill file: {exc}")
        return None


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python utils/package_skill.py <path/to/skill-folder> [output-directory]")
        print("\nExample:")
        print("  python utils/package_skill.py skills/public/my-skill")
        print("  python utils/package_skill.py skills/public/my-skill ./dist")
        return 1

    skill_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None

    print(f"Packaging skill: {skill_path}")
    if output_dir:
        print(f"   Output directory: {output_dir}")
    print()

    result = package_skill(skill_path, output_dir)

    return 0 if result else 1


if __name__ == "__main__":
    raise SystemExit(main())
