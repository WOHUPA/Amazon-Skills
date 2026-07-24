"""Run deterministic contract checks for codex-theme-selector."""

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
    script = (ROOT / "scripts" / "theme-selector.ps1").read_text(encoding="utf-8")
    checks = [
        (1, "客户端状态检测", "CodexThemeStudio.exe" in script and "NOT_INSTALLED" in script),
        (2, "只读列表", "'--engine', $Action.ToLowerInvariant()" in script),
        (3, "精确预览", "Assert-ExactThemeId $ThemeId" in script and "'--theme', $ThemeId" in script),
        (4, "导入不激活", "'--package'" in script and "activationStatus=NOT_RUN" in skill),
        (5, "精确激活", "$writeActions" in script and "requires -Confirm" in script and "'--confirm'" in script),
        (6, "回退", "'Rollback'" in script and "上一主题" in skill),
        (7, "暂停与官方外观", "'Pause'" in script and "'Restore'" in script),
        (8, "安装更新反例", "'Install'" not in script and "'Update'" not in script and "不实现客户端安装器或更新器" in skill),
        (9, "生成反例", "codex-theme-generator" in skill and "不生成或重绘主题" in skill),
        (10, "迁移反例", "codex-skin-maker" in skill),
        (11, "原生引擎探测", "--result-file" in script and "engineVersion" in skill and "RuntimeSupervisor" in skill),
    ]
    results = [{"id": case_id, "name": name, "status": "PASS" if passed else "FAIL"} for case_id, name, passed in checks]
    failed = sum(item["status"] == "FAIL" for item in results)
    print(json.dumps({"status": "PASS" if not failed else "FAIL", "total": len(results), "passed": len(results) - failed, "failed": failed, "results": results}, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
