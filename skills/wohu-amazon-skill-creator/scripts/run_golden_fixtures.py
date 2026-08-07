"""按结构化 manifest 逐案例运行创建器 Golden Set，不调用真实店铺或外部模型。"""
from __future__ import annotations

import argparse
import io
import json
import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = SKILL_ROOT / "references" / "golden_cases.json"


def load_manifest() -> list[dict[str, object]]:
    """加载并严格校验案例 ID、执行模式与测试映射。"""
    try:
        payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Golden manifest 文件不存在: {MANIFEST_PATH}") from exc
    except PermissionError as exc:
        raise RuntimeError(f"无法读取 Golden manifest，权限不足: {MANIFEST_PATH}") from exc
    except UnicodeError as exc:
        raise RuntimeError(f"Golden manifest 编码无法读取（应为 UTF-8）: {MANIFEST_PATH}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Golden manifest JSON 无效: {exc}") from exc

    cases = payload.get("cases") if isinstance(payload, dict) else None
    if payload.get("version") != 2 or not isinstance(cases, list) or not cases:
        raise RuntimeError("Golden manifest 必须是 version=2 且包含非空 cases")
    ids = [case.get("id") for case in cases if isinstance(case, dict)]
    expected = list(range(1, len(cases) + 1))
    if ids != expected:
        raise RuntimeError(f"Golden case ID 必须连续且唯一，期望 {expected}，实际 {ids}")
    for case in cases:
        if case.get("mode") != "contract":
            raise RuntimeError(f"案例 {case.get('id')} mode 必须是 contract")
        test_ids = case.get("test_ids")
        if not isinstance(test_ids, list) or not test_ids or not all(
            isinstance(test_id, str) and test_id.startswith("tests.test_")
            for test_id in test_ids
        ):
            raise RuntimeError(f"案例 {case.get('id')} 缺少合法 test_ids")
    return cases


def validate_test_sources(cases: list[dict[str, object]] | None = None) -> None:
    """在加载测试前确认源文件存在、可读且采用 UTF-8 编码。"""
    selected = cases if cases is not None else load_manifest()
    module_names = sorted(
        {
            ".".join(test_id.split(".")[:2])
            for case in selected
            for test_id in case["test_ids"]
        }
    )
    for module_name in module_names:
        source_path = SKILL_ROOT.joinpath(*module_name.split(".")).with_suffix(".py")
        try:
            source_path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise RuntimeError(f"回归测试文件不存在: {source_path}") from exc
        except PermissionError as exc:
            raise RuntimeError(f"无法读取回归测试文件，权限不足: {source_path}") from exc
        except IsADirectoryError as exc:
            raise RuntimeError(f"回归测试路径不是文件: {source_path}") from exc
        except UnicodeError as exc:
            raise RuntimeError(f"回归测试文件编码无法读取（应为 UTF-8）: {source_path}") from exc


def run_cases(cases: list[dict[str, object]]) -> dict[str, object]:
    """逐案例运行映射测试，确保声明覆盖与实际执行数量一致。"""
    sys.path.insert(0, str(SKILL_ROOT))
    results: list[dict[str, object]] = []
    for case in cases:
        suite = unittest.TestSuite(
            unittest.defaultTestLoader.loadTestsFromName(test_id)
            for test_id in case["test_ids"]
        )
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=0).run(suite)
        status = "PASS" if result.wasSuccessful() else "FAIL"
        case_result: dict[str, object] = {
            "id": case["id"],
            "name": case["name"],
            "status": status,
            "testsRun": result.testsRun,
            "testIds": case["test_ids"],
        }
        if status == "FAIL":
            case_result["detail"] = stream.getvalue()[-4000:]
        results.append(case_result)
    passed = sum(result["status"] == "PASS" for result in results)
    failed = len(results) - passed
    return {
        "schemaVersion": "1.0",
        "reportType": "golden-regression",
        "status": "PASS" if failed == 0 else "FAIL",
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "results": results,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行 wohu-amazon-skill-creator Golden Set")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        cases = load_manifest()
        validate_test_sources(cases)
        report = run_cases(cases)
    except RuntimeError as exc:
        if args.format == "json":
            print(json.dumps({
                "status": "FAIL",
                "total": 1,
                "passed": 0,
                "failed": 1,
                "results": [{"id": 1, "status": "FAIL", "detail": str(exc)}],
            }, ensure_ascii=False))
        else:
            print(f"[FAIL] {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False))
    else:
        for result in report["results"]:
            print(f"[{result['status']}] 案例 {result['id']}: {result['name']} ({result['testsRun']} tests)")
            if result.get("detail"):
                print(result["detail"])
        print(f"{report['status']}: Golden Set {report['passed']}/{report['total']} cases passed")
        if report["status"] == "PASS":
            print("OK")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
