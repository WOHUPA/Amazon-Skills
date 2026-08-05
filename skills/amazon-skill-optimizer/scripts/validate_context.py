#!/usr/bin/env python3
"""Validate the AmazonContext contract used by amazon-skill-optimizer.

The input may be the context object itself, or an object containing a
``context`` member. Domains can be supplied with ``--domain`` (repeatable or
comma-separated), or with ``selected_domain_packs`` in the input wrapper.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
SCRIPT_NAME = "validate_context"
GLOBAL_REQUIRED = {
    "marketplace",
    "category",
    "business_stage",
    "available_data",
    "read_only_or_write_action",
}
ALL_FIELDS = {
    "marketplace",
    "country",
    "locale",
    "category",
    "product_type",
    "seller_model",
    "fulfillment_model",
    "business_stage",
    "target_customer",
    "price_band",
    "business_objective",
    "constraints",
    "available_data",
    "data_time_window",
    "currency",
    "tax_basis",
    "attribution_window",
    "account_data_or_public_data",
    "read_only_or_write_action",
    "risk_tier",
}

DOMAIN_REQUIRED = {
    "market-research": {"country", "target_customer", "price_band", "business_objective", "account_data_or_public_data"},
    "product-development": {"product_type", "target_customer", "business_objective", "constraints", "account_data_or_public_data"},
    "supply-unit-economics": {"fulfillment_model", "currency", "tax_basis", "constraints", "price_band"},
    "listing-content": {"locale", "product_type", "target_customer", "business_objective", "account_data_or_public_data"},
    "visual-content": {"locale", "product_type", "target_customer", "business_objective", "constraints"},
    "launch-growth": {"seller_model", "fulfillment_model", "business_objective", "data_time_window", "account_data_or_public_data"},
    "amazon-ads": {"currency", "attribution_window", "business_objective", "data_time_window", "account_data_or_public_data"},
    "pricing-promotions": {"price_band", "currency", "tax_basis", "business_objective", "data_time_window"},
    "inventory-fba": {"fulfillment_model", "data_time_window", "currency", "constraints", "account_data_or_public_data"},
    "reviews-voc": {"product_type", "locale", "data_time_window", "account_data_or_public_data", "risk_tier"},
    "brand-compliance": {"country", "locale", "product_type", "constraints", "risk_tier", "account_data_or_public_data"},
    "business-analytics": {"currency", "tax_basis", "attribution_window", "data_time_window", "account_data_or_public_data", "business_objective"},
}

DOMAIN_ALIASES = {
    "market-research": "market-research",
    "selection": "market-research",
    "product-research": "market-research",
    "product-development": "product-development",
    "supply-unit-economics": "supply-unit-economics",
    "supply-chain": "supply-unit-economics",
    "listing-content": "listing-content",
    "listing": "listing-content",
    "visual-content": "visual-content",
    "launch-growth": "launch-growth",
    "amazon-ads": "amazon-ads",
    "ads": "amazon-ads",
    "pricing-promotions": "pricing-promotions",
    "pricing": "pricing-promotions",
    "inventory-fba": "inventory-fba",
    "inventory": "inventory-fba",
    "reviews-voc": "reviews-voc",
    "voc": "reviews-voc",
    "brand-compliance": "brand-compliance",
    "compliance": "brand-compliance",
    "business-analytics": "business-analytics",
    "analytics": "business-analytics",
}

ENUMS = {
    "seller_model": {"private_label", "wholesale", "reseller", "vendor", "handmade", "unknown"},
    "fulfillment_model": {"FBA", "FBM", "SFP", "vendor", "mixed", "unknown"},
    "business_stage": {"research", "development", "pre_launch", "launch", "growth", "mature", "decline", "recovery"},
    "tax_basis": {"tax_inclusive", "tax_exclusive", "not_applicable", "unknown"},
    "account_data_or_public_data": {"account", "public", "mixed", "none"},
    "read_only_or_write_action": {"read_only", "write_proposal", "write_execution"},
    "risk_tier": {"low", "medium", "high", "critical"},
}
AVAILABLE_DATA_VALUES = {
    "skill_files",
    "historical_outputs",
    "evals",
    "first_party_account",
    "official_export",
    "amazon_public",
    "third_party",
    "user_provided",
    "none",
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


def _is_missing(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _parse_iso_date(value: Any) -> date | None:
    if not _non_empty_string(value):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _normalize_domains(raw_domains: list[str]) -> tuple[list[str], list[str]]:
    normalized: list[str] = []
    invalid: list[str] = []
    for raw in raw_domains:
        for value in raw.split(","):
            candidate = value.strip().lower().replace("_", "-")
            if not candidate:
                continue
            domain = DOMAIN_ALIASES.get(candidate)
            if domain is None:
                invalid.append(value.strip())
            elif domain not in normalized:
                normalized.append(domain)
    return normalized, invalid


def _validate_string_list(field: str, value: Any, errors: list[str]) -> None:
    if not isinstance(value, list) or any(not _non_empty_string(item) for item in value):
        errors.append(f"{field} 必须是字符串数组")


def _validate_object_fields(context: dict[str, Any], errors: list[str]) -> None:
    for field in ("category", "product_type", "target_customer"):
        if field in context and not _is_missing(context[field]) and not _non_empty_string(context[field]):
            errors.append(f"{field} 必须是非空字符串")

    marketplace = context.get("marketplace")
    if not _is_missing(marketplace) and (
        not _non_empty_string(marketplace)
        or re.fullmatch(r"[A-Z][A-Z0-9-]{1,9}", marketplace) is None
    ):
        errors.append("marketplace 必须是 2-10 位大写站点代码，例如 US、UK、DE")

    country = context.get("country")
    if not _is_missing(country) and (
        not _non_empty_string(country) or re.fullmatch(r"[A-Z]{2}", country) is None
    ):
        errors.append("country 必须是两位大写国家代码")

    locale = context.get("locale")
    if not _is_missing(locale) and (
        not _non_empty_string(locale)
        or re.fullmatch(r"[a-z]{2,3}(?:-[A-Z]{2})?", locale) is None
    ):
        errors.append("locale 必须是 BCP-47 风格代码，例如 en-US、de-DE、ja-JP")

    currency = context.get("currency")
    if not _is_missing(currency) and (
        not _non_empty_string(currency) or re.fullmatch(r"[A-Z]{3}", currency) is None
    ):
        errors.append("currency 必须是三位大写 ISO-4217 风格代码")

    for field, allowed in ENUMS.items():
        value = context.get(field)
        if not _is_missing(value) and value not in allowed:
            errors.append(f"{field} 非法；允许值：{sorted(allowed)}")

    for field in ("business_objective", "constraints"):
        if field in context and not _is_missing(context[field]):
            _validate_string_list(field, context[field], errors)

    available_data = context.get("available_data")
    if not _is_missing(available_data):
        _validate_string_list("available_data", available_data, errors)
        if isinstance(available_data, list):
            unknown = sorted({value for value in available_data if value not in AVAILABLE_DATA_VALUES})
            if unknown:
                errors.append(f"available_data 含非法值：{unknown}")
            if "none" in available_data and len(available_data) > 1:
                errors.append("available_data 的 none 不得与其他数据源并存")

    price_band = context.get("price_band")
    if not _is_missing(price_band):
        if not isinstance(price_band, dict):
            errors.append("price_band 必须是包含 min、max 的对象")
        else:
            minimum, maximum = price_band.get("min"), price_band.get("max")
            if isinstance(minimum, bool) or not isinstance(minimum, (int, float)):
                errors.append("price_band.min 必须是数字")
            if isinstance(maximum, bool) or not isinstance(maximum, (int, float)):
                errors.append("price_band.max 必须是数字")
            if isinstance(minimum, (int, float)) and not isinstance(minimum, bool) and isinstance(maximum, (int, float)) and not isinstance(maximum, bool):
                if minimum < 0 or maximum < 0 or minimum > maximum:
                    errors.append("price_band 必须满足 0 <= min <= max")

    data_window = context.get("data_time_window")
    if not _is_missing(data_window):
        if not isinstance(data_window, dict):
            errors.append("data_time_window 必须是包含 start、end 的对象")
        else:
            start = _parse_iso_date(data_window.get("start"))
            end = _parse_iso_date(data_window.get("end"))
            if start is None or end is None:
                errors.append("data_time_window.start/end 必须是 ISO 日期")
            elif start > end:
                errors.append("data_time_window.start 不得晚于 end")

    attribution = context.get("attribution_window")
    if not _is_missing(attribution):
        if not isinstance(attribution, dict):
            errors.append("attribution_window 必须是包含 click_days、view_days、source 的对象")
        else:
            for key in ("click_days", "view_days"):
                value = attribution.get(key)
                if type(value) is not int or value < 0:
                    errors.append(f"attribution_window.{key} 必须是非负整数")
            if not _non_empty_string(attribution.get("source")):
                errors.append("attribution_window.source 必须是非空字符串")


def validate(payload: Any, cli_domains: list[str]) -> tuple[dict[str, Any], int]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(payload, dict):
        result = {"schema_version": SCHEMA_VERSION, "script": SCRIPT_NAME, "status": "FAIL", "errors": ["JSON 根节点必须是对象"], "warnings": [], "data": {}}
        return result, 2

    wrapper = payload
    context = payload.get("context", payload)
    if not isinstance(context, dict):
        result = {"schema_version": SCHEMA_VERSION, "script": SCRIPT_NAME, "status": "FAIL", "errors": ["context 必须是对象"], "warnings": [], "data": {}}
        return result, 2

    wrapper_domains = wrapper.get("selected_domain_packs", []) if "context" in wrapper else []
    if isinstance(wrapper_domains, str):
        wrapper_domains = [wrapper_domains]
    if not isinstance(wrapper_domains, list) or any(not isinstance(item, str) for item in wrapper_domains):
        errors.append("selected_domain_packs 必须是字符串数组")
        wrapper_domains = []
    domains, invalid_domains = _normalize_domains(cli_domains or wrapper_domains)
    if invalid_domains:
        errors.append(f"未知 Domain Pack：{invalid_domains}")
    if not domains:
        warnings.append("未选择 Domain Pack；只能执行全域结构校验，领域结论必须标记 UNVERIFIED")

    unknown_fields = sorted(set(context) - ALL_FIELDS)
    if unknown_fields:
        warnings.append(f"发现 Schema 外字段，将忽略：{unknown_fields}")

    missing_global = sorted(field for field in GLOBAL_REQUIRED if _is_missing(context.get(field)))
    missing_by_domain = {
        domain: sorted(field for field in DOMAIN_REQUIRED[domain] if _is_missing(context.get(field)))
        for domain in domains
    }
    missing_by_domain = {domain: fields for domain, fields in missing_by_domain.items() if fields}
    _validate_object_fields(context, errors)

    if context.get("read_only_or_write_action") == "write_execution":
        errors.append("V1 禁止 write_execution；只能使用 read_only 或 write_proposal")

    if "brand-compliance" in domains and context.get("risk_tier") in {"high", "critical"}:
        sources = context.get("available_data") if isinstance(context.get("available_data"), list) else []
        if not {"official_export", "amazon_public"}.intersection(sources):
            errors.append("高/关键风险合规审计缺少适用站点的官方证据，禁止给出结论")

    if len(domains) > 2:
        warnings.append("一次最多加载两个 Domain Pack；已生成顺序批次，禁止同时加载全部领域")
    domain_batches = [domains[index:index + 2] for index in range(0, len(domains), 2)]

    domain_required_union = set().union(*(DOMAIN_REQUIRED[domain] for domain in domains)) if domains else set()
    optional_candidates = ALL_FIELDS - GLOBAL_REQUIRED - domain_required_union
    optional_missing = sorted(field for field in optional_candidates if _is_missing(context.get(field)))
    recommendations: list[dict[str, Any]] = []
    if errors:
        recommendations.append({"action": "BLOCK", "reason": "存在 Schema、权限或高风险证据错误", "errors": list(errors)})
    if missing_global:
        recommendations.append({"action": "BLOCK", "fields": missing_global, "reason": "缺少全域必填字段"})
    for domain, fields in missing_by_domain.items():
        recommendations.append({"action": "ASK", "domain": domain, "fields": fields, "reason": "缺少可由用户补齐的领域必填字段"})
    if optional_missing or not domains:
        recommendations.append({"action": "DEGRADE", "fields": optional_missing, "reason": "只输出条件式结论并显式标注假设与 UNVERIFIED"})

    blocked = bool(errors or missing_global)
    degraded = bool(warnings or missing_by_domain or optional_missing)
    status = "FAIL" if blocked else ("WARN" if degraded else "PASS")
    data = {
        "selected_domain_packs": domains,
        "domain_batches": domain_batches,
        "missing_global": missing_global,
        "missing_by_domain": missing_by_domain,
        "optional_missing": optional_missing,
        "recommendations": recommendations,
        "conflict_precedence": ["marketplace", "category", "business_stage", "general_default"],
        "validated_fields": sorted(set(context).intersection(ALL_FIELDS)),
    }
    return {"schema_version": SCHEMA_VERSION, "script": SCRIPT_NAME, "status": status, "errors": errors, "warnings": warnings, "data": data}, 2 if blocked else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="校验 amazon-skill-optimizer 的 AmazonContext JSON。")
    parser.add_argument("--input", "-i", required=True, help="JSON 文件路径；使用 - 从标准输入读取。")
    parser.add_argument("--domain", action="append", default=[], help="Domain Pack slug；可重复或用逗号分隔。")
    return parser


def main() -> int:
    _configure_stdout()
    args = build_parser().parse_args()
    try:
        payload = _read_json(args.input)
        report, exit_code = validate(payload, args.domain)
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
