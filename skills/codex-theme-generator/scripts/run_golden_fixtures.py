"""Run deterministic contract checks for codex-theme-generator."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("json",), default="json")
    parser.parse_args()
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    builder = (ROOT / "scripts" / "build_theme.py").read_text(encoding="utf-8")
    validator = (ROOT / "scripts" / "validate_theme.py").read_text(encoding="utf-8")
    native_compiler = (ROOT / "scripts" / "compile_native_theme.py").read_text(encoding="utf-8")
    bundle_builder = (ROOT / "scripts" / "bundle_theme.py").read_text(encoding="utf-8")
    checks = [
        (1, "完整深色主题", "Theme Pack v2" in skill and "SEMANTIC_ICON_SLOTS" in builder),
        (2, "双模式主题", "--pair" in skill and "themes_root" in builder),
        (3, "实验布局只读检测", all(item in builder for item in (
            "assert_layout_approved", "CodexThemeStudio", "host_adapter_registry_path"
        ))),
        (4, "三层职责分离", all(item in skill for item in (
            "不携带、不安装、不更新", "codex-theme-selector", "importStatus=NOT_RUN"
        )) and not (ROOT / "tool" / "codex-theme-studio").exists()),
        (5, "切换反例", "codex-theme-selector" in skill and "不导入、激活" in skill),
        (6, "旧主题迁移反例", "codex-skin-maker" in skill),
        (7, "官方模式反例", "官方" in skill and "不适用" in skill),
        (8, "安全失败关闭", "FORBIDDEN_TERMS" in validator and "os.replace" in builder),
        (9, "静态与运行状态分离", all(item in builder for item in (
            '"packStatus"', '"handoffStatus"', '"importStatus"', '"activationStatus"'
        ))),
        (10, "原生主题编译", all(item in native_compiler for item in (
            "codex-theme-v1:", "write_native_files", "DEFAULT_CODE_THEME_ID", "NATIVE_DEFAULTS"
        ))),
        (11, "Bundle 一键交付", all(item in builder for item in (
            "--bundle-output", "--series-id", "--series-name", '"bundleStatus"'
        )) and all(item in bundle_builder for item in (
            "bundle.json", "themes/", "sha256", "ZIP_DEFLATED"
        ))),
    ]
    results = [{"id": case_id, "name": name, "status": "PASS" if passed else "FAIL"} for case_id, name, passed in checks]
    failed = sum(item["status"] == "FAIL" for item in results)
    print(json.dumps({"status": "PASS" if not failed else "FAIL", "total": len(results), "passed": len(results) - failed, "failed": failed, "results": results}, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
