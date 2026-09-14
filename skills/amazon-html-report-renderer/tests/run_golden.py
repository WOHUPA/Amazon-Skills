from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
CLI_PATH = SKILL_ROOT / "scripts" / "render_report.py"
CASES_PATH = SKILL_ROOT / "evals" / "golden-cases.json"
DEFAULT_RECEIPTS_PATH = SKILL_ROOT / "evals" / "golden-receipts.jsonl"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_assertion(
    name: str,
    *,
    document: str,
    spec: dict[str, Any],
    renderer_receipt: dict[str, Any],
) -> bool:
    lowered = document.lower()
    checks = {
        "self_contained": not bool(
            re.search(r'<(?:script|link|img)\b[^>]*(?:src|href)=["\']https?://', lowered)
        ),
        "missing_not_zero": "缺失" in document or "MISSING" in document,
        "negative_preserved": "-7.5" in document,
        "zero_preserved": bool(re.search(r"(?:>|\s)0(?:<|\s)", document)),
        "accessible_charts": "<svg" in lowered and "<title" in lowered and "<desc" in lowered,
        "partial_visible": "PARTIAL" in document,
        "limitations_visible": "限制" in document or "limitations" in lowered,
        "null_preserved": "缺失" in document or "MISSING" in document,
        "source_conflict_visible": "冲突" in document or "CONFLICT" in document,
        "quotes_escaped": "The zipper failed after light use." in document,
        "image_embedded": "data:image/png;base64," in document,
        "image_alt": bool(re.search(r"<img\b[^>]*\balt=[\"'][^\"']+[\"']", document)),
        "topic_table_present": "尺寸" in document and "<table" in lowered,
        "demo_visible": document.count("DEMO") >= 2,
        "radar_summary": "<svg" in lowered and "<desc" in lowered,
        "comparison_grid": "匿名工具 A" in document and "匿名工具 B" in document,
        "evidence_labels": "匿名工具 A" in document and "匿名工具 B" in document,
        "checklist_states": all(
            label in document
            for label in ("检查账号健康摘要", "复核缺货风险", "核对异常价格提示", "关闭高风险工单")
        ),
        "single_h1": len(re.findall(r"<h1\b", lowered)) == 1,
        "no_empty_components": "{{" not in document and "{%" not in document,
        "print_styles": "@media print" in lowered,
        "back_to_top_contract": (
            len(re.findall(r'\bid=["\']report-top["\']', document, re.IGNORECASE)) == 1
            and len(re.findall(r'<a\b[^>]*\bclass=["\'][^"\']*\bback-to-top\b[^"\']*["\'][^>]*>', document, re.IGNORECASE)) == 1
            and 'href="#report-top"' in document
            and "IntersectionObserver" in document
            and bool(re.search(r"@media print\{[\s\S]*?\.back-to-top", document, re.IGNORECASE))
        ),
        "blocked_quality_page": "BLOCKED" in document and "数据质量" in document,
        "no_normal_dashboard": "计划覆盖范围" not in document,
        "no_fabricated_values": "<svg" not in lowered and not spec["metrics"],
    }
    if name not in checks:
        return False
    return bool(checks[name]) and bool(renderer_receipt)


def run_case(case: dict[str, Any]) -> dict[str, Any]:
    fixture_path = SKILL_ROOT / case["fixture"]
    fixture_bytes = fixture_path.read_bytes()
    spec = load_json(fixture_path)
    with tempfile.TemporaryDirectory(prefix=f"{case['case_id'].lower()}-") as temp_dir:
        output_path = Path(temp_dir) / f"{case['case_id'].lower()}.html"
        result = subprocess.run(
            [
                sys.executable,
                str(CLI_PATH),
                "--spec",
                str(fixture_path),
                "--output",
                str(output_path),
            ],
            text=True,
            capture_output=True,
            encoding="utf-8",
        )
        parse_errors: list[str] = []
        try:
            stdout_payload = json.loads(result.stdout.strip()) if result.stdout.strip() else {}
        except json.JSONDecodeError as exc:
            stdout_payload = {}
            parse_errors.append(f"stdout JSON invalid: {exc.msg}")
        receipt_path = output_path.with_suffix(".render-receipt.json")
        try:
            renderer_receipt = load_json(receipt_path) if receipt_path.is_file() else {}
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            renderer_receipt = {}
            parse_errors.append(f"renderer receipt invalid: {type(exc).__name__}")
        output_bytes = output_path.read_bytes() if output_path.is_file() else b""
        document = output_bytes.decode("utf-8") if output_bytes else ""
        output_hash = sha256_bytes(output_bytes) if output_bytes else None
        base_passed = (
            result.returncode == 0
            and stdout_payload.get("ok") is True
            and output_path.is_file()
            and receipt_path.is_file()
            and renderer_receipt.get("status") == case["expected_status"]
            and renderer_receipt.get("html_hash") == output_hash
        )
        assertion_results = []
        for index, assertion in enumerate(case["assertions"], start=1):
            assertion_passed = base_passed and evaluate_assertion(
                assertion,
                document=document,
                spec=spec,
                renderer_receipt=renderer_receipt,
            )
            assertion_results.append(
                {
                    "id": f"{case['case_id']}-A{index:02d}",
                    "name": assertion,
                    "status": "PASS" if assertion_passed else "FAIL",
                }
            )
        passed = base_passed and all(
            assertion["status"] == "PASS" for assertion in assertion_results
        )
        return {
            "record_type": "golden_case_receipt",
            "runner": "tests/run_golden.py",
            "case_id": case["case_id"],
            "fixture": case["fixture"],
            "fixture_hash": sha256_bytes(fixture_bytes),
            "output_hash": output_hash,
            "exit_code": int(result.returncode),
            "status": "PASS" if passed else "FAIL",
            "report_status": renderer_receipt.get("status", stdout_payload.get("status", "ERROR")),
            "assertions": assertion_results,
            "renderer_receipt_hash": (
                sha256_bytes(receipt_path.read_bytes()) if receipt_path.is_file() else None
            ),
            "artifact_summary": {
                "html_bytes": len(output_bytes),
                "receipt_bytes": receipt_path.stat().st_size if receipt_path.is_file() else 0,
                "output_retained": False,
            },
            "error": (
                None
                if passed
                else {
                    "parse_errors": parse_errors,
                    "stderr": result.stderr.strip(),
                    "stdout_envelope": stdout_payload,
                }
            ),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="运行六组匿名 Amazon HTML Golden fixtures")
    parser.add_argument("--receipt-log", type=Path, default=DEFAULT_RECEIPTS_PATH)
    args = parser.parse_args()

    cases = load_json(CASES_PATH)
    receipts = [run_case(case) for case in cases]
    planned_case_ids = [case["case_id"] for case in cases]
    executed_case_ids = [receipt["case_id"] for receipt in receipts]
    passed_case_ids = [receipt["case_id"] for receipt in receipts if receipt["status"] == "PASS"]
    unexecuted_case_ids = [case_id for case_id in planned_case_ids if case_id not in executed_case_ids]
    summary = {
        "record_type": "golden_run_summary",
        "runner": "tests/run_golden.py",
        "planned_case_ids": planned_case_ids,
        "executed": len(executed_case_ids),
        "passed": len(passed_case_ids),
        "unexecuted_case_ids": unexecuted_case_ids,
        "status": (
            "PASS"
            if len(passed_case_ids) == len(planned_case_ids) and not unexecuted_case_ids
            else "FAIL"
        ),
    }
    serialized = "".join(
        json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
        for record in [*receipts, summary]
    )
    args.receipt_log.parent.mkdir(parents=True, exist_ok=True)
    staging_path = args.receipt_log.with_suffix(args.receipt_log.suffix + ".tmp")
    staging_path.write_text(serialized, encoding="utf-8", newline="\n")
    staging_path.replace(args.receipt_log)
    stdout_summary = {
        **summary,
        "ok": summary["status"] == "PASS",
        "receipt_log": str(args.receipt_log),
    }
    sys.stdout.write(json.dumps(stdout_summary, ensure_ascii=False, sort_keys=True) + "\n")
    return 0 if stdout_summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
