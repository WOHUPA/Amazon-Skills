#!/usr/bin/env python3
"""Recompute Amazon business formulas and validate their measurement basis."""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
SCRIPT_NAME = "validate_calculations"
TAX_BASES = {"tax_inclusive", "tax_exclusive", "not_applicable", "unknown"}

FORMULAS: dict[str, tuple[list[str], str]] = {
    "landed_cost": (["purchase", "packaging", "inbound_freight", "duty", "insurance", "prep", "other_landed"], "money"),
    "contribution_margin": (["net_revenue", "landed_cost", "amazon_fees", "fulfillment", "storage", "return_loss", "other_variable", "ad_spend"], "money"),
    "acos": (["ad_spend", "attributed_ad_sales"], "money"),
    "break_even_acos": (["selling_price", "non_ad_variable_cost"], "money"),
    "tacos": (["ad_spend", "total_sales"], "money"),
    "ctr": (["clicks", "impressions"], "count"),
    "cvr": (["orders", "clicks"], "count"),
    "inventory_turnover": (["cogs", "avg_inventory_value"], "money"),
}
ALIASES = {
    "break-even-acos": "break_even_acos",
    "break_even_acos": "break_even_acos",
    "landed-cost": "landed_cost",
    "contribution-margin": "contribution_margin",
    "inventory-turnover": "inventory_turnover",
}


def _configure_stdout() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass


def _read_json(path_text: str) -> Any:
    if path_text == "-":
        return json.loads(sys.stdin.read().lstrip("\ufeff"))
    with Path(path_text).open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def _records(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("calculations"), list):
        return payload["calculations"]
    return [payload]


def _number(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _normal_type(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    candidate = value.strip().lower().replace(" ", "_")
    return ALIASES.get(candidate, candidate.replace("-", "_"))


def _validate_time_range(record: dict[str, Any], errors: list[str], prefix: str) -> None:
    value = record.get("time_range")
    if not isinstance(value, dict) or not _non_empty_string(value.get("start")) or not _non_empty_string(value.get("end")):
        errors.append(f"{prefix}.time_range 必须提供非空 start、end；不得混用不同时间粒度")
        return
    try:
        start = datetime.fromisoformat(value["start"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(value["end"].replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{prefix}.time_range.start/end 必须是 ISO 日期或时间")
        return
    if start > end:
        errors.append(f"{prefix}.time_range.start 不得晚于 end")


def _validate_attribution(record: dict[str, Any], errors: list[str], prefix: str) -> None:
    value = record.get("attribution_window")
    if not isinstance(value, dict):
        errors.append(f"{prefix}.attribution_window 必须是包含 click_days、view_days、source 的对象")
        return
    for field in ("click_days", "view_days"):
        item = value.get(field)
        if type(item) is not int or item < 0:
            errors.append(f"{prefix}.attribution_window.{field} 必须是非负整数")
    if not _non_empty_string(value.get("source")):
        errors.append(f"{prefix}.attribution_window.source 必须是非空字符串")


def _operand(
    name: str,
    raw: Any,
    defaults: dict[str, Any],
    basis: str,
    errors: list[str],
    prefix: str,
) -> tuple[float | None, dict[str, Any]]:
    if raw is None:
        errors.append(f"{prefix}.inputs 缺少 {name}；缺失值不得当作 0")
        return None, {}
    if isinstance(raw, dict):
        value = raw.get("value")
        metadata = {key: raw.get(key, defaults.get(key)) for key in ("currency", "unit", "tax_basis")}
    else:
        value = raw
        metadata = {key: defaults.get(key) for key in ("currency", "unit", "tax_basis")}
    if not _number(value):
        errors.append(f"{prefix}.inputs.{name}.value 必须是有限数字，不能为 null 或 bool")
        return None, metadata
    if value < 0:
        errors.append(f"{prefix}.inputs.{name}.value 不得为负数")
    required_metadata = ("currency", "unit", "tax_basis") if basis == "money" else ("unit",)
    for field in required_metadata:
        if not _non_empty_string(metadata.get(field)):
            errors.append(f"{prefix}.inputs.{name} 缺少 {field}；禁止无口径精确计算")
    if basis == "money":
        currency = metadata.get("currency")
        if _non_empty_string(currency) and re.fullmatch(r"[A-Z]{3}", currency) is None:
            errors.append(f"{prefix}.inputs.{name}.currency 必须是三位大写币种代码")
        tax_basis = metadata.get("tax_basis")
        if _non_empty_string(tax_basis) and tax_basis not in TAX_BASES:
            errors.append(f"{prefix}.inputs.{name}.tax_basis 非法；允许值：{sorted(TAX_BASES)}")
    return float(value), metadata


def _consistent_metadata(
    metadata: dict[str, dict[str, Any]],
    basis: str,
    errors: list[str],
    prefix: str,
) -> dict[str, str | None]:
    fields = ("currency", "unit", "tax_basis") if basis == "money" else ("unit",)
    resolved: dict[str, str | None] = {"currency": None, "unit": None, "tax_basis": None}
    for field in fields:
        values = {str(item.get(field)) for item in metadata.values() if _non_empty_string(item.get(field))}
        if len(values) > 1:
            errors.append(f"{prefix} 的 {field} 不一致：{sorted(values)}；禁止混算")
        elif values:
            resolved[field] = next(iter(values))
    return resolved


def _divide(numerator: float, denominator: float, name: str, errors: list[str], prefix: str) -> float | None:
    if denominator == 0:
        errors.append(f"{prefix}.{name} 分母为 0，禁止输出伪精确结果")
        return None
    return numerator / denominator


def _compute(calc_type: str, values: dict[str, float], errors: list[str], prefix: str) -> dict[str, float]:
    if calc_type == "landed_cost":
        return {"landed_cost": sum(values.values())}
    if calc_type == "contribution_margin":
        margin = values["net_revenue"] - sum(value for key, value in values.items() if key != "net_revenue")
        ratio = _divide(margin, values["net_revenue"], "contribution_margin_ratio", errors, prefix)
        result = {"contribution_margin": margin}
        if ratio is not None:
            result["contribution_margin_ratio"] = ratio
        return result
    if calc_type == "acos":
        value = _divide(values["ad_spend"], values["attributed_ad_sales"], "acos", errors, prefix)
        return {} if value is None else {"acos": value}
    if calc_type == "break_even_acos":
        value = _divide(values["selling_price"] - values["non_ad_variable_cost"], values["selling_price"], "break_even_acos", errors, prefix)
        return {} if value is None else {"break_even_acos": value}
    if calc_type == "tacos":
        value = _divide(values["ad_spend"], values["total_sales"], "tacos", errors, prefix)
        return {} if value is None else {"tacos": value}
    if calc_type == "ctr":
        value = _divide(values["clicks"], values["impressions"], "ctr", errors, prefix)
        return {} if value is None else {"ctr": value}
    if calc_type == "cvr":
        value = _divide(values["orders"], values["clicks"], "cvr", errors, prefix)
        return {} if value is None else {"cvr": value}
    value = _divide(values["cogs"], values["avg_inventory_value"], "inventory_turnover", errors, prefix)
    return {} if value is None else {"inventory_turnover": value}


def _expected_values(record: dict[str, Any], result: dict[str, float], errors: list[str], prefix: str) -> None:
    expected = record.get("expected")
    if expected is None:
        return
    if _number(expected):
        if not result:
            return
        expected_map = {next(iter(result)): float(expected)}
    elif isinstance(expected, dict):
        if "value" in expected and _number(expected.get("value")) and result:
            expected_map = {next(iter(result)): float(expected["value"])}
        else:
            expected_map = {key: float(value) for key, value in expected.items() if _number(value)}
            if not expected_map:
                errors.append(f"{prefix}.expected 对象必须包含数值结果")
                return
    else:
        errors.append(f"{prefix}.expected 必须是数字或结果名到数字的对象")
        return
    tolerance = record.get("tolerance", 1e-9)
    if not _number(tolerance) or tolerance < 0:
        errors.append(f"{prefix}.tolerance 必须是非负有限数字")
        return
    for key, expected_value in expected_map.items():
        if key not in result:
            errors.append(f"{prefix}.expected 含未知或未计算结果：{key}")
            continue
        allowed = max(float(tolerance), abs(expected_value) * float(tolerance))
        if not math.isclose(result[key], expected_value, rel_tol=0.0, abs_tol=allowed):
            errors.append(f"{prefix}.{key} 复算不一致：expected={expected_value}, computed={result[key]}")


def _validate_record(record: Any, index: int) -> tuple[list[str], list[str], dict[str, Any]]:
    prefix = f"calculations[{index}]"
    errors: list[str] = []
    warnings: list[str] = []
    summary: dict[str, Any] = {"index": index, "id": None, "type": None, "status": "FAIL", "computed": {}}
    if not isinstance(record, dict):
        return [f"{prefix} 必须是对象"], warnings, summary
    summary["id"] = record.get("id", f"calculation-{index + 1}")
    calc_type = _normal_type(record.get("type", record.get("calculation")))
    summary["type"] = calc_type or None
    if calc_type not in FORMULAS:
        errors.append(f"{prefix}.type 非法；允许值：{sorted(FORMULAS)}")
        return errors, warnings, summary
    inputs = record.get("inputs")
    if not isinstance(inputs, dict):
        errors.append(f"{prefix}.inputs 必须是对象")
        return errors, warnings, summary
    inputs = dict(inputs)
    if calc_type == "acos" and "attributed_ad_sales" not in inputs and "ad_sales" in inputs:
        inputs["attributed_ad_sales"] = inputs.pop("ad_sales")
        warnings.append(f"{prefix}.inputs.ad_sales 已按兼容别名读取；后续请使用 attributed_ad_sales 明确归因口径")
    if record.get("assume_missing_zero") is True:
        errors.append(f"{prefix}.assume_missing_zero=true 被禁止；缺失值不得当作 0")

    required, basis = FORMULAS[calc_type]
    defaults = {key: record.get(key) for key in ("currency", "unit", "tax_basis")}
    values: dict[str, float] = {}
    metadata: dict[str, dict[str, Any]] = {}
    for name in required:
        value, item_metadata = _operand(name, inputs.get(name), defaults, basis, errors, prefix)
        if value is not None:
            values[name] = value
        metadata[name] = item_metadata
    unknown_inputs = sorted(set(inputs) - set(required))
    if unknown_inputs:
        warnings.append(f"{prefix}.inputs 含当前公式未使用字段：{unknown_inputs}")
    basis_metadata = _consistent_metadata(metadata, basis, errors, prefix)

    if calc_type in {"acos", "tacos", "ctr", "cvr", "inventory_turnover"} or (calc_type == "contribution_margin" and values.get("ad_spend", 0) > 0):
        _validate_time_range(record, errors, prefix)
    if calc_type in {"acos", "tacos", "cvr"} or (calc_type == "contribution_margin" and values.get("ad_spend", 0) > 0):
        _validate_attribution(record, errors, prefix)

    computed = _compute(calc_type, values, errors, prefix) if len(values) == len(required) else {}
    _expected_values(record, computed, errors, prefix)
    summary.update({"status": "FAIL" if errors else "PASS", "computed": computed, "basis": basis_metadata})
    return errors, warnings, summary


def validate(payload: Any) -> tuple[dict[str, Any], int]:
    records = _records(payload)
    errors: list[str] = []
    warnings: list[str] = []
    results: list[dict[str, Any]] = []
    if not records or records == [None]:
        errors.append("至少需要一个 calculation")
    for index, record in enumerate(records):
        item_errors, item_warnings, result = _validate_record(record, index)
        errors.extend(item_errors)
        warnings.extend(item_warnings)
        results.append(result)
    status = "FAIL" if errors else ("WARN" if warnings else "PASS")
    data = {"calculation_count": len(results), "passed": sum(item["status"] == "PASS" for item in results), "failed": sum(item["status"] == "FAIL" for item in results), "results": results}
    return {"schema_version": SCHEMA_VERSION, "script": SCRIPT_NAME, "status": status, "errors": errors, "warnings": warnings, "data": data}, 2 if errors else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="复算 Amazon 常用公式，并校验币种、单位、税基、时间与归因口径。")
    parser.add_argument("--input", "-i", required=True, help="JSON 文件路径；使用 - 从标准输入读取。")
    return parser


def main() -> int:
    _configure_stdout()
    args = build_parser().parse_args()
    try:
        report, exit_code = validate(_read_json(args.input))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        report = {"schema_version": SCHEMA_VERSION, "script": SCRIPT_NAME, "status": "FAIL", "errors": [f"无法读取输入：{exc}"], "warnings": [], "data": {}}
        exit_code = 2
    except Exception as exc:  # pragma: no cover - defensive CLI boundary
        report = {"schema_version": SCHEMA_VERSION, "script": SCRIPT_NAME, "status": "FAIL", "errors": [f"内部错误：{type(exc).__name__}: {exc}"], "warnings": [], "data": {}}
        exit_code = 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
