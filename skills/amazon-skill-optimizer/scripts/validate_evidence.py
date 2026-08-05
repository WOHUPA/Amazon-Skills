#!/usr/bin/env python3
"""Validate Amazon audit evidence records in JSON or JSONL form."""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
SCRIPT_NAME = "validate_evidence"
SCHEMA_FIELDS = {
    "evidence_id", "claim_id", "claim", "source_type", "source_location",
    "marketplace", "category", "entity_type", "entity_id", "time_range",
    "observed_at", "effective_date", "timezone", "currency", "unit",
    "tax_basis", "attribution_window", "coverage", "freshness",
    "evidence_level", "confidence", "limitations", "conflicting_evidence",
    "status", "supersedes",
}
CORE_REQUIRED = {
    "evidence_id", "claim_id", "claim", "source_type", "source_location",
    "marketplace", "observed_at", "evidence_level", "confidence",
    "limitations", "status",
}
SOURCE_LEVELS = {
    "official_policy": "E1",
    "authorized_first_party": "E1",
    "amazon_public": "E2",
    "trusted_third_party": "E3",
    "historical_case": "E4",
    "expert_experience": "E4",
    "user_provided": "E4",
    "model_inference": "E5",
}
STATUSES = {"observed", "verified", "partial", "unverified", "superseded", "rejected"}
TAX_BASES = {"tax_inclusive", "tax_exclusive", "not_applicable", "unknown"}
FRESHNESS_VALUES = {"fresh", "aging", "stale", "unknown"}
METRIC_TERMS = ("sales", "revenue", "cost", "price", "margin", "rate", "ratio", "ctr", "cvr", "acos", "tacos", "销量", "销售额", "成本", "价格", "利润", "转化率", "点击率", "比率")
MONEY_TERMS = ("revenue", "cost", "price", "margin", "profit", "fee", "sales", "acos", "tacos", "销售额", "成本", "价格", "利润", "费用")
ADS_TERMS = ("advertis", "campaign", "acos", "tacos", "ad spend", "广告", "活动归因", "归因")
CURRENT_TERMS = ("current", "today", "latest", "now", "当前", "今天", "最新", "现行")


def _configure_stdout() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass


def _read_records(path_text: str) -> list[Any]:
    if path_text == "-":
        text = sys.stdin.read().lstrip("\ufeff")
        suffix = ""
    else:
        path = Path(path_text)
        text = path.read_text(encoding="utf-8-sig")
        suffix = path.suffix.lower()
    if not text.strip():
        raise ValueError("输入为空")

    if suffix != ".jsonl":
        try:
            payload = json.loads(text)
            if isinstance(payload, list):
                return payload
            if isinstance(payload, dict) and isinstance(payload.get("evidence"), list):
                return payload["evidence"]
            if isinstance(payload, dict) and isinstance(payload.get("records"), list):
                return payload["records"]
            return [payload]
        except json.JSONDecodeError:
            pass

    records: list[Any] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSONL 第 {line_number} 行无效：{exc.msg}") from exc
    return records


def _missing(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _parse_datetime(value: Any) -> datetime | None:
    if not _string(value):
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        try:
            parsed = datetime.fromisoformat(normalized[:10])
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _validate_range(name: str, value: Any, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{name} 必须是包含 start、end 的对象")
        return
    start, end = _parse_datetime(value.get("start")), _parse_datetime(value.get("end"))
    if start is None or end is None:
        errors.append(f"{name}.start/end 必须是 ISO 日期或时间")
    elif start > end:
        errors.append(f"{name}.start 不得晚于 end")


def _validate_attribution(value: Any, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append("attribution_window 必须是包含 click_days、view_days、source 的对象")
        return
    for field in ("click_days", "view_days"):
        item = value.get(field)
        if type(item) is not int or item < 0:
            errors.append(f"attribution_window.{field} 必须是非负整数")
    if not _string(value.get("source")):
        errors.append("attribution_window.source 必须是非空字符串")


def _computed_freshness(source_type: str, age_days: int) -> str:
    if source_type in {"historical_case", "expert_experience", "user_provided"}:
        return "unknown"
    if source_type == "model_inference":
        return "unknown"
    if source_type == "authorized_first_party":
        if age_days <= 7:
            return "fresh"
        return "aging" if age_days <= 30 else "stale"
    if source_type in {"amazon_public", "trusted_third_party"}:
        if age_days <= 30:
            return "fresh"
        return "aging" if age_days <= 90 else "stale"
    return "fresh" if age_days <= 30 else "stale"


def _validate_record(record: Any, index: int, now: datetime) -> tuple[list[str], list[str], dict[str, Any]]:
    prefix = f"records[{index}]"
    errors: list[str] = []
    warnings: list[str] = []
    summary: dict[str, Any] = {"index": index, "evidence_id": None, "computed_freshness": None}
    if not isinstance(record, dict):
        return [f"{prefix} 必须是对象"], warnings, summary

    summary["evidence_id"] = record.get("evidence_id")
    missing_core = sorted(
        field
        for field in CORE_REQUIRED
        if (field == "limitations" and (field not in record or record.get(field) is None))
        or (field != "limitations" and _missing(record.get(field)))
    )
    if missing_core:
        errors.append(f"{prefix} 缺核心字段：{missing_core}")
    optional_absent = sorted(SCHEMA_FIELDS - set(record))
    if optional_absent:
        warnings.append(f"{prefix} 未显式提供可空字段：{optional_absent}")
    unknown = sorted(set(record) - SCHEMA_FIELDS)
    if unknown:
        warnings.append(f"{prefix} 含 Schema 外字段，将忽略：{unknown}")

    for field in ("evidence_id", "claim_id", "claim", "source_location", "marketplace"):
        if field in record and not _missing(record[field]) and not _string(record[field]):
            errors.append(f"{prefix}.{field} 必须是非空字符串")
    marketplace = record.get("marketplace")
    if _string(marketplace) and re.fullmatch(r"[A-Z][A-Z0-9-]{1,9}", marketplace) is None:
        errors.append(f"{prefix}.marketplace 必须是大写站点代码")

    source_type = record.get("source_type")
    if source_type not in SOURCE_LEVELS:
        errors.append(f"{prefix}.source_type 非法；允许值：{sorted(SOURCE_LEVELS)}")
    level = record.get("evidence_level")
    if level not in {"E1", "E2", "E3", "E4", "E5"}:
        errors.append(f"{prefix}.evidence_level 必须为 E1-E5")
    elif source_type in SOURCE_LEVELS and level != SOURCE_LEVELS[source_type]:
        errors.append(f"{prefix} 的 source_type={source_type} 只能映射为 {SOURCE_LEVELS[source_type]}，不得标为 {level}")

    status = record.get("status")
    if status not in STATUSES:
        errors.append(f"{prefix}.status 非法；允许值：{sorted(STATUSES)}")
    if source_type == "model_inference" and status != "unverified":
        errors.append(f"{prefix} 的模型推断必须标记 status=unverified")

    for field in ("confidence", "coverage"):
        value = record.get(field)
        if field == "coverage" and _missing(value):
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
            errors.append(f"{prefix}.{field} 必须是 0-1 数字")

    limitations = record.get("limitations")
    confidence_value = record.get("confidence")
    if limitations is not None and not (isinstance(limitations, list) and all(_string(item) for item in limitations)):
        errors.append(f"{prefix}.limitations 必须是字符串数组")
    elif isinstance(limitations, list) and not limitations and (
        source_type in {"trusted_third_party", "historical_case", "expert_experience", "user_provided", "model_inference"}
        or record.get("status") in {"partial", "unverified"}
        or isinstance(confidence_value, (int, float)) and not isinstance(confidence_value, bool) and confidence_value < 1
    ):
        errors.append(f"{prefix}.limitations 对不确定、估算或未验证证据不得为空")
    for field in ("conflicting_evidence", "supersedes"):
        value = record.get(field)
        if not _missing(value) and not (isinstance(value, list) and all(_string(item) for item in value)):
            errors.append(f"{prefix}.{field} 必须是 evidence_id 字符串数组")

    observed_at = _parse_datetime(record.get("observed_at"))
    if observed_at is None:
        if not _missing(record.get("observed_at")):
            errors.append(f"{prefix}.observed_at 必须是 ISO 日期或时间")
    else:
        age_days = (now - observed_at).days
        if age_days < -1:
            errors.append(f"{prefix}.observed_at 不得位于未来")
        elif source_type in SOURCE_LEVELS:
            computed = _computed_freshness(source_type, max(age_days, 0))
            summary["computed_freshness"] = computed
            supplied = record.get("freshness")
            if not _missing(supplied) and supplied not in FRESHNESS_VALUES:
                errors.append(f"{prefix}.freshness 非法；允许值：{sorted(FRESHNESS_VALUES)}")
            elif not _missing(supplied) and supplied != computed:
                warnings.append(f"{prefix}.freshness={supplied} 与按 observed_at 计算的 {computed} 不一致")
            if computed in {"aging", "stale"}:
                warnings.append(f"{prefix} 证据时效为 {computed}；不得证明当前状态")
            if source_type == "official_policy":
                warnings.append(f"{prefix} 涉及官方政策；执行前无论时间戳均须核验适用站点的当前官方来源")

    if not _missing(record.get("effective_date")) and _parse_datetime(record.get("effective_date")) is None:
        errors.append(f"{prefix}.effective_date 必须是 ISO 日期")
    if source_type == "official_policy" and _missing(record.get("effective_date")):
        errors.append(f"{prefix} 的 official_policy 必须提供 effective_date")
    timezone_value = record.get("timezone")
    if not _missing(timezone_value) and not _string(timezone_value):
        errors.append(f"{prefix}.timezone 必须是时区字符串")
    currency_value = record.get("currency")
    if not _missing(currency_value) and (not _string(currency_value) or re.fullmatch(r"[A-Z]{3}", currency_value) is None):
        errors.append(f"{prefix}.currency 必须是三位大写币种代码")
    unit_value = record.get("unit")
    if not _missing(unit_value) and not _string(unit_value):
        errors.append(f"{prefix}.unit 必须是非空字符串")
    tax_value = record.get("tax_basis")
    if not _missing(tax_value) and tax_value not in TAX_BASES:
        errors.append(f"{prefix}.tax_basis 非法；允许值：{sorted(TAX_BASES)}")

    entity_type, entity_id = record.get("entity_type"), record.get("entity_id")
    if bool(_missing(entity_type)) != bool(_missing(entity_id)):
        errors.append(f"{prefix}.entity_type 与 entity_id 必须成对提供")
    if not _missing(entity_type) and not _string(entity_type):
        errors.append(f"{prefix}.entity_type 必须是非空字符串")
    if not _missing(entity_id) and not _string(entity_id):
        errors.append(f"{prefix}.entity_id 必须是非空字符串")

    claim = str(record.get("claim", "")).lower()
    is_metric = bool(record.get("unit") or record.get("currency") or any(term in claim for term in METRIC_TERMS))
    is_money = any(term in claim for term in MONEY_TERMS)
    is_ads = bool(record.get("attribution_window") or any(term in claim for term in ADS_TERMS))
    if is_metric:
        if _missing(record.get("time_range")):
            errors.append(f"{prefix} 的指标主张必须提供 time_range")
        else:
            _validate_range(f"{prefix}.time_range", record["time_range"], errors)
        for field in ("unit", "coverage"):
            if _missing(record.get(field)):
                errors.append(f"{prefix} 的指标主张必须提供 {field}")
    elif not _missing(record.get("time_range")):
        _validate_range(f"{prefix}.time_range", record["time_range"], errors)

    if is_money:
        for field in ("currency", "unit", "tax_basis"):
            if _missing(record.get(field)):
                errors.append(f"{prefix} 的金额主张必须提供 {field}")
    if is_ads:
        for field in ("entity_type", "entity_id", "time_range", "timezone", "currency"):
            if _missing(record.get(field)):
                errors.append(f"{prefix} 的广告主张必须提供 {field}")
        if _missing(record.get("attribution_window")):
            errors.append(f"{prefix} 的广告/归因主张必须提供 attribution_window")
        else:
            attribution_errors: list[str] = []
            _validate_attribution(record["attribution_window"], attribution_errors)
            errors.extend(f"{prefix}.{message}" for message in attribution_errors)

    if any(term in claim for term in CURRENT_TERMS) and source_type in {"historical_case", "expert_experience", "model_inference"}:
        errors.append(f"{prefix} 使用 {source_type} 证明当前事实，必须改用当前官方或授权第一方证据")

    return errors, warnings, summary


def validate(records: list[Any], now: datetime) -> tuple[dict[str, Any], int]:
    errors: list[str] = []
    warnings: list[str] = []
    summaries: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, record in enumerate(records):
        record_errors, record_warnings, summary = _validate_record(record, index, now)
        errors.extend(record_errors)
        warnings.extend(record_warnings)
        evidence_id = summary.get("evidence_id")
        if isinstance(evidence_id, str) and evidence_id:
            if evidence_id in seen_ids:
                errors.append(f"records[{index}].evidence_id 重复：{evidence_id}")
            seen_ids.add(evidence_id)
        summaries.append(summary)
    if not records:
        errors.append("至少需要一条 evidence 记录")
    status = "FAIL" if errors else ("WARN" if warnings else "PASS")
    data = {"record_count": len(records), "valid_count": len(records) if not errors else sum(1 for summary in summaries if not any(message.startswith(f"records[{summary['index']}]") for message in errors)), "records": summaries}
    return {"schema_version": SCHEMA_VERSION, "script": SCRIPT_NAME, "status": status, "errors": errors, "warnings": warnings, "data": data}, 2 if errors else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="校验 Amazon 审计 Evidence Schema（JSON 或 JSONL）。")
    parser.add_argument("--input", "-i", required=True, help="JSON/JSONL 文件路径；使用 - 从标准输入读取。")
    parser.add_argument("--now", help="用于时效复算的 ISO 时间；默认当前 UTC。")
    return parser


def main() -> int:
    _configure_stdout()
    args = build_parser().parse_args()
    try:
        now = _parse_datetime(args.now) if args.now else datetime.now(timezone.utc)
        if now is None:
            raise ValueError("--now 必须是 ISO 日期或时间")
        report, exit_code = validate(_read_records(args.input), now)
    except (OSError, UnicodeError, ValueError) as exc:
        report = {"schema_version": SCHEMA_VERSION, "script": SCRIPT_NAME, "status": "FAIL", "errors": [f"无法校验输入：{exc}"], "warnings": [], "data": {}}
        exit_code = 2
    except Exception as exc:  # pragma: no cover - defensive CLI boundary
        report = {"schema_version": SCHEMA_VERSION, "script": SCRIPT_NAME, "status": "FAIL", "errors": [f"内部错误：{type(exc).__name__}: {exc}"], "warnings": [], "data": {}}
        exit_code = 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
