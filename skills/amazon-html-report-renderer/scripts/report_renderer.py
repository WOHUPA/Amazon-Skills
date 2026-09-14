"""Validation, rendering, and atomic delivery for amazon-html-report/v1."""

from __future__ import annotations

import base64
import binascii
import copy
import hashlib
import html
import json
import math
import os
import re
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


PROTOCOL = "amazon-html-report/v1"
RECEIPT_PROTOCOL = "amazon-html-report-render-receipt/v1"
TEMPLATE_VERSION = "1.0.5"
PRIORITY_TABLE_COLUMN_COUNT = 4
COMPACT_COLUMN_MAX_UNITS = 10.0
MIN_ADAPTIVE_COLUMN_WIDTH_EM = 16
MAX_ADAPTIVE_COLUMN_WIDTH_EM = 48
ADAPTIVE_COLUMN_WIDTH_STEP_EM = 4
ORDINAL_CELL_MAX_UNITS = 6.0
ORDINAL_COLUMN_TOKENS = {"序号", "编号", "排名", "排行", "名次", "rank", "ranking", "no", "number"}
MAX_SPEC_BYTES = 25 * 1024 * 1024
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_TOTAL_IMAGE_BYTES = 20 * 1024 * 1024

FAMILIES = {"auto", "performance", "insight", "operations", "knowledge"}
THEMES = {"system", "light", "dark"}
REPORT_STATUSES = {"COMPLETE", "PARTIAL", "BLOCKED"}
DATA_MODES = {"REAL", "DEMO"}
REPORT_EDITIONS = {"BASIC", "ENHANCED_PARTIAL", "ENHANCED_FULL"}
EVIDENCE_STRENGTHS = {"strong", "medium", "weak", "conflict", "none"}
DATA_QUALITY_GRADES = {"A", "B", "C", "D"}
REDACTION_STATUSES = {"REDACTED", "PUBLIC_ONLY", "NOT_APPLICABLE"}
VALUE_STATUSES = {
    "OBSERVED",
    "DERIVED",
    "MISSING",
    "CONFLICT",
    "NO_ROW",
    "NO_ACCESS",
    "COLLECTION_FAILURE",
    "NOT_APPLICABLE",
    "NO_BASELINE",
}
SOURCE_TYPES = {
    "official_policy",
    "authorized_first_party",
    "amazon_public",
    "trusted_third_party",
    "historical_case",
    "expert_experience",
    "user_provided",
    "model_inference",
}
SOURCE_ROLES = {"PRIMARY", "VERIFICATION", "FALLBACK", "MANUAL"}
SOURCE_STATUSES = {"AVAILABLE", "PARTIAL", "UNAVAILABLE", "CONFLICT", "NOT_APPLICABLE"}
SOURCE_TIERS = {"S0", "S1", "S2", "S3", "S4", "S5"}
BEHAVIOR_TIERS = {"STATIC", "UNIT", "INTEGRATION", "LIVE", "UNVERIFIED"}
FIELD_LEVELS = {
    "basic_required",
    "enhancement_global_required",
    "module_required",
    "full_required",
    "display_optional",
}
METRIC_FORMATS = {
    "number",
    "integer",
    "currency",
    "percent",
    "signed_percent",
    "ratio",
    "duration",
    "text",
}
COLUMN_TYPES = {"string", "number", "integer", "boolean", "date", "datetime"}
DATASET_KINDS = {
    "tabular",
    "distribution",
    "series",
    "radar",
    "quotes",
    "keywords",
    "swot",
    "images",
    "image_compare",
    "checklist",
}
LIMITATION_SEVERITIES = {"INFO", "WARNING", "ERROR", "BLOCKER"}
COMPONENT_TYPES = {
    "kpi_cards",
    "distribution",
    "line_chart",
    "data_table",
    "radar_comparison",
    "quote_cards",
    "keyword_topics",
    "summary_insights",
    "swot_grid",
    "evidence_image_grid",
    "evidence_compare",
    "narrative",
    "checklist",
}

IDENTIFIER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,127}$")
LOCALE_RE = re.compile(r"^[a-z]{2,3}(?:-[A-Z][A-Za-z0-9]{1,7}){0,2}$")
CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d ().-]{8,}\d)(?!\w)")
AWS_KEY_RE = re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")
CREDENTIAL_RE = re.compile(
    r"(?i)\b(?:api[-_ ]?key|client[-_ ]?secret|access[-_ ]?token|refresh[-_ ]?token|"
    r"password|passwd|authorization|bearer|cookie)\b\s*[:=]\s*[^\s,;]{4,}"
)
SIGNED_URL_RE = re.compile(
    r"(?i)https?://[^\s]+[?&](?:x-amz-signature|signature|awsaccesskeyid|access_token|token|sig)="
)
PRIVATE_ID_RE = re.compile(
    r"(?i)(?:store|seller|merchant|account|campaign|ad[ _-]?group|profile)[ _-]?"
    r"(?:id|identifier)\s*[:：=#]\s*[A-Za-z0-9_-]{4,}"
)
RAW_FIELD_NAMES = {
    "html",
    "raw_html",
    "svg",
    "raw_svg",
    "javascript",
    "raw_javascript",
    "script",
    "markdown",
    "raw_markdown",
}


class RenderError(Exception):
    """A safe validation or delivery failure intended for machine output."""

    def __init__(self, code: str, message: str, path: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path


def fail(code: str, message: str, path: str) -> None:
    raise RenderError(code, message, path)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def esc(value: Any) -> str:
    """Escape every upstream string before it reaches HTML or SVG markup."""

    return html.escape("" if value is None else str(value), quote=True)


def require_dict(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail("SCHEMA_TYPE_ERROR", "expected object", path)
    return value


def require_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        fail("SCHEMA_TYPE_ERROR", "expected array", path)
    return value


def require_string(value: Any, path: str, *, allow_empty: bool = False, max_length: int = 2000) -> str:
    if not isinstance(value, str):
        fail("SCHEMA_TYPE_ERROR", "expected string", path)
    if not allow_empty and not value.strip():
        fail("SCHEMA_VALUE_ERROR", "string must not be empty", path)
    if len(value) > max_length:
        fail("SCHEMA_LIMIT_ERROR", f"string exceeds {max_length} characters", path)
    return value


def require_bool(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        fail("SCHEMA_TYPE_ERROR", "expected boolean", path)
    return value


def require_number(value: Any, path: str, *, nullable: bool = False) -> float | int | None:
    if value is None and nullable:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        fail("SCHEMA_TYPE_ERROR", "expected finite number", path)
    if not math.isfinite(float(value)):
        fail("SCHEMA_VALUE_ERROR", "number must be finite", path)
    return value


def require_enum(value: Any, allowed: set[str], path: str) -> str:
    text = require_string(value, path, max_length=80)
    if text not in allowed:
        fail("SCHEMA_ENUM_ERROR", f"unsupported value: {text}", path)
    return text


def require_identifier(value: Any, path: str) -> str:
    text = require_string(value, path, max_length=128)
    if not IDENTIFIER_RE.fullmatch(text):
        fail("SCHEMA_IDENTIFIER_ERROR", "invalid identifier", path)
    return text


def exact_keys(
    obj: dict[str, Any],
    required: set[str],
    optional: set[str],
    path: str,
) -> None:
    missing = sorted(required - obj.keys())
    if missing:
        fail("SCHEMA_REQUIRED_ERROR", f"missing fields: {', '.join(missing)}", path)
    unknown = sorted(obj.keys() - required - optional)
    if unknown:
        raw = next((key for key in unknown if key.lower() in RAW_FIELD_NAMES), None)
        code = "RAW_CONTENT_REJECTED" if raw else "SCHEMA_UNKNOWN_FIELD"
        fail(code, f"unknown field: {unknown[0]}", f"{path}.{unknown[0]}")


def validate_string_list(value: Any, path: str, *, max_items: int = 200, max_length: int = 2000) -> list[str]:
    items = require_list(value, path)
    if len(items) > max_items:
        fail("SCHEMA_LIMIT_ERROR", f"array exceeds {max_items} items", path)
    result: list[str] = []
    for index, item in enumerate(items):
        result.append(require_string(item, f"{path}[{index}]", max_length=max_length))
    return result


def validate_source_refs(value: Any, path: str, *, required: bool = True) -> list[str]:
    refs = validate_string_list(value, path, max_items=100, max_length=128)
    for index, ref in enumerate(refs):
        require_identifier(ref, f"{path}[{index}]")
    if required and not refs:
        fail("SOURCE_REF_REQUIRED", "at least one source reference is required", path)
    if len(refs) != len(set(refs)):
        fail("SCHEMA_DUPLICATE_ERROR", "source references must be unique", path)
    return refs


def scan_sensitive_strings(value: Any, path: str = "$") -> None:
    """Reject secrets and direct private identities, while leaving markup to escaping."""

    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in RAW_FIELD_NAMES:
                fail("RAW_CONTENT_REJECTED", f"raw content field is forbidden: {key}", f"{path}.{key}")
            scan_sensitive_strings(child, f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            scan_sensitive_strings(child, f"{path}[{index}]")
        return
    if not isinstance(value, str) or value.startswith("data:image/"):
        return
    if AWS_KEY_RE.search(value) or CREDENTIAL_RE.search(value):
        fail("CREDENTIAL_DETECTED", "credential-like content is forbidden", path)
    if SIGNED_URL_RE.search(value):
        fail("SIGNED_URL_DETECTED", "signed URL is forbidden", path)
    if EMAIL_RE.search(value):
        fail("PII_DETECTED", "email address is forbidden", path)
    if PRIVATE_ID_RE.search(value):
        fail("PRIVATE_IDENTIFIER_DETECTED", "unredacted private identifier is forbidden", path)
    for match in PHONE_RE.finditer(value):
        digits = re.sub(r"\D", "", match.group(0))
        candidate = match.group(0).strip()
        is_iso_date = bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[T ][0-9:Z+.-]+)?", candidate))
        if 10 <= len(digits) <= 15 and not is_iso_date:
            fail("PII_DETECTED", "phone-like content is forbidden", path)


def validate_period(value: Any, path: str) -> None:
    period = require_dict(value, path)
    exact_keys(period, {"label"}, {"start", "end", "data_as_of"}, path)
    require_string(period["label"], f"{path}.label", max_length=160)
    for key in ("start", "end", "data_as_of"):
        if key in period:
            require_string(period[key], f"{path}.{key}", max_length=64)


def validate_report(value: Any) -> None:
    path = "$.report"
    report = require_dict(value, path)
    exact_keys(
        report,
        {
            "report_id",
            "report_type",
            "title",
            "locale",
            "marketplace",
            "period",
            "timezone",
            "currency",
            "report_version",
            "data_mode",
            "status",
            "report_edition",
            "report_edition_reason",
            "data_quality",
            "evidence_strength",
            "privacy",
        },
        set(),
        path,
    )
    require_identifier(report["report_id"], f"{path}.report_id")
    require_string(report["report_type"], f"{path}.report_type", max_length=100)
    require_string(report["title"], f"{path}.title", max_length=240)
    locale = require_string(report["locale"], f"{path}.locale", max_length=32)
    if not LOCALE_RE.fullmatch(locale):
        fail("SCHEMA_VALUE_ERROR", "invalid locale", f"{path}.locale")
    require_string(report["marketplace"], f"{path}.marketplace", max_length=80)
    validate_period(report["period"], f"{path}.period")
    require_string(report["timezone"], f"{path}.timezone", max_length=80)
    currency = require_string(report["currency"], f"{path}.currency", max_length=3)
    if not CURRENCY_RE.fullmatch(currency):
        fail("SCHEMA_VALUE_ERROR", "currency must be an ISO-style three-letter code", f"{path}.currency")
    require_string(report["report_version"], f"{path}.report_version", max_length=40)
    require_enum(report["data_mode"], DATA_MODES, f"{path}.data_mode")
    require_enum(report["status"], REPORT_STATUSES, f"{path}.status")
    require_enum(report["report_edition"], REPORT_EDITIONS, f"{path}.report_edition")
    require_string(report["report_edition_reason"], f"{path}.report_edition_reason", max_length=1000)
    require_enum(report["data_quality"], DATA_QUALITY_GRADES, f"{path}.data_quality")
    require_enum(report["evidence_strength"], EVIDENCE_STRENGTHS, f"{path}.evidence_strength")

    privacy_path = f"{path}.privacy"
    privacy = require_dict(report["privacy"], privacy_path)
    exact_keys(privacy, {"redaction_status", "contains_private_identifiers"}, {"notes"}, privacy_path)
    require_enum(privacy["redaction_status"], REDACTION_STATUSES, f"{privacy_path}.redaction_status")
    contains_private = require_bool(
        privacy["contains_private_identifiers"], f"{privacy_path}.contains_private_identifiers"
    )
    if contains_private:
        fail("UNREDACTED_PRIVATE_DATA", "private identifiers must be redacted upstream", privacy_path)
    if "notes" in privacy:
        require_string(privacy["notes"], f"{privacy_path}.notes", allow_empty=True, max_length=1000)


def validate_sources(value: Any) -> set[str]:
    sources = require_list(value, "$.sources")
    if not sources:
        fail("SOURCE_REQUIRED", "at least one source is required", "$.sources")
    if len(sources) > 500:
        fail("SCHEMA_LIMIT_ERROR", "sources exceed 500 items", "$.sources")
    source_ids: set[str] = set()
    for index, raw in enumerate(sources):
        path = f"$.sources[{index}]"
        source = require_dict(raw, path)
        exact_keys(
            source,
            {
                "source_id",
                "name",
                "source_type",
                "provider_family",
                "role",
                "status",
                "source_tier",
                "data_quality_grade",
                "behavior_evidence_tier",
                "observed_at",
            },
            {"data_as_of", "scope", "limitations"},
            path,
        )
        source_id = require_identifier(source["source_id"], f"{path}.source_id")
        if source_id in source_ids:
            fail("SCHEMA_DUPLICATE_ERROR", "duplicate source_id", f"{path}.source_id")
        source_ids.add(source_id)
        require_string(source["name"], f"{path}.name", max_length=240)
        require_enum(source["source_type"], SOURCE_TYPES, f"{path}.source_type")
        require_string(source["provider_family"], f"{path}.provider_family", max_length=100)
        require_enum(source["role"], SOURCE_ROLES, f"{path}.role")
        require_enum(source["status"], SOURCE_STATUSES, f"{path}.status")
        require_enum(source["source_tier"], SOURCE_TIERS, f"{path}.source_tier")
        require_enum(source["data_quality_grade"], DATA_QUALITY_GRADES, f"{path}.data_quality_grade")
        require_enum(source["behavior_evidence_tier"], BEHAVIOR_TIERS, f"{path}.behavior_evidence_tier")
        require_string(source["observed_at"], f"{path}.observed_at", max_length=64)
        if "data_as_of" in source:
            require_string(source["data_as_of"], f"{path}.data_as_of", max_length=64)
        if "scope" in source:
            require_string(source["scope"], f"{path}.scope", max_length=1000)
        if "limitations" in source:
            validate_string_list(source["limitations"], f"{path}.limitations", max_items=50, max_length=500)
    return source_ids


def ensure_known_refs(refs: Iterable[str], source_ids: set[str], path: str) -> None:
    unknown = sorted(set(refs) - source_ids)
    if unknown:
        fail("UNKNOWN_SOURCE_REF", f"unknown source reference: {unknown[0]}", path)


def validate_metrics(value: Any, source_ids: set[str]) -> set[str]:
    metrics = require_list(value, "$.metrics")
    if len(metrics) > 2000:
        fail("SCHEMA_LIMIT_ERROR", "metrics exceed 2000 items", "$.metrics")
    metric_ids: set[str] = set()
    derived_inputs: list[tuple[str, list[str], str]] = []
    for index, raw in enumerate(metrics):
        path = f"$.metrics[{index}]"
        metric = require_dict(raw, path)
        exact_keys(
            metric,
            {"metric_id", "label", "value", "value_status", "unit", "source_refs", "field_level"},
            {"format", "currency", "definition", "grain", "derivation"},
            path,
        )
        metric_id = require_identifier(metric["metric_id"], f"{path}.metric_id")
        if metric_id in metric_ids:
            fail("SCHEMA_DUPLICATE_ERROR", "duplicate metric_id", f"{path}.metric_id")
        metric_ids.add(metric_id)
        require_string(metric["label"], f"{path}.label", max_length=160)
        value_status = require_enum(metric["value_status"], VALUE_STATUSES, f"{path}.value_status")
        value = require_number(metric["value"], f"{path}.value", nullable=True)
        if value_status in {"OBSERVED", "DERIVED"} and value is None:
            fail("VALUE_STATUS_MISMATCH", "observed or derived values cannot be null", f"{path}.value")
        if value_status in VALUE_STATUSES - {"OBSERVED", "DERIVED"} and value is not None:
            fail("VALUE_STATUS_MISMATCH", "missing-state values must be null", f"{path}.value")
        require_string(metric["unit"], f"{path}.unit", allow_empty=True, max_length=32)
        refs = validate_source_refs(metric["source_refs"], f"{path}.source_refs", required=value is not None)
        ensure_known_refs(refs, source_ids, f"{path}.source_refs")
        require_enum(metric["field_level"], FIELD_LEVELS, f"{path}.field_level")
        if "format" in metric:
            require_enum(metric["format"], METRIC_FORMATS, f"{path}.format")
        if "currency" in metric:
            currency = require_string(metric["currency"], f"{path}.currency", max_length=3)
            if not CURRENCY_RE.fullmatch(currency):
                fail("SCHEMA_VALUE_ERROR", "invalid currency", f"{path}.currency")
        for key in ("definition", "grain"):
            if key in metric:
                require_string(metric[key], f"{path}.{key}", max_length=1000)
        if value_status == "DERIVED":
            if "derivation" not in metric:
                fail("DERIVATION_REQUIRED", "derived metric requires derivation", f"{path}.derivation")
            derivation_path = f"{path}.derivation"
            derivation = require_dict(metric["derivation"], derivation_path)
            exact_keys(derivation, {"formula", "input_refs", "calculation_receipt"}, set(), derivation_path)
            require_string(derivation["formula"], f"{derivation_path}.formula", max_length=1000)
            input_refs = validate_string_list(
                derivation["input_refs"], f"{derivation_path}.input_refs", max_items=100, max_length=128
            )
            if not input_refs:
                fail("DERIVATION_REQUIRED", "derived metric requires input references", derivation_path)
            require_string(
                derivation["calculation_receipt"],
                f"{derivation_path}.calculation_receipt",
                max_length=2000,
            )
            derived_inputs.append((metric_id, input_refs, f"{derivation_path}.input_refs"))
        elif "derivation" in metric:
            fail("DERIVATION_NOT_ALLOWED", "only derived metrics may declare derivation", f"{path}.derivation")

    for metric_id, input_refs, path in derived_inputs:
        unknown = sorted(set(input_refs) - metric_ids)
        if unknown:
            fail("UNKNOWN_METRIC_REF", f"unknown derivation input: {unknown[0]}", path)
        if metric_id in input_refs:
            fail("DERIVATION_CYCLE", "metric cannot derive from itself", path)
    return metric_ids


def validate_cell_value(value: Any, data_type: str, path: str) -> None:
    if value is None:
        return
    if data_type in {"number", "integer"}:
        number = require_number(value, path)
        if data_type == "integer" and not float(number).is_integer():
            fail("SCHEMA_VALUE_ERROR", "integer column requires an integer value", path)
        return
    if data_type == "boolean":
        require_bool(value, path)
        return
    require_string(value, path, max_length=4000)


def validate_datasets(value: Any, source_ids: set[str]) -> dict[str, dict[str, Any]]:
    datasets = require_list(value, "$.datasets")
    if len(datasets) > 500:
        fail("SCHEMA_LIMIT_ERROR", "datasets exceed 500 items", "$.datasets")
    result: dict[str, dict[str, Any]] = {}
    for dataset_index, raw in enumerate(datasets):
        path = f"$.datasets[{dataset_index}]"
        dataset = require_dict(raw, path)
        exact_keys(dataset, {"dataset_id", "label", "kind", "source_refs", "columns", "rows"}, set(), path)
        dataset_id = require_identifier(dataset["dataset_id"], f"{path}.dataset_id")
        if dataset_id in result:
            fail("SCHEMA_DUPLICATE_ERROR", "duplicate dataset_id", f"{path}.dataset_id")
        require_string(dataset["label"], f"{path}.label", max_length=200)
        require_enum(dataset["kind"], DATASET_KINDS, f"{path}.kind")
        dataset_refs = validate_source_refs(dataset["source_refs"], f"{path}.source_refs")
        ensure_known_refs(dataset_refs, source_ids, f"{path}.source_refs")

        columns = require_list(dataset["columns"], f"{path}.columns")
        if not columns or len(columns) > 100:
            fail("SCHEMA_LIMIT_ERROR", "dataset needs 1 to 100 columns", f"{path}.columns")
        column_types: dict[str, str] = {}
        for column_index, raw_column in enumerate(columns):
            column_path = f"{path}.columns[{column_index}]"
            column = require_dict(raw_column, column_path)
            exact_keys(column, {"column_id", "label", "data_type"}, {"unit"}, column_path)
            column_id = require_identifier(column["column_id"], f"{column_path}.column_id")
            if column_id in column_types:
                fail("SCHEMA_DUPLICATE_ERROR", "duplicate column_id", f"{column_path}.column_id")
            require_string(column["label"], f"{column_path}.label", max_length=160)
            column_types[column_id] = require_enum(
                column["data_type"], COLUMN_TYPES, f"{column_path}.data_type"
            )
            if "unit" in column:
                require_string(column["unit"], f"{column_path}.unit", allow_empty=True, max_length=32)

        rows = require_list(dataset["rows"], f"{path}.rows")
        if len(rows) > 10000:
            fail("SCHEMA_LIMIT_ERROR", "dataset rows exceed 10000", f"{path}.rows")
        row_ids: set[str] = set()
        for row_index, raw_row in enumerate(rows):
            row_path = f"{path}.rows[{row_index}]"
            row = require_dict(raw_row, row_path)
            exact_keys(row, {"row_id", "values"}, {"label"}, row_path)
            row_id = require_identifier(row["row_id"], f"{row_path}.row_id")
            if row_id in row_ids:
                fail("SCHEMA_DUPLICATE_ERROR", "duplicate row_id", f"{row_path}.row_id")
            row_ids.add(row_id)
            if "label" in row:
                require_string(row["label"], f"{row_path}.label", max_length=200)
            cells = require_list(row["values"], f"{row_path}.values")
            cell_ids: set[str] = set()
            for cell_index, raw_cell in enumerate(cells):
                cell_path = f"{row_path}.values[{cell_index}]"
                cell = require_dict(raw_cell, cell_path)
                exact_keys(cell, {"column_id", "value", "status", "source_refs"}, set(), cell_path)
                column_id = require_identifier(cell["column_id"], f"{cell_path}.column_id")
                if column_id not in column_types:
                    fail("UNKNOWN_COLUMN_REF", "cell references an unknown column", f"{cell_path}.column_id")
                if column_id in cell_ids:
                    fail("SCHEMA_DUPLICATE_ERROR", "duplicate cell column_id", f"{cell_path}.column_id")
                cell_ids.add(column_id)
                status = require_enum(cell["status"], VALUE_STATUSES, f"{cell_path}.status")
                validate_cell_value(cell["value"], column_types[column_id], f"{cell_path}.value")
                if status in {"OBSERVED", "DERIVED"} and cell["value"] is None:
                    fail("VALUE_STATUS_MISMATCH", "observed or derived cell cannot be null", cell_path)
                if status in VALUE_STATUSES - {"OBSERVED", "DERIVED"} and cell["value"] is not None:
                    fail("VALUE_STATUS_MISMATCH", "missing-state cell must be null", cell_path)
                refs = validate_source_refs(
                    cell["source_refs"], f"{cell_path}.source_refs", required=cell["value"] is not None
                )
                ensure_known_refs(refs, source_ids, f"{cell_path}.source_refs")
            if cell_ids != set(column_types):
                missing = sorted(set(column_types) - cell_ids)
                fail("DATASET_ROW_INCOMPLETE", f"row is missing columns: {', '.join(missing)}", row_path)
        result[dataset_id] = dataset
    return result


def dataset_columns(dataset: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {column["column_id"]: column for column in dataset["columns"]}


def validate_dataset_key(
    dataset: dict[str, Any], key: Any, path: str, *, numeric: bool = False
) -> str:
    column_id = require_identifier(key, path)
    columns = dataset_columns(dataset)
    if column_id not in columns:
        fail("UNKNOWN_COLUMN_REF", "component references an unknown column", path)
    if numeric and columns[column_id]["data_type"] not in {"number", "integer"}:
        fail("NON_NUMERIC_COLUMN", "component requires a numeric column", path)
    return column_id


def validate_series(value: Any, dataset: dict[str, Any], path: str) -> None:
    series = require_list(value, path)
    if not 1 <= len(series) <= 8:
        fail("SCHEMA_LIMIT_ERROR", "series requires 1 to 8 entries", path)
    seen: set[str] = set()
    for index, raw in enumerate(series):
        item_path = f"{path}[{index}]"
        item = require_dict(raw, item_path)
        exact_keys(item, {"key"}, {"label"}, item_path)
        key = validate_dataset_key(dataset, item["key"], f"{item_path}.key", numeric=True)
        if key in seen:
            fail("SCHEMA_DUPLICATE_ERROR", "duplicate series key", f"{item_path}.key")
        seen.add(key)
        if "label" in item:
            require_string(item["label"], f"{item_path}.label", max_length=120)


def validate_quote(value: Any, path: str, source_ids: set[str]) -> None:
    quote = require_dict(value, path)
    exact_keys(quote, {"text", "source_ref"}, {"author", "rating", "sentiment"}, path)
    require_string(quote["text"], f"{path}.text", max_length=5000)
    source_ref = require_identifier(quote["source_ref"], f"{path}.source_ref")
    ensure_known_refs([source_ref], source_ids, f"{path}.source_ref")
    if "author" in quote:
        require_string(quote["author"], f"{path}.author", max_length=100)
    if "rating" in quote:
        rating = require_number(quote["rating"], f"{path}.rating")
        if not 0 <= float(rating) <= 5:
            fail("SCHEMA_VALUE_ERROR", "rating must be between 0 and 5", f"{path}.rating")
    if "sentiment" in quote:
        require_enum(quote["sentiment"], {"positive", "negative", "neutral", "mixed"}, f"{path}.sentiment")


def validate_insight_item(value: Any, path: str, source_ids: set[str]) -> None:
    if isinstance(value, str):
        require_string(value, path, max_length=3000)
        return
    item = require_dict(value, path)
    exact_keys(item, {"title"}, {"detail", "severity", "source_refs"}, path)
    require_string(item["title"], f"{path}.title", max_length=240)
    if "detail" in item:
        require_string(item["detail"], f"{path}.detail", max_length=3000)
    if "severity" in item:
        require_enum(item["severity"], {"info", "positive", "warning", "critical"}, f"{path}.severity")
    if "source_refs" in item:
        refs = validate_source_refs(item["source_refs"], f"{path}.source_refs")
        ensure_known_refs(refs, source_ids, f"{path}.source_refs")


def validate_swot_item(value: Any, path: str, source_ids: set[str]) -> None:
    if isinstance(value, str):
        require_string(value, path, max_length=2000)
        return
    item = require_dict(value, path)
    exact_keys(item, {"text"}, {"source_refs"}, path)
    require_string(item["text"], f"{path}.text", max_length=2000)
    if "source_refs" in item:
        refs = validate_source_refs(item["source_refs"], f"{path}.source_refs")
        ensure_known_refs(refs, source_ids, f"{path}.source_refs")


def validate_image_descriptor(value: Any, path: str, source_ids: set[str]) -> None:
    image = require_dict(value, path)
    exact_keys(image, {"src", "alt", "source_ref"}, {"caption"}, path)
    src = image["src"]
    if not isinstance(src, str) or not src.strip():
        fail("SCHEMA_TYPE_ERROR", "image src must be a non-empty string", f"{path}.src")
    if len(src) > (MAX_IMAGE_BYTES * 4 // 3 + 1024):
        fail("IMAGE_TOO_LARGE", "encoded image exceeds 5 MiB", f"{path}.src")
    require_string(image["alt"], f"{path}.alt", max_length=500)
    source_ref = require_identifier(image["source_ref"], f"{path}.source_ref")
    ensure_known_refs([source_ref], source_ids, f"{path}.source_ref")
    if "caption" in image:
        require_string(image["caption"], f"{path}.caption", max_length=1000)


def validate_component(
    value: Any,
    path: str,
    metric_ids: set[str],
    datasets: dict[str, dict[str, Any]],
    source_ids: set[str],
    explicit_component_ids: set[str],
) -> None:
    component = require_dict(value, path)
    if "type" not in component:
        fail("SCHEMA_REQUIRED_ERROR", "missing fields: type", path)
    component_type = require_enum(component["type"], COMPONENT_TYPES, f"{path}.type")
    common_required = {"type"}
    common_optional = {"component_id", "title"}
    if "component_id" in component:
        component_id = require_identifier(component["component_id"], f"{path}.component_id")
        if component_id in explicit_component_ids:
            fail("SCHEMA_DUPLICATE_ERROR", "duplicate component_id", f"{path}.component_id")
        explicit_component_ids.add(component_id)
    if "title" in component:
        require_string(component["title"], f"{path}.title", max_length=200)

    if component_type == "kpi_cards":
        exact_keys(component, common_required | {"metric_ids"}, common_optional, path)
        refs = validate_string_list(component["metric_ids"], f"{path}.metric_ids", max_items=24, max_length=128)
        if not refs:
            fail("SCHEMA_VALUE_ERROR", "kpi_cards requires at least one metric", f"{path}.metric_ids")
        unknown = sorted(set(refs) - metric_ids)
        if unknown:
            fail("UNKNOWN_METRIC_REF", f"unknown metric: {unknown[0]}", f"{path}.metric_ids")
        return

    if component_type in {"distribution", "line_chart", "data_table", "radar_comparison", "keyword_topics"}:
        if "dataset_id" not in component:
            fail("SCHEMA_REQUIRED_ERROR", "missing fields: dataset_id", path)
        dataset_id = require_identifier(component["dataset_id"], f"{path}.dataset_id")
        if dataset_id not in datasets:
            fail("UNKNOWN_DATASET_REF", "component references an unknown dataset", f"{path}.dataset_id")
        dataset = datasets[dataset_id]

        if component_type == "distribution":
            exact_keys(
                component,
                common_required | {"dataset_id", "label_key", "value_key"},
                common_optional | {"chart"},
                path,
            )
            validate_dataset_key(dataset, component["label_key"], f"{path}.label_key")
            validate_dataset_key(dataset, component["value_key"], f"{path}.value_key", numeric=True)
            if "chart" in component:
                require_enum(component["chart"], {"donut", "pie"}, f"{path}.chart")
            return

        if component_type == "line_chart":
            exact_keys(
                component,
                common_required | {"dataset_id", "x_key", "series"},
                common_optional,
                path,
            )
            validate_dataset_key(dataset, component["x_key"], f"{path}.x_key")
            validate_series(component["series"], dataset, f"{path}.series")
            return

        if component_type == "data_table":
            exact_keys(
                component,
                common_required | {"dataset_id"},
                common_optional | {"column_keys", "top_n"},
                path,
            )
            if "column_keys" in component:
                keys = validate_string_list(
                    component["column_keys"], f"{path}.column_keys", max_items=100, max_length=128
                )
                if not keys:
                    fail("SCHEMA_VALUE_ERROR", "column_keys cannot be empty", f"{path}.column_keys")
                for index, key in enumerate(keys):
                    validate_dataset_key(dataset, key, f"{path}.column_keys[{index}]")
            if "top_n" in component:
                top_n = require_number(component["top_n"], f"{path}.top_n")
                if not float(top_n).is_integer() or not 1 <= int(top_n) <= 10000:
                    fail("SCHEMA_VALUE_ERROR", "top_n must be an integer from 1 to 10000", f"{path}.top_n")
            return

        if component_type == "radar_comparison":
            exact_keys(
                component,
                common_required | {"dataset_id", "axis_key", "series"},
                common_optional,
                path,
            )
            validate_dataset_key(dataset, component["axis_key"], f"{path}.axis_key")
            validate_series(component["series"], dataset, f"{path}.series")
            if len(dataset["rows"]) < 3:
                fail("RADAR_DATA_INVALID", "radar comparison requires at least three axes", path)
            return

        exact_keys(
            component,
            common_required | {"dataset_id", "keyword_key", "weight_key"},
            common_optional | {"column_keys"},
            path,
        )
        validate_dataset_key(dataset, component["keyword_key"], f"{path}.keyword_key")
        validate_dataset_key(dataset, component["weight_key"], f"{path}.weight_key", numeric=True)
        if "column_keys" in component:
            keys = validate_string_list(
                component["column_keys"], f"{path}.column_keys", max_items=100, max_length=128
            )
            for index, key in enumerate(keys):
                validate_dataset_key(dataset, key, f"{path}.column_keys[{index}]")
        return

    if component_type == "quote_cards":
        exact_keys(component, common_required | {"quotes"}, common_optional, path)
        quotes = require_list(component["quotes"], f"{path}.quotes")
        if not 1 <= len(quotes) <= 100:
            fail("SCHEMA_LIMIT_ERROR", "quote_cards requires 1 to 100 quotes", f"{path}.quotes")
        for index, quote in enumerate(quotes):
            validate_quote(quote, f"{path}.quotes[{index}]", source_ids)
        return

    if component_type == "summary_insights":
        exact_keys(component, common_required | {"summary", "insights"}, common_optional, path)
        require_string(component["summary"], f"{path}.summary", max_length=5000)
        insights = require_list(component["insights"], f"{path}.insights")
        if not 1 <= len(insights) <= 100:
            fail("SCHEMA_LIMIT_ERROR", "summary_insights requires 1 to 100 insights", f"{path}.insights")
        for index, item in enumerate(insights):
            validate_insight_item(item, f"{path}.insights[{index}]", source_ids)
        return

    if component_type == "swot_grid":
        quadrants = {"strengths", "weaknesses", "opportunities", "threats"}
        exact_keys(component, common_required | quadrants, common_optional, path)
        for quadrant in sorted(quadrants):
            items = require_list(component[quadrant], f"{path}.{quadrant}")
            if not items:
                fail("SCHEMA_VALUE_ERROR", "each SWOT quadrant requires at least one item", f"{path}.{quadrant}")
            if len(items) > 50:
                fail("SCHEMA_LIMIT_ERROR", "SWOT quadrant exceeds 50 items", f"{path}.{quadrant}")
            for index, item in enumerate(items):
                validate_swot_item(item, f"{path}.{quadrant}[{index}]", source_ids)
        return

    if component_type == "evidence_image_grid":
        exact_keys(component, common_required | {"images"}, common_optional, path)
        images = require_list(component["images"], f"{path}.images")
        if not 1 <= len(images) <= 24:
            fail("SCHEMA_LIMIT_ERROR", "image grid requires 1 to 24 images", f"{path}.images")
        for index, image in enumerate(images):
            validate_image_descriptor(image, f"{path}.images[{index}]", source_ids)
        return

    if component_type == "evidence_compare":
        exact_keys(
            component,
            common_required | {"left", "right"},
            common_optional | {"left_label", "right_label"},
            path,
        )
        validate_image_descriptor(component["left"], f"{path}.left", source_ids)
        validate_image_descriptor(component["right"], f"{path}.right", source_ids)
        for key in ("left_label", "right_label"):
            if key in component:
                require_string(component[key], f"{path}.{key}", max_length=100)
        return

    if component_type == "narrative":
        exact_keys(component, common_required | {"paragraphs"}, common_optional, path)
        paragraphs = validate_string_list(
            component["paragraphs"], f"{path}.paragraphs", max_items=200, max_length=10000
        )
        if not paragraphs:
            fail("SCHEMA_VALUE_ERROR", "narrative requires at least one paragraph", f"{path}.paragraphs")
        return

    if component_type == "checklist":
        exact_keys(component, common_required | {"items"}, common_optional, path)
        items = require_list(component["items"], f"{path}.items")
        if not 1 <= len(items) <= 300:
            fail("SCHEMA_LIMIT_ERROR", "checklist requires 1 to 300 items", f"{path}.items")
        for index, raw_item in enumerate(items):
            item_path = f"{path}.items[{index}]"
            item = require_dict(raw_item, item_path)
            exact_keys(item, {"label", "status"}, {"detail"}, item_path)
            require_string(item["label"], f"{item_path}.label", max_length=300)
            require_enum(item["status"], {"done", "pending", "blocked", "warning"}, f"{item_path}.status")
            if "detail" in item:
                require_string(item["detail"], f"{item_path}.detail", max_length=2000)
        return

    fail("UNKNOWN_COMPONENT", f"unsupported component: {component_type}", f"{path}.type")


def validate_sections(
    value: Any,
    metric_ids: set[str],
    datasets: dict[str, dict[str, Any]],
    source_ids: set[str],
) -> None:
    sections = require_list(value, "$.sections")
    if not sections:
        fail("SCHEMA_VALUE_ERROR", "at least one section is required", "$.sections")
    if len(sections) > 100:
        fail("SCHEMA_LIMIT_ERROR", "sections exceed 100 items", "$.sections")
    section_ids: set[str] = set()
    component_ids: set[str] = set()
    for section_index, raw in enumerate(sections):
        path = f"$.sections[{section_index}]"
        section = require_dict(raw, path)
        exact_keys(section, {"section_id", "title", "components"}, {"summary"}, path)
        section_id = require_identifier(section["section_id"], f"{path}.section_id")
        if section_id in section_ids:
            fail("SCHEMA_DUPLICATE_ERROR", "duplicate section_id", f"{path}.section_id")
        section_ids.add(section_id)
        require_string(section["title"], f"{path}.title", max_length=240)
        if "summary" in section:
            require_string(section["summary"], f"{path}.summary", max_length=3000)
        components = require_list(section["components"], f"{path}.components")
        if not components:
            fail("SCHEMA_VALUE_ERROR", "section needs at least one component", f"{path}.components")
        if len(components) > 100:
            fail("SCHEMA_LIMIT_ERROR", "components exceed 100 per section", f"{path}.components")
        for component_index, component in enumerate(components):
            validate_component(
                component,
                f"{path}.components[{component_index}]",
                metric_ids,
                datasets,
                source_ids,
                component_ids,
            )


def validate_limitations(value: Any, source_ids: set[str]) -> None:
    limitations = require_list(value, "$.limitations")
    if len(limitations) > 200:
        fail("SCHEMA_LIMIT_ERROR", "limitations exceed 200 items", "$.limitations")
    ids: set[str] = set()
    for index, raw in enumerate(limitations):
        path = f"$.limitations[{index}]"
        item = require_dict(raw, path)
        exact_keys(item, {"limitation_id", "detail", "severity"}, {"source_refs", "impact"}, path)
        limitation_id = require_identifier(item["limitation_id"], f"{path}.limitation_id")
        if limitation_id in ids:
            fail("SCHEMA_DUPLICATE_ERROR", "duplicate limitation_id", f"{path}.limitation_id")
        ids.add(limitation_id)
        require_string(item["detail"], f"{path}.detail", max_length=3000)
        require_enum(item["severity"], LIMITATION_SEVERITIES, f"{path}.severity")
        if "impact" in item:
            require_string(item["impact"], f"{path}.impact", max_length=2000)
        if "source_refs" in item:
            refs = validate_source_refs(item["source_refs"], f"{path}.source_refs")
            ensure_known_refs(refs, source_ids, f"{path}.source_refs")


def validate_render(value: Any) -> None:
    render = require_dict(value, "$.render")
    exact_keys(render, {"family", "theme", "show_toc"}, set(), "$.render")
    require_enum(render["family"], FAMILIES, "$.render.family")
    require_enum(render["theme"], THEMES, "$.render.theme")
    require_bool(render["show_toc"], "$.render.show_toc")


def validate_spec(spec: Any) -> dict[str, Any]:
    root = require_dict(spec, "$")
    exact_keys(
        root,
        {"protocol", "report", "sources", "metrics", "datasets", "sections", "limitations", "render"},
        set(),
        "$",
    )
    if root["protocol"] != PROTOCOL:
        fail("PROTOCOL_MISMATCH", f"protocol must be {PROTOCOL}", "$.protocol")
    scan_sensitive_strings(root)
    validate_report(root["report"])
    source_ids = validate_sources(root["sources"])
    metric_ids = validate_metrics(root["metrics"], source_ids)
    for index, metric in enumerate(root["metrics"]):
        is_fact = metric["value_status"] in {"OBSERVED", "DERIVED"} and metric["value"] is not None
        if (
            metric["field_level"] == "basic_required"
            and not is_fact
            and root["report"]["status"] != "BLOCKED"
        ):
            fail(
                "BASIC_FIELD_UNAVAILABLE",
                "a missing basic_required metric requires report status BLOCKED",
                f"$.metrics[{index}]",
            )
        if (
            root["report"]["report_edition"] == "ENHANCED_FULL"
            and metric["field_level"] == "full_required"
            and not is_fact
        ):
            fail(
                "FULL_EDITION_FIELD_UNAVAILABLE",
                "ENHANCED_FULL requires every full_required metric to be factual",
                f"$.metrics[{index}]",
            )
    datasets = validate_datasets(root["datasets"], source_ids)
    validate_sections(root["sections"], metric_ids, datasets, source_ids)
    validate_limitations(root["limitations"], source_ids)
    validate_render(root["render"])
    return root


class ImageResolver:
    """Resolve only local in-tree raster evidence and canonical raster data URIs."""

    DATA_URI_RE = re.compile(r"^data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=\r\n]+)$", re.IGNORECASE)

    def __init__(self, spec_root: Path) -> None:
        self.spec_root = spec_root.resolve()
        self.total_bytes = 0
        self.records: list[dict[str, Any]] = []

    @staticmethod
    def detect_media(payload: bytes, path: str) -> str:
        if payload.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if payload.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if len(payload) >= 12 and payload[:4] == b"RIFF" and payload[8:12] == b"WEBP":
            return "image/webp"
        fail("IMAGE_TYPE_REJECTED", "image must be PNG, JPEG, or WebP", path)

    def add_payload(self, payload: bytes, claimed_media: str | None, path: str) -> str:
        if len(payload) > MAX_IMAGE_BYTES:
            fail("IMAGE_TOO_LARGE", "image exceeds 5 MiB", path)
        media = self.detect_media(payload, path)
        if claimed_media is not None and claimed_media.lower() != media:
            fail("IMAGE_TYPE_MISMATCH", "data URI media type does not match image bytes", path)
        if self.total_bytes + len(payload) > MAX_TOTAL_IMAGE_BYTES:
            fail("IMAGE_TOTAL_TOO_LARGE", "embedded images exceed 20 MiB total", path)
        self.total_bytes += len(payload)
        digest = sha256_bytes(payload)
        self.records.append({"sha256": digest, "bytes": len(payload), "media_type": media})
        encoded = base64.b64encode(payload).decode("ascii")
        return f"data:{media};base64,{encoded}"

    def resolve(self, src: str, path: str) -> str:
        match = self.DATA_URI_RE.fullmatch(src.strip())
        if match:
            encoded = re.sub(r"\s+", "", match.group(2))
            if (len(encoded) * 3 // 4) > MAX_IMAGE_BYTES:
                fail("IMAGE_TOO_LARGE", "encoded image exceeds 5 MiB", path)
            try:
                payload = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError):
                fail("IMAGE_DATA_INVALID", "invalid base64 image data", path)
            return self.add_payload(payload, f"image/{match.group(1).lower()}", path)

        if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", src) or src.startswith("//"):
            fail("REMOTE_IMAGE_REJECTED", "remote and URI-scheme image sources are forbidden", path)
        candidate = Path(src)
        if candidate.is_absolute():
            resolved = candidate.resolve()
        else:
            resolved = (self.spec_root / candidate).resolve()
        try:
            resolved.relative_to(self.spec_root)
        except ValueError:
            fail("IMAGE_PATH_REJECTED", "image must remain inside the spec directory tree", path)
        if not resolved.is_file():
            fail("IMAGE_NOT_FOUND", "local evidence image does not exist", path)
        if resolved.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            fail("IMAGE_TYPE_REJECTED", "local image extension is not allowed", path)
        try:
            file_size = resolved.stat().st_size
            if file_size > MAX_IMAGE_BYTES:
                fail("IMAGE_TOO_LARGE", "image exceeds 5 MiB", path)
            payload = resolved.read_bytes()
        except OSError:
            fail("IMAGE_READ_ERROR", "local evidence image could not be read", path)
        return self.add_payload(payload, None, path)


def prepare_images(spec: dict[str, Any], spec_root: Path) -> tuple[dict[str, Any], list[dict[str, Any]], int]:
    prepared = copy.deepcopy(spec)
    resolver = ImageResolver(spec_root)
    for section_index, section in enumerate(prepared["sections"]):
        for component_index, component in enumerate(section["components"]):
            base = f"$.sections[{section_index}].components[{component_index}]"
            if component["type"] == "evidence_image_grid":
                for image_index, image in enumerate(component["images"]):
                    image["src"] = resolver.resolve(image["src"], f"{base}.images[{image_index}].src")
            elif component["type"] == "evidence_compare":
                for side in ("left", "right"):
                    component[side]["src"] = resolver.resolve(
                        component[side]["src"], f"{base}.{side}.src"
                    )
    return prepared, resolver.records, resolver.total_bytes


def select_family(spec: dict[str, Any], override: str) -> tuple[str, list[str]]:
    warnings: list[str] = []
    if override != "auto":
        configured = spec["render"]["family"]
        if configured != "auto" and configured != override:
            warnings.append("FAMILY_OVERRIDE_CONFLICT")
        return override, warnings
    configured = spec["render"]["family"]
    if configured != "auto":
        return configured, warnings
    report_type = spec["report"]["report_type"].lower()
    if report_type == "custom":
        fail("FAMILY_REQUIRED", "custom reports require an explicit layout family", "$.render.family")
    mappings = (
        ("performance", ("ads", "advert", "weekly", "inventory", "profit", "performance", "广告", "周报", "库存", "利润")),
        ("insight", ("voc", "review", "research", "competitor", "keyword", "comparison", "mcp", "选品", "竞品", "关键词")),
        ("operations", ("operations", "daily", "sop", "checklist", "action", "日常", "检查", "行动")),
        ("knowledge", ("knowledge", "policy", "method", "retrospective", "知识", "政策", "方法")),
    )
    for family, keywords in mappings:
        if any(keyword in report_type for keyword in keywords):
            return family, warnings
    fail("FAMILY_UNRESOLVED", "report_type cannot be mapped to a layout family", "$.report.report_type")


def row_cells(row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {cell["column_id"]: cell for cell in row["values"]}


def column_label(dataset: dict[str, Any], column_id: str) -> str:
    return dataset_columns(dataset)[column_id]["label"]


def column_unit(dataset: dict[str, Any], column_id: str) -> str:
    return dataset_columns(dataset)[column_id].get("unit", "")


def status_label(status: str, zh: bool) -> str:
    labels = {
        "MISSING": ("缺失", "Missing"),
        "CONFLICT": ("冲突", "Conflict"),
        "NO_ROW": ("无数据行", "No row"),
        "NO_ACCESS": ("无权限", "No access"),
        "COLLECTION_FAILURE": ("采集失败", "Collection failed"),
        "NOT_APPLICABLE": ("不适用", "Not applicable"),
        "NO_BASELINE": ("无基线", "No baseline"),
        "DERIVED": ("派生", "Derived"),
        "OBSERVED": ("已观测", "Observed"),
    }
    pair = labels.get(status, (status, status))
    return pair[0] if zh else pair[1]


def number_text(value: float | int, decimals: int = 2) -> str:
    if float(value).is_integer():
        return f"{int(value):,}"
    return f"{float(value):,.{decimals}f}".rstrip("0").rstrip(".")


def display_metric(metric: dict[str, Any], report_currency: str, zh: bool) -> str:
    value = metric["value"]
    if value is None:
        return status_label(metric["value_status"], zh)
    fmt = metric.get("format", "number")
    unit = metric.get("unit", "")
    if fmt == "integer":
        rendered = f"{int(round(float(value))):,}"
    elif fmt == "currency":
        currency = metric.get("currency", report_currency)
        symbols = {"USD": "$", "CNY": "¥", "EUR": "€", "GBP": "£", "JPY": "¥"}
        rendered = f"{symbols.get(currency, currency + ' ')}{number_text(value)}"
    elif fmt in {"percent", "signed_percent"}:
        sign = "+" if fmt == "signed_percent" and float(value) > 0 else ""
        rendered = f"{sign}{number_text(value)}%"
    elif fmt == "ratio":
        rendered = f"{number_text(value)}x"
    else:
        rendered = number_text(value)
    if unit and fmt not in {"currency", "percent", "signed_percent", "ratio"}:
        rendered = f"{rendered} {unit}"
    return rendered


def display_cell(cell: dict[str, Any], column: dict[str, Any], zh: bool) -> str:
    value = cell["value"]
    if value is None:
        return status_label(cell["status"], zh)
    data_type = column["data_type"]
    if data_type == "integer":
        rendered = f"{int(value):,}"
    elif data_type == "number":
        rendered = number_text(value)
    elif data_type == "boolean":
        rendered = ("是" if value else "否") if zh else ("Yes" if value else "No")
    else:
        rendered = str(value)
    unit = column.get("unit", "")
    return f"{rendered} {unit}".strip()


def visible_width_units(value: Any) -> float:
    """Estimate visible text width with CJK/fullwidth characters as one unit."""

    text = re.sub(r"\s+", " ", unicodedata.normalize("NFC", str(value))).strip()
    units = 0.0
    for character in text:
        category = unicodedata.category(character)
        if category.startswith(("M", "C")):
            continue
        units += 1.0 if unicodedata.east_asian_width(character) in {"W", "F"} else 0.5
    return units


def column_width_profile(label: Any, values: Iterable[Any]) -> tuple[float, int | None]:
    """Return the maximum visible width and its bounded adaptive CSS width."""

    max_units = max((visible_width_units(value) for value in (label, *values)), default=0.0)
    if max_units <= COMPACT_COLUMN_MAX_UNITS:
        return max_units, None
    width_em = ADAPTIVE_COLUMN_WIDTH_STEP_EM * math.ceil(
        (max_units + 2.0) / ADAPTIVE_COLUMN_WIDTH_STEP_EM
    )
    return max_units, min(
        MAX_ADAPTIVE_COLUMN_WIDTH_EM,
        max(MIN_ADAPTIVE_COLUMN_WIDTH_EM, width_em),
    )


def table_layout_class(
    column_count: int,
    profiles: Iterable[tuple[float, int | None]],
) -> str:
    """Preserve the 4/5/14-column layout tiers while using adaptive widths."""

    if column_count >= 14:
        return "table-layout-dense"
    if column_count >= 5 or (column_count >= 4 and any(width_em for _, width_em in profiles)):
        return "table-layout-wide"
    return "table-layout-standard"


def source_badges(refs: Iterable[str]) -> str:
    return "".join(f'<span class="source-ref">{esc(ref)}</span>' for ref in refs)


def stable_html_id(prefix: str, raw: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", raw).strip("-").lower() or "item"
    digest = sha256_bytes(raw.encode("utf-8"))[:8]
    return f"{prefix}-{slug[:48]}-{digest}"


def clip_label(value: Any, limit: int = 18) -> str:
    text = str(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def svg_shell(svg_id: str, title: str, description: str, content: str, view_box: str = "0 0 640 360") -> str:
    title_id = f"{svg_id}-title"
    desc_id = f"{svg_id}-desc"
    return (
        f'<svg id="{esc(svg_id)}" class="chart-svg" viewBox="{view_box}" role="img" '
        f'aria-labelledby="{esc(title_id)} {esc(desc_id)}" xmlns="http://www.w3.org/2000/svg">'
        f'<title id="{esc(title_id)}">{esc(title)}</title>'
        f'<desc id="{esc(desc_id)}">{esc(description)}</desc>{content}</svg>'
    )


class ReportRenderer:
    """Render validated structures without evaluating or injecting upstream markup."""

    PALETTE = ("#ff9900", "#334155", "#64748b", "#94a3b8", "#475569", "#78716c", "#a8a29e", "#cbd5e1")

    def __init__(self, spec: dict[str, Any], family: str) -> None:
        self.spec = spec
        self.family = family
        self.report = spec["report"]
        self.zh = self.report["locale"].lower().startswith("zh")
        self.metrics = {metric["metric_id"]: metric for metric in spec["metrics"]}
        self.datasets = {dataset["dataset_id"]: dataset for dataset in spec["datasets"]}
        self.sources = {source["source_id"]: source for source in spec["sources"]}
        self.warnings: list[str] = []

    def warn(self, code: str) -> None:
        if code not in self.warnings:
            self.warnings.append(code)

    def component_title(self, component: dict[str, Any]) -> str:
        if component.get("title"):
            return component["title"]
        labels = {
            "kpi_cards": ("核心指标", "Key metrics"),
            "distribution": ("分布与占比", "Distribution"),
            "line_chart": ("趋势", "Trend"),
            "data_table": ("数据明细", "Data table"),
            "radar_comparison": ("多维对比", "Multi-dimensional comparison"),
            "quote_cards": ("原始文本证据", "Quoted evidence"),
            "keyword_topics": ("关键词与话题", "Keywords and topics"),
            "summary_insights": ("结论与建议", "Summary and insights"),
            "swot_grid": ("综合研判", "SWOT assessment"),
            "evidence_image_grid": ("图片视觉证据", "Visual evidence"),
            "evidence_compare": ("证据对比", "Evidence comparison"),
            "narrative": ("说明", "Narrative"),
            "checklist": ("检查清单", "Checklist"),
        }
        pair = labels[component["type"]]
        return pair[0] if self.zh else pair[1]

    def component_frame(self, component: dict[str, Any], component_id: str, body: str) -> str:
        if not body:
            return ""
        return (
            f'<div class="report-component component-{esc(component["type"])}" id="{esc(component_id)}">'
            f'<h3>{esc(self.component_title(component))}</h3>{body}</div>'
        )

    def render_kpi_cards(self, component: dict[str, Any]) -> str:
        cards: list[str] = []
        for metric_id in component["metric_ids"]:
            metric = self.metrics[metric_id]
            status = metric["value_status"].lower()
            value = display_metric(metric, self.report["currency"], self.zh)
            definition = metric.get("definition", "")
            detail = f'<p class="metric-detail">{esc(definition)}</p>' if definition else ""
            cards.append(
                f'<article class="kpi-card status-{esc(status)}">'
                f'<p class="kpi-label">{esc(metric["label"])}</p>'
                f'<p class="kpi-value">{esc(value)}</p>'
                f'<div class="kpi-meta"><span class="value-status">{esc(status_label(metric["value_status"], self.zh))}</span>'
                f'{source_badges(metric["source_refs"])}</div>{detail}</article>'
            )
        return f'<div class="kpi-grid">{"".join(cards)}</div>'

    @staticmethod
    def table_column_classes(
        index: int,
        data_type: str,
        profile: tuple[float, int | None],
        *,
        ordinal: bool = False,
    ) -> str:
        """Map one audited column to semantic and adaptive-width CSS classes."""

        max_units, width_em = profile
        classes: list[str] = []
        if index == 0:
            classes.append("table-col-primary")
        if data_type in {"number", "integer"}:
            classes.append("table-col-numeric")
        elif index != 0 and data_type in {"boolean", "date", "datetime"}:
            classes.append("table-col-compact")
        elif index != 0:
            classes.append("table-col-text")
        if width_em is None:
            classes.append("table-col-short")
        else:
            classes.extend(("table-col-expanded", f"table-col-width-{width_em}"))
            if max_units + 2.0 > MAX_ADAPTIVE_COLUMN_WIDTH_EM:
                classes.append("table-col-capped")
        if ordinal:
            classes.append("table-col-ordinal")
        if index < PRIORITY_TABLE_COLUMN_COUNT and width_em is None:
            classes.append("table-cell-priority")
        return " ".join(classes)

    def render_dataset_table(
        self,
        dataset: dict[str, Any],
        column_keys: list[str] | None = None,
        top_n: int | None = None,
        caption: str | None = None,
        table_class: str = "data-table",
    ) -> str:
        if not dataset["rows"]:
            self.warn(f"EMPTY_DATASET:{dataset['dataset_id']}")
            return ""
        columns = dataset_columns(dataset)
        keys = column_keys or list(columns)
        rows = dataset["rows"][:top_n] if top_n is not None else dataset["rows"]
        rendered_values = {
            key: [display_cell(row_cells(row)[key], columns[key], self.zh) for row in rows]
            for key in keys
        }
        column_profiles = {
            key: column_width_profile(columns[key]["label"], rendered_values[key])
            for key in keys
        }
        ordinal_keys = {
            key
            for key in keys
            if any(
                token in {str(key).strip().lower(), str(columns[key]["label"]).strip().lower()}
                or str(columns[key]["label"]).strip().lower().endswith(token)
                for token in ORDINAL_COLUMN_TOKENS
            )
            and all(visible_width_units(value) <= ORDINAL_CELL_MAX_UNITS for value in rendered_values[key])
        }
        layout_class = table_layout_class(len(keys), column_profiles.values())

        def column_classes(index: int, key: str) -> str:
            return self.table_column_classes(
                index,
                columns[key]["data_type"],
                column_profiles[key],
                ordinal=key in ordinal_keys,
            )

        headers = "".join(
            f'<th scope="col" class="{column_classes(index, key)}">'
            f'{esc(columns[key]["label"])}</th>'
            for index, key in enumerate(keys)
        )
        body_rows: list[str] = []
        for row in rows:
            cells = row_cells(row)
            rendered_cells: list[str] = []
            for index, key in enumerate(keys):
                cell = cells[key]
                value = display_cell(cell, columns[key], self.zh)
                tag = "th" if index == 0 else "td"
                scope = ' scope="row"' if index == 0 else ""
                classes = (
                    f'cell-{esc(cell["status"].lower())} '
                    f'{column_classes(index, key)}'
                )
                refs = ", ".join(cell["source_refs"])
                provenance = (
                    f'<span class="sr-only">{esc("来源" if self.zh else "Sources")}: {esc(refs)}</span>'
                    if refs
                    else ""
                )
                rendered_cells.append(
                    f'<{tag}{scope} class="{classes}">'
                    f'{esc(value)}{provenance}</{tag}>'
                )
            body_rows.append(f'<tr>{"".join(rendered_cells)}</tr>')
        source_note = source_badges(dataset["source_refs"])
        table_caption = caption or dataset["label"]
        return (
            '<div class="table-scroll" tabindex="0" role="region" '
            f'aria-label="{esc(table_caption)}">'
            f'<table class="{esc(table_class)} {layout_class}"><caption>{esc(table_caption)}</caption>'
            f'<thead><tr>{headers}</tr></thead><tbody>{"".join(body_rows)}</tbody></table></div>'
            f'<div class="dataset-sources">{source_note}</div>'
        )

    @staticmethod
    def pie_sector(cx: float, cy: float, radius: float, start: float, end: float) -> str:
        start_x = cx + radius * math.cos(start)
        start_y = cy + radius * math.sin(start)
        end_x = cx + radius * math.cos(end)
        end_y = cy + radius * math.sin(end)
        large_arc = 1 if end - start > math.pi else 0
        return (
            f"M {cx:.2f} {cy:.2f} L {start_x:.2f} {start_y:.2f} "
            f"A {radius:.2f} {radius:.2f} 0 {large_arc} 1 {end_x:.2f} {end_y:.2f} Z"
        )

    def render_distribution(self, component: dict[str, Any], html_id: str) -> str:
        dataset = self.datasets[component["dataset_id"]]
        label_key = component["label_key"]
        value_key = component["value_key"]
        columns = dataset_columns(dataset)
        items: list[tuple[str, float, dict[str, Any]]] = []
        for row in dataset["rows"]:
            cells = row_cells(row)
            value = cells[value_key]["value"]
            if value is None:
                continue
            if float(value) < 0:
                self.warn(f"NEGATIVE_DISTRIBUTION_SKIPPED:{dataset['dataset_id']}")
                return ""
            label_value = cells[label_key]["value"]
            items.append((str(label_value), float(value), cells[value_key]))
        total = sum(item[1] for item in items)
        if not items or total <= 0:
            self.warn(f"EMPTY_DISTRIBUTION:{dataset['dataset_id']}")
            return ""
        chart_kind = component.get("chart", "donut")
        chart_parts: list[str] = []
        start = -math.pi / 2
        for index, (_, value, _) in enumerate(items):
            fraction = value / total
            end = start + fraction * math.tau
            color = self.PALETTE[index % len(self.PALETTE)]
            if chart_kind == "pie":
                path = self.pie_sector(180, 170, 125, start, end)
                chart_parts.append(f'<path d="{path}" fill="{color}" stroke="var(--surface)" stroke-width="2"/>')
            else:
                circumference = 2 * math.pi * 110
                dash = fraction * circumference
                offset = -((start + math.pi / 2) / math.tau) * circumference
                chart_parts.append(
                    f'<circle cx="180" cy="170" r="110" fill="none" stroke="{color}" stroke-width="44" '
                    f'stroke-dasharray="{dash:.2f} {circumference - dash:.2f}" '
                    f'stroke-dashoffset="{offset:.2f}" transform="rotate(-90 180 170)"/>'
                )
            start = end
        if chart_kind == "donut":
            chart_parts.append(
                f'<text x="180" y="165" text-anchor="middle" class="svg-total-label">'
                f'{esc("合计" if self.zh else "Total")}</text>'
                f'<text x="180" y="193" text-anchor="middle" class="svg-total-value">{esc(number_text(total))}</text>'
            )
        legend: list[str] = []
        for index, (label, value, cell) in enumerate(items):
            share = value / total * 100
            percent_class = f"pct-{max(0, min(100, int(round(share))))}"
            legend.append(
                '<div class="distribution-row">'
                f'<div class="distribution-label"><span class="legend-swatch swatch-{index % len(self.PALETTE)}"></span>'
                f'<span>{esc(label)}</span><strong>{esc(number_text(value))}</strong></div>'
                f'<div class="progress-track" role="progressbar" aria-valuemin="0" aria-valuemax="100" '
                f'aria-valuenow="{share:.2f}" aria-label="{esc(label)}"><span class="progress-fill {percent_class}"></span></div>'
                f'<small>{share:.1f}% {source_badges(cell["source_refs"])}</small></div>'
            )
        description = "; ".join(f"{label}: {number_text(value)}" for label, value, _ in items)
        svg = svg_shell(
            f"{html_id}-svg",
            self.component_title(component),
            description,
            "".join(chart_parts),
            "0 0 360 340",
        )
        summary = self.render_dataset_table(
            dataset,
            [label_key, value_key],
            caption=("分布数据摘要" if self.zh else "Distribution data summary"),
            table_class="chart-summary-table",
        )
        return (
            f'<div class="distribution-layout"><div>{svg}</div><div class="distribution-list">{"".join(legend)}</div></div>'
            f'<details class="chart-data"><summary>{esc("查看图表数据" if self.zh else "View chart data")}</summary>{summary}</details>'
        )

    def render_line_chart(self, component: dict[str, Any], html_id: str) -> str:
        dataset = self.datasets[component["dataset_id"]]
        if not dataset["rows"]:
            self.warn(f"EMPTY_SERIES:{dataset['dataset_id']}")
            return ""
        x_key = component["x_key"]
        series = component["series"]
        all_values: list[float] = []
        for row in dataset["rows"]:
            cells = row_cells(row)
            for item in series:
                value = cells[item["key"]]["value"]
                if value is not None:
                    all_values.append(float(value))
        if not all_values:
            self.warn(f"EMPTY_SERIES:{dataset['dataset_id']}")
            return ""
        minimum = min(all_values)
        maximum = max(all_values)
        if math.isclose(minimum, maximum):
            padding = abs(minimum) * 0.1 or 1.0
            minimum -= padding
            maximum += padding
        else:
            padding = (maximum - minimum) * 0.08
            minimum -= padding
            maximum += padding
        left, top, width, height = 58.0, 34.0, 548.0, 250.0

        def point(index: int, value: float) -> tuple[float, float]:
            x = left + (width / max(1, len(dataset["rows"]) - 1)) * index
            y = top + (maximum - value) / (maximum - minimum) * height
            return x, y

        grid: list[str] = []
        for tick in range(5):
            y = top + height * tick / 4
            label_value = maximum - (maximum - minimum) * tick / 4
            grid.append(
                f'<line x1="{left}" y1="{y:.2f}" x2="{left + width}" y2="{y:.2f}" class="svg-grid"/>'
                f'<text x="{left - 8}" y="{y + 4:.2f}" text-anchor="end" class="svg-axis-label">'
                f'{esc(number_text(label_value))}</text>'
            )
        chart: list[str] = grid
        legend: list[str] = []
        description_parts: list[str] = []
        for series_index, item in enumerate(series):
            color = self.PALETTE[series_index % len(self.PALETTE)]
            label = item.get("label") or column_label(dataset, item["key"])
            segments: list[list[tuple[float, float]]] = []
            current: list[tuple[float, float]] = []
            present: list[float] = []
            for row_index, row in enumerate(dataset["rows"]):
                value = row_cells(row)[item["key"]]["value"]
                if value is None:
                    if current:
                        segments.append(current)
                        current = []
                    continue
                numeric = float(value)
                present.append(numeric)
                current.append(point(row_index, numeric))
            if current:
                segments.append(current)
            for segment in segments:
                if len(segment) == 1:
                    x, y = segment[0]
                    chart.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="{color}"/>')
                    continue
                path_data = " ".join(
                    ("M" if index == 0 else "L") + f" {x:.2f} {y:.2f}"
                    for index, (x, y) in enumerate(segment)
                )
                chart.append(
                    f'<path d="{path_data}" fill="none" stroke="{color}" stroke-width="3" '
                    f'stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>'
                )
                chart.extend(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3" fill="{color}"/>' for x, y in segment)
            legend.append(
                f'<span class="chart-legend-item"><span class="legend-swatch swatch-{series_index % len(self.PALETTE)}"></span>{esc(label)}</span>'
            )
            if present:
                description_parts.append(f"{label}: {number_text(min(present))} to {number_text(max(present))}")
        first_x = row_cells(dataset["rows"][0])[x_key]["value"]
        last_x = row_cells(dataset["rows"][-1])[x_key]["value"]
        chart.append(
            f'<text x="{left}" y="{top + height + 30}" class="svg-axis-label">{esc(clip_label(first_x))}</text>'
            f'<text x="{left + width}" y="{top + height + 30}" text-anchor="end" class="svg-axis-label">{esc(clip_label(last_x))}</text>'
        )
        svg = svg_shell(
            f"{html_id}-svg",
            self.component_title(component),
            "; ".join(description_parts),
            "".join(chart),
            "0 0 640 340",
        )
        keys = [x_key] + [item["key"] for item in series]
        summary = self.render_dataset_table(
            dataset,
            keys,
            caption=("趋势图数据摘要" if self.zh else "Trend chart data summary"),
            table_class="chart-summary-table",
        )
        return (
            f'<div class="chart-legend">{"".join(legend)}</div>{svg}'
            f'<details class="chart-data"><summary>{esc("查看图表数据" if self.zh else "View chart data")}</summary>{summary}</details>'
        )

    def render_radar(self, component: dict[str, Any], html_id: str) -> str:
        dataset = self.datasets[component["dataset_id"]]
        axis_key = component["axis_key"]
        series = component["series"]
        rows = dataset["rows"]
        center_x, center_y, radius = 240.0, 190.0, 132.0
        axis_count = len(rows)
        values_by_series: list[list[float] | None] = []
        for item in series:
            values: list[float] = []
            valid = True
            for row in rows:
                value = row_cells(row)[item["key"]]["value"]
                if value is None or float(value) < 0:
                    valid = False
                    break
                values.append(float(value))
            values_by_series.append(values if valid else None)
        radar_available = all(values is not None for values in values_by_series)
        svg = ""
        if radar_available:
            typed_values = [values for values in values_by_series if values is not None]
            axis_maxima = [max(1.0, *(values[index] for values in typed_values)) for index in range(axis_count)]

            def axis_point(axis_index: int, factor: float) -> tuple[float, float]:
                angle = -math.pi / 2 + math.tau * axis_index / axis_count
                return (
                    center_x + radius * factor * math.cos(angle),
                    center_y + radius * factor * math.sin(angle),
                )

            content: list[str] = []
            for ring in (0.25, 0.5, 0.75, 1.0):
                points = " ".join(f"{x:.2f},{y:.2f}" for x, y in (axis_point(i, ring) for i in range(axis_count)))
                content.append(f'<polygon points="{points}" class="radar-ring"/>')
            for axis_index, row in enumerate(rows):
                x, y = axis_point(axis_index, 1.0)
                lx, ly = axis_point(axis_index, 1.18)
                label = row_cells(row)[axis_key]["value"]
                anchor = "middle" if abs(lx - center_x) < 10 else ("start" if lx > center_x else "end")
                content.append(
                    f'<line x1="{center_x}" y1="{center_y}" x2="{x:.2f}" y2="{y:.2f}" class="radar-axis"/>'
                    f'<text x="{lx:.2f}" y="{ly:.2f}" text-anchor="{anchor}" class="radar-label">{esc(clip_label(label, 12))}</text>'
                )
            legend: list[str] = []
            for series_index, (item, values) in enumerate(zip(series, typed_values)):
                points = " ".join(
                    f"{x:.2f},{y:.2f}"
                    for x, y in (
                        axis_point(axis_index, value / axis_maxima[axis_index])
                        for axis_index, value in enumerate(values)
                    )
                )
                color = self.PALETTE[series_index % len(self.PALETTE)]
                content.append(
                    f'<polygon points="{points}" fill="{color}" fill-opacity="0.14" stroke="{color}" stroke-width="3"/>'
                )
                label = item.get("label") or column_label(dataset, item["key"])
                legend.append(
                    f'<span class="chart-legend-item"><span class="legend-swatch swatch-{series_index % len(self.PALETTE)}"></span>{esc(label)}</span>'
                )
            description = "; ".join(
                f"{(item.get('label') or column_label(dataset, item['key']))}: "
                + ", ".join(number_text(value) for value in values)
                for item, values in zip(series, typed_values)
            )
            svg = (
                f'<div class="chart-legend">{"".join(legend)}</div>'
                + svg_shell(
                    f"{html_id}-svg",
                    self.component_title(component),
                    description,
                    "".join(content),
                    "0 0 480 390",
                )
                + f'<p class="chart-note">{esc("雷达图按各维度可用最大值归一化，原值见对比表。" if self.zh else "Radar axes are normalized to each dimension maximum; raw values remain in the comparison grid.")}</p>'
            )
        else:
            self.warn(f"RADAR_INCOMPLETE:{dataset['dataset_id']}")
            svg = f'<p class="quality-note">{esc("雷达图因缺失或负值未生成，原始对比数据保留如下。" if self.zh else "Radar chart omitted because values are missing or negative; the raw comparison remains below.")}</p>'
        keys = [axis_key] + [item["key"] for item in series]
        grid = self.render_dataset_table(
            dataset,
            keys,
            caption=("多维对比明细" if self.zh else "Comparison grid"),
            table_class="comparison-table",
        )
        return f'<div class="radar-layout"><div>{svg}</div><div>{grid}</div></div>'

    def render_quotes(self, component: dict[str, Any]) -> str:
        cards: list[str] = []
        for quote in component["quotes"]:
            meta: list[str] = []
            if quote.get("author"):
                meta.append(quote["author"])
            if "rating" in quote:
                meta.append(f'{number_text(quote["rating"])} / 5')
            if quote.get("sentiment"):
                meta.append(quote["sentiment"])
            cards.append(
                f'<figure class="quote-card sentiment-{esc(quote.get("sentiment", "neutral"))}">'
                f'<blockquote>{esc(quote["text"])}</blockquote>'
                f'<figcaption>{esc(" · ".join(meta))}{source_badges([quote["source_ref"]])}</figcaption>'
                f'</figure>'
            )
        return f'<div class="quote-grid">{"".join(cards)}</div>'

    def render_keywords(self, component: dict[str, Any]) -> str:
        dataset = self.datasets[component["dataset_id"]]
        keyword_key = component["keyword_key"]
        weight_key = component["weight_key"]
        weighted: list[tuple[str, float]] = []
        for row in dataset["rows"]:
            cells = row_cells(row)
            keyword = cells[keyword_key]["value"]
            weight = cells[weight_key]["value"]
            if keyword is None or weight is None:
                continue
            if float(weight) < 0:
                self.warn(f"NEGATIVE_KEYWORD_WEIGHT:{dataset['dataset_id']}")
                continue
            weighted.append((str(keyword), float(weight)))
        cloud = ""
        if weighted:
            low = min(weight for _, weight in weighted)
            high = max(weight for _, weight in weighted)
            tags: list[str] = []
            for keyword, weight in sorted(weighted, key=lambda pair: (-pair[1], pair[0])):
                ratio = 0.5 if math.isclose(low, high) else (weight - low) / (high - low)
                bucket = 1 + min(4, int(ratio * 4.999))
                tags.append(f'<span class="topic-tag tag-size-{bucket}">{esc(keyword)}<small>{esc(number_text(weight))}</small></span>')
            cloud = f'<div class="tag-cloud" aria-label="{esc("关键词云" if self.zh else "Keyword cloud")}">{"".join(tags)}</div>'
        else:
            self.warn(f"EMPTY_KEYWORDS:{dataset['dataset_id']}")
        keys = component.get("column_keys") or [keyword_key, weight_key]
        table = self.render_dataset_table(
            dataset,
            keys,
            caption=("关键词与话题明细" if self.zh else "Keyword and topic details"),
        )
        return cloud + table

    def render_summary(self, component: dict[str, Any]) -> str:
        items: list[str] = []
        for insight in component["insights"]:
            if isinstance(insight, str):
                title, detail, severity, refs = insight, "", "info", []
            else:
                title = insight["title"]
                detail = insight.get("detail", "")
                severity = insight.get("severity", "info")
                refs = insight.get("source_refs", [])
            detail_html = f'<p>{esc(detail)}</p>' if detail else ""
            items.append(
                f'<li class="insight-{esc(severity)}"><div><strong>{esc(title)}</strong>{detail_html}</div>'
                f'<div class="insight-sources">{source_badges(refs)}</div></li>'
            )
        demo = ""
        if self.report["data_mode"] == "DEMO":
            demo = f'<p class="demo-inline">{esc("演示数据不可用于真实业务决策。" if self.zh else "Demo data must not be used for live business decisions.")}</p>'
        return (
            f'<div class="summary-box"><p>{esc(component["summary"])}</p>{demo}</div>'
            f'<ul class="insight-list">{"".join(items)}</ul>'
        )

    def render_swot(self, component: dict[str, Any]) -> str:
        labels = {
            "strengths": ("优势", "Strengths"),
            "weaknesses": ("劣势", "Weaknesses"),
            "opportunities": ("机会", "Opportunities"),
            "threats": ("威胁", "Threats"),
        }
        quadrants: list[str] = []
        for key in ("strengths", "weaknesses", "opportunities", "threats"):
            rendered_items: list[str] = []
            for item in component[key]:
                if isinstance(item, str):
                    text, refs = item, []
                else:
                    text, refs = item["text"], item.get("source_refs", [])
                rendered_items.append(f'<li>{esc(text)}<div>{source_badges(refs)}</div></li>')
            label = labels[key][0] if self.zh else labels[key][1]
            quadrants.append(
                f'<article class="swot-quadrant swot-{key}"><h4>{esc(label)}</h4><ul>{"".join(rendered_items)}</ul></article>'
            )
        return f'<div class="swot-grid">{"".join(quadrants)}</div>'

    def image_figure(self, image: dict[str, Any], extra_class: str = "") -> str:
        caption = image.get("caption", "")
        return (
            f'<figure class="evidence-figure {esc(extra_class)}"><img src="{esc(image["src"])}" '
            f'alt="{esc(image["alt"])}" loading="eager" decoding="async"/>'
            f'<figcaption>{esc(caption)}{source_badges([image["source_ref"]])}</figcaption></figure>'
        )

    def render_images(self, component: dict[str, Any]) -> str:
        figures = "".join(self.image_figure(image) for image in component["images"])
        return f'<div class="evidence-grid">{figures}</div>'

    def render_evidence_compare(self, component: dict[str, Any]) -> str:
        left_label = component.get("left_label", "左侧" if self.zh else "Left")
        right_label = component.get("right_label", "右侧" if self.zh else "Right")
        return (
            '<div class="evidence-compare">'
            f'<div><p class="compare-label">{esc(left_label)}</p>{self.image_figure(component["left"], "compare-left")}</div>'
            f'<div><p class="compare-label">{esc(right_label)}</p>{self.image_figure(component["right"], "compare-right")}</div>'
            '</div>'
        )

    @staticmethod
    def render_narrative(component: dict[str, Any]) -> str:
        return '<div class="narrative">' + "".join(f'<p>{esc(text)}</p>' for text in component["paragraphs"]) + "</div>"

    def render_checklist(self, component: dict[str, Any]) -> str:
        labels = {
            "done": ("已完成", "Done"),
            "pending": ("待处理", "Pending"),
            "warning": ("警告", "Warning"),
            "blocked": ("阻塞", "Blocked"),
        }
        items: list[str] = []
        for item in component["items"]:
            detail = f'<p>{esc(item["detail"])}</p>' if item.get("detail") else ""
            status_text = labels[item["status"]][0 if self.zh else 1]
            items.append(
                f'<li class="check-{esc(item["status"])}"><span class="check-mark" aria-hidden="true"></span>'
                f'<div><strong>{esc(item["label"])}</strong>{detail}</div>'
                f'<span class="status-pill">{esc(status_text)}</span></li>'
            )
        return f'<ul class="checklist">{"".join(items)}</ul>'

    def render_component(self, component: dict[str, Any], section_id: str, index: int) -> str:
        raw_id = component.get("component_id") or f"{section_id}-component-{index + 1}"
        html_id = stable_html_id("component", raw_id)
        component_type = component["type"]
        if component_type == "kpi_cards":
            body = self.render_kpi_cards(component)
        elif component_type == "distribution":
            body = self.render_distribution(component, html_id)
        elif component_type == "line_chart":
            body = self.render_line_chart(component, html_id)
        elif component_type == "data_table":
            dataset = self.datasets[component["dataset_id"]]
            body = self.render_dataset_table(
                dataset,
                component.get("column_keys"),
                int(component["top_n"]) if "top_n" in component else None,
                self.component_title(component),
            )
        elif component_type == "radar_comparison":
            body = self.render_radar(component, html_id)
        elif component_type == "quote_cards":
            body = self.render_quotes(component)
        elif component_type == "keyword_topics":
            body = self.render_keywords(component)
        elif component_type == "summary_insights":
            body = self.render_summary(component)
        elif component_type == "swot_grid":
            body = self.render_swot(component)
        elif component_type == "evidence_image_grid":
            body = self.render_images(component)
        elif component_type == "evidence_compare":
            body = self.render_evidence_compare(component)
        elif component_type == "narrative":
            body = self.render_narrative(component)
        elif component_type == "checklist":
            body = self.render_checklist(component)
        else:
            fail("UNKNOWN_COMPONENT", "unsupported component", component_type)
        return self.component_frame(component, html_id, body)

    def render_sources(self) -> str:
        caption = "来源、覆盖状态与数据时点" if self.zh else "Sources, coverage status, and data cutoff"
        headers = (
            ("来源", "类型", "状态", "层级", "质量", "数据时点")
            if self.zh
            else ("Source", "Type", "Status", "Tier", "Quality", "Data as of")
        )
        source_values = [
            (
                source["name"],
                source["source_type"],
                source["status"],
                source["source_tier"],
                source["data_quality_grade"],
                source.get("data_as_of", source["observed_at"]),
            )
            for source in self.spec["sources"]
        ]
        data_types = ("string", "string", "string", "string", "string", "datetime")
        profiles = [
            column_width_profile(header, (values[index] for values in source_values))
            for index, header in enumerate(headers)
        ]
        layout_class = table_layout_class(len(headers), profiles)

        def source_column_classes(index: int) -> str:
            return self.table_column_classes(index, data_types[index], profiles[index])

        rows: list[str] = []
        for source, values in zip(self.spec["sources"], source_values, strict=True):
            cells: list[str] = []
            for index, value in enumerate(values):
                tag = "th" if index == 0 else "td"
                scope = ' scope="row"' if index == 0 else ""
                rendered = (
                    f'<span class="status-pill status-{esc(source["status"].lower())}">{esc(value)}</span>'
                    if index == 2
                    else esc(value)
                )
                cells.append(
                    f'<{tag}{scope} class="{source_column_classes(index)}">{rendered}</{tag}>'
                )
            rows.append(f'<tr>{"".join(cells)}</tr>')
        return (
            '<section class="report-section source-section" id="source-appendix">'
            f'<div class="section-heading"><h2>{esc("来源与证据" if self.zh else "Sources and evidence")}</h2></div>'
            '<div class="table-scroll" tabindex="0" role="region" '
            f'aria-label="{esc(caption)}"><table class="data-table {layout_class}"><caption>{esc(caption)}</caption>'
            '<thead><tr>'
            + "".join(
                f'<th scope="col" class="{source_column_classes(index)}">{esc(header)}</th>'
                for index, header in enumerate(headers)
            )
            + f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div></section>'
        )

    def render_limitations(self) -> str:
        if not self.spec["limitations"]:
            return ""
        items: list[str] = []
        for limitation in self.spec["limitations"]:
            impact = f'<p>{esc(limitation["impact"])}</p>' if limitation.get("impact") else ""
            items.append(
                f'<li class="limitation-{esc(limitation["severity"].lower())}">'
                f'<span class="status-pill">{esc(limitation["severity"])}</span>'
                f'<div><strong>{esc(limitation["detail"])}</strong>{impact}'
                f'<div>{source_badges(limitation.get("source_refs", []))}</div></div></li>'
            )
        return (
            '<section class="report-section limitation-section" id="report-limitations">'
            f'<div class="section-heading"><h2>{esc("限制与可信边界" if self.zh else "Limitations and confidence boundaries")}</h2></div>'
            f'<ul class="limitation-list">{"".join(items)}</ul></section>'
        )

    def render_sections(self) -> str:
        rendered: list[str] = []
        for section in self.spec["sections"]:
            section_id = stable_html_id("section", section["section_id"])
            summary = f'<p class="section-summary">{esc(section["summary"])}</p>' if section.get("summary") else ""
            components = "".join(
                self.render_component(component, section["section_id"], index)
                for index, component in enumerate(section["components"])
            )
            if not components:
                self.warn(f"EMPTY_SECTION:{section['section_id']}")
                continue
            rendered.append(
                f'<section class="report-section" id="{esc(section_id)}">'
                f'<div class="section-heading"><h2>{esc(section["title"])}</h2>{summary}</div>'
                f'{components}</section>'
            )
        return "".join(rendered)

    def render_blocked_body(self) -> str:
        privacy_notes = self.report["privacy"].get("notes", "")
        notes = f'<p>{esc(privacy_notes)}</p>' if privacy_notes else ""
        limitations = self.render_limitations()
        return (
            '<section class="report-section blocked-panel" id="data-quality-status">'
            f'<div class="section-heading"><h2>{esc("数据质量阻塞说明" if self.zh else "Data quality blocker")}</h2></div>'
            f'<div class="quality-summary"><p>{esc(self.report["report_edition_reason"])}</p>{notes}'
            f'<dl><div><dt>{esc("数据质量" if self.zh else "Data quality")}</dt><dd>{esc(self.report["data_quality"])}</dd></div>'
            f'<div><dt>{esc("证据强度" if self.zh else "Evidence strength")}</dt><dd>{esc(self.report["evidence_strength"])}</dd></div>'
            f'<div><dt>{esc("报告版本" if self.zh else "Report edition")}</dt><dd>{esc(self.report["report_edition"])}</dd></div></dl></div>'
            f'</section>{limitations}{self.render_sources()}'
        )

    def render_toc(self) -> str:
        if not self.spec["render"]["show_toc"]:
            return ""
        items: list[str] = []
        if self.report["status"] == "BLOCKED":
            items.append(f'<li><a href="#data-quality-status">{esc("数据质量" if self.zh else "Data quality")}</a></li>')
        else:
            for section in self.spec["sections"]:
                section_id = stable_html_id("section", section["section_id"])
                items.append(f'<li><a href="#{esc(section_id)}">{esc(section["title"])}</a></li>')
            if self.spec["limitations"]:
                items.append(f'<li><a href="#report-limitations">{esc("限制" if self.zh else "Limitations")}</a></li>')
        items.append(f'<li><a href="#source-appendix">{esc("来源" if self.zh else "Sources")}</a></li>')
        return (
            '<aside class="toc" aria-label="'
            + esc("报告目录" if self.zh else "Report contents")
            + '"><p class="toc-title">'
            + esc("报告目录" if self.zh else "Contents")
            + f'</p><ol>{"".join(items)}</ol></aside>'
        )

    def render_hero(self) -> str:
        period = self.report["period"]
        status = self.report["status"]
        mode = self.report["data_mode"]
        eyebrow = "AMAZON 业务报告" if self.zh else "AMAZON BUSINESS REPORT"
        status_text = {
            "COMPLETE": ("完整", "Complete"),
            "PARTIAL": ("部分", "Partial"),
            "BLOCKED": ("BLOCKED 阻塞", "Blocked"),
        }[status][0 if self.zh else 1]
        mode_text = ("真实数据" if self.zh else "Real data") if mode == "REAL" else ("演示数据" if self.zh else "Demo data")
        return (
            '<header class="hero"><div class="hero-grid"><div class="hero-copy">'
            f'<p class="eyebrow">{esc(eyebrow)}</p><h1>{esc(self.report["title"])}</h1>'
            f'<p class="hero-context">{esc(self.report["report_edition_reason"])}</p>'
            f'<div class="hero-badges"><span class="status-pill report-{status.lower()}">{esc(status_text)}</span>'
            f'<span class="status-pill mode-{mode.lower()}">{esc(mode_text)}</span>'
            f'<span class="status-pill">{esc(self.report["marketplace"])}</span></div></div>'
            '<div class="hero-facts"><dl>'
            f'<div><dt>{esc("周期" if self.zh else "Period")}</dt><dd>{esc(period["label"])}</dd></div>'
            f'<div><dt>{esc("数据时点" if self.zh else "Data as of")}</dt><dd>{esc(period.get("data_as_of", period.get("end", "未提供" if self.zh else "Not supplied")))}</dd></div>'
            f'<div><dt>{esc("质量 / 证据" if self.zh else "Quality / evidence")}</dt><dd>{esc(self.report["data_quality"])} / {esc(self.report["evidence_strength"])}</dd></div>'
            f'<div><dt>{esc("时区 / 币种" if self.zh else "Timezone / currency")}</dt><dd>{esc(self.report["timezone"])} / {esc(self.report["currency"])}</dd></div>'
            '</dl></div></div></header>'
        )

    def render_document(self, semantic_hash: str) -> str:
        nonce = semantic_hash[:24]
        theme = self.spec["render"]["theme"]
        demo_banner = ""
        if self.report["data_mode"] == "DEMO":
            demo_banner = (
                f'<div class="demo-banner" role="note">{esc("DEMO 演示数据，不可用于真实业务决策" if self.zh else "DEMO data, not for live business decisions")}</div>'
            )
        partial_banner = ""
        if self.report["status"] == "PARTIAL":
            partial_banner = (
                f'<div class="partial-banner" role="status">{esc("PARTIAL 部分数据：缺失与冲突值未补零" if self.zh else "PARTIAL data: missing and conflicting values are not replaced with zero")}</div>'
            )
        if self.report["status"] == "BLOCKED":
            body = self.render_blocked_body()
        else:
            body = self.render_sections() + self.render_limitations() + self.render_sources()
        demo_closing = ""
        if self.report["data_mode"] == "DEMO":
            demo_closing = (
                '<section class="demo-closing" id="demo-disclaimer"><strong>DEMO</strong>'
                f'<p>{esc("本报告仅用于课程演示与模板验证，不构成真实业务结论。" if self.zh else "This report is for training and template validation only; it is not a live business conclusion.")}</p></section>'
            )
        toc = self.render_toc()
        layout_class = "with-toc" if toc else "without-toc"
        theme_label = "主题" if self.zh else "Theme"
        skip_label = "跳到报告正文" if self.zh else "Skip to report content"
        back_to_top_label = "回到顶部" if self.zh else "Back to top"
        footer_text = "本地离线渲染" if self.zh else "Rendered locally and offline"
        csp = (
            "default-src 'none'; "
            f"style-src 'nonce-{nonce}'; style-src-attr 'none'; "
            f"script-src 'nonce-{nonce}'; script-src-attr 'none'; "
            "img-src data:; font-src 'none'; connect-src 'none'; media-src 'none'; "
            "object-src 'none'; frame-src 'none'; child-src 'none'; worker-src 'none'; "
            "base-uri 'none'; form-action 'none'; manifest-src 'none'"
        )
        return (
            '<!doctype html><html lang="'
            + esc(self.report["locale"])
            + f'" data-theme="{esc(theme)}"><head><meta charset="utf-8">'
            + '<meta name="viewport" content="width=device-width,initial-scale=1,minimum-scale=1,shrink-to-fit=no,viewport-fit=cover">'
            + f'<meta http-equiv="Content-Security-Policy" content="{html.escape(csp, quote=False)}">'
            + f'<title>{esc(self.report["title"])}</title><style nonce="{nonce}">{report_css()}</style></head>'
            + f'<body id="report-top" class="family-{esc(self.family)}">'
            + f'<a class="skip-link" href="#report-main">{esc(skip_label)}</a>{demo_banner}'
            + f'<a class="back-to-top" id="back-to-top" href="#report-top" aria-label="{esc(back_to_top_label)}">'
            + f'<span aria-hidden="true">↑</span><span class="sr-only">{esc(back_to_top_label)}</span></a>'
            + '<div class="topbar"><div class="brand-lockup"><span class="brand-mark">a</span><span>Amazon Report</span></div>'
            + f'<button class="theme-toggle" type="button" id="theme-toggle" aria-label="{esc(theme_label)}">'
            + f'<span aria-hidden="true">◐</span><span id="theme-label">{esc(theme_label)}</span></button></div>'
            + f'<div class="report-shell">{self.render_hero()}{partial_banner}'
            + f'<div class="page-layout {layout_class}">{toc}<main id="report-main" tabindex="-1">{body}{demo_closing}</main></div>'
            + f'<footer><span>{esc(footer_text)}</span><span>{esc(PROTOCOL)} / {esc(TEMPLATE_VERSION)}</span></footer></div>'
            + f'<script nonce="{nonce}">{theme_script(self.zh)}</script></body></html>'
        )


def progress_css() -> str:
    return "".join(f".pct-{value}{{width:{value}%;}}" for value in range(101))


def adaptive_table_width_css() -> str:
    return "".join(
        f".table-col-width-{width_em}{{width:{width_em}em;min-width:{width_em}em}}"
        for width_em in range(
            MIN_ADAPTIVE_COLUMN_WIDTH_EM,
            MAX_ADAPTIVE_COLUMN_WIDTH_EM + ADAPTIVE_COLUMN_WIDTH_STEP_EM,
            ADAPTIVE_COLUMN_WIDTH_STEP_EM,
        )
    )


def report_css() -> str:
    """Return the fixed visual system; no upstream value is interpolated into CSS."""

    return r"""

:root{color-scheme:light dark;--accent:#ff9900;--radius-content:12px;--radius-control:8px;--radius-pill:999px;--bg:#f4f5f7;--surface:#ffffff;--surface-soft:#f8fafc;--text:#172033;--muted:#667085;--line:#dfe3e8;--line-strong:#c9d0d8;--info:#2563eb;--good:#15803d;--warning:#b45309;--critical:#b91c1c;--shadow:0 12px 36px rgba(15,23,42,.08);--font:Inter,"Segoe UI","PingFang SC","Microsoft YaHei",Arial,sans-serif}
*{box-sizing:border-box}html{max-width:100%;overflow-x:hidden;scroll-behavior:smooth;background:var(--bg)}body{max-width:100%;overflow-x:hidden;margin:0;background:var(--bg);color:var(--text);font-family:var(--font);font-size:15px;line-height:1.65;overflow-wrap:anywhere}@supports(overflow-x:clip){html,body{overflow-x:clip}}button,a{font:inherit}a{color:var(--info);text-underline-offset:3px}a:focus-visible,button:focus-visible,[tabindex="0"]:focus-visible{outline:3px solid var(--accent);outline-offset:3px}.sr-only{position:absolute!important;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}.skip-link{position:fixed;z-index:50;left:16px;top:12px;padding:8px 12px;border-radius:var(--radius-control);background:var(--text);color:var(--surface);transform:translateY(-160%)}.skip-link:focus{transform:none}.demo-banner{position:relative;z-index:5;padding:8px 20px;text-align:center;background:#7c2d12;color:#fff;font-weight:800;letter-spacing:.04em}.partial-banner{margin:18px 0 0;padding:11px 14px;border:1px solid #f59e0b;border-radius:var(--radius-control);background:#fffbeb;color:#78350f;font-weight:700}.topbar{height:58px;display:flex;align-items:center;justify-content:space-between;padding:0 max(20px,calc((100vw - 1380px)/2));border-bottom:1px solid var(--line);background:var(--surface);position:sticky;top:0;z-index:20}.brand-lockup{display:flex;align-items:center;gap:9px;font-weight:800}.brand-mark{display:grid;place-items:center;width:30px;height:30px;border-radius:var(--radius-control);background:var(--accent);color:#111827;font:900 22px/1 Georgia,serif}.theme-toggle{display:flex;align-items:center;gap:7px;border:1px solid var(--line-strong);border-radius:var(--radius-control);padding:7px 11px;background:var(--surface);color:var(--text);cursor:pointer}.report-shell{width:min(1380px,calc(100% - 40px));margin:0 auto}.hero{padding:52px 0 32px;border-bottom:1px solid var(--line)}.hero-grid{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(260px,.55fr);gap:clamp(32px,6vw,88px);align-items:end}.eyebrow{margin:0 0 14px;color:#9a5b00;font-size:12px;font-weight:850;letter-spacing:.14em}.hero h1{max-width:920px;margin:0;font-size:clamp(40px,5vw,56px);line-height:1.08;letter-spacing:-.035em}.hero-context{max-width:780px;margin:20px 0 0;color:var(--muted);font-size:17px}.hero-badges{display:flex;flex-wrap:wrap;gap:8px;margin-top:24px}.status-pill{display:inline-flex;align-items:center;width:max-content;max-width:100%;padding:3px 9px;border:1px solid var(--line-strong);border-radius:var(--radius-pill);background:var(--surface-soft);color:var(--text);font-size:12px;font-weight:750}.report-complete,.status-available,.mode-real{border-color:#86efac;background:#f0fdf4;color:#166534}.report-partial,.status-partial,.status-conflict{border-color:#fcd34d;background:#fffbeb;color:#92400e}.report-blocked,.status-unavailable{border-color:#fca5a5;background:#fef2f2;color:#991b1b}.mode-demo{border-color:#fdba74;background:#fff7ed;color:#9a3412}.hero-facts{border-left:4px solid var(--accent);padding:4px 0 4px 24px}.hero-facts dl,.quality-summary dl{margin:0}.hero-facts dl div,.quality-summary dl div{display:grid;grid-template-columns:minmax(90px,.8fr) minmax(120px,1.2fr);gap:16px;padding:9px 0;border-bottom:1px solid var(--line)}dt{color:var(--muted);font-size:12px;font-weight:750;text-transform:uppercase;letter-spacing:.04em}dd{margin:0;font-weight:700}.page-layout{display:grid;gap:42px;padding:34px 0 70px}.page-layout.with-toc{grid-template-columns:210px minmax(0,1fr)}.page-layout.without-toc{grid-template-columns:minmax(0,1fr)}.toc{position:sticky;top:82px;align-self:start;max-height:calc(100vh - 100px);overflow:auto;padding-right:10px}.toc-title{margin:0 0 12px;color:var(--muted);font-size:12px;font-weight:850;letter-spacing:.08em}.toc ol{display:grid;gap:6px;margin:0;padding:0;list-style:none}.toc a{display:block;padding:6px 9px;border-left:2px solid var(--line);color:var(--muted);text-decoration:none}.toc a:hover{border-color:var(--accent);color:var(--text)}main{min-width:0}.report-section{scroll-margin-top:82px;padding:0 0 52px;margin:0 0 52px;border-bottom:1px solid var(--line)}.report-section:last-child{margin-bottom:0}.section-heading{margin-bottom:26px}.section-heading h2{margin:0;font-size:clamp(28px,3.2vw,36px);line-height:1.2;letter-spacing:-.02em}.section-summary{max-width:860px;margin:10px 0 0;color:var(--muted);font-size:16px}.report-component{margin:30px 0}.report-component>h3{margin:0 0 16px;font-size:20px;line-height:1.3}.report-component+.report-component{margin-top:44px}.kpi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}.kpi-card{min-width:0;padding:18px;border:1px solid var(--line);border-radius:var(--radius-content);background:var(--surface)}.kpi-card.status-missing,.kpi-card.status-conflict{border-color:#f6c2c2}.kpi-label{margin:0;color:var(--muted);font-size:13px;font-weight:700}.kpi-value{margin:8px 0 10px;font-size:clamp(27px,3vw,38px);font-weight:850;line-height:1.05;letter-spacing:-.025em}.kpi-meta{display:flex;flex-wrap:wrap;gap:6px}.value-status{font-size:12px;font-weight:700;color:var(--muted)}.metric-detail{margin:12px 0 0;color:var(--muted);font-size:13px}.source-ref{display:inline-flex;margin:2px 0 2px 5px;padding:1px 7px;border:1px solid var(--line);border-radius:var(--radius-pill);color:var(--muted);font-size:10px;font-weight:700}.summary-box{padding:18px 20px;border-left:5px solid var(--accent);border-radius:0 var(--radius-content) var(--radius-content) 0;background:var(--surface)}.summary-box p{margin:0;font-size:17px;font-weight:700}.demo-inline{margin-top:10px!important;color:#9a3412!important;font-size:13px!important}.insight-list,.limitation-list,.checklist{display:grid;gap:10px;margin:16px 0 0;padding:0;list-style:none}.insight-list li,.limitation-list li,.checklist li{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:16px;align-items:start;padding:14px 16px;border:1px solid var(--line);border-radius:var(--radius-control);background:var(--surface)}.insight-list p,.limitation-list p,.checklist p{margin:4px 0 0;color:var(--muted)}.insight-warning,.limitation-warning{border-left:4px solid var(--warning)!important}.insight-critical,.limitation-error,.limitation-blocker{border-left:4px solid var(--critical)!important}.insight-positive{border-left:4px solid var(--good)!important}.insight-info,.limitation-info{border-left:4px solid var(--info)!important}.table-scroll{max-width:100%;overflow:auto;border:1px solid var(--line);border-radius:var(--radius-content);background:var(--surface)}table{width:100%;border-collapse:collapse;min-width:620px}caption{padding:12px 14px;text-align:left;color:var(--muted);font-size:12px;font-weight:750}th,td{padding:11px 13px;border-top:1px solid var(--line);text-align:left;vertical-align:top}thead th{position:sticky;top:0;background:var(--surface-soft);color:var(--muted);font-size:12px;letter-spacing:.025em}tbody th{font-weight:700}.cell-missing,.cell-conflict,.cell-no_access,.cell-collection_failure{color:var(--critical);font-style:italic}.dataset-sources{margin-top:7px}.chart-svg{display:block;width:100%;height:auto;max-height:430px;overflow:visible}.chart-svg text{fill:var(--text);font-family:var(--font)}.svg-grid,.radar-ring,.radar-axis{fill:none;stroke:var(--line-strong);stroke-width:1}.svg-axis-label,.radar-label,.svg-total-label{font-size:12px;fill:var(--muted)!important}.svg-total-value{font-size:24px;font-weight:850}.chart-legend{display:flex;flex-wrap:wrap;gap:14px;margin:0 0 8px}.chart-legend-item,.distribution-label{display:flex;align-items:center;gap:7px}.legend-swatch{display:inline-block;width:14px;height:5px;border-radius:var(--radius-pill);background:#64748b}.swatch-0{background:#ff9900}.swatch-1{background:#334155}.swatch-2{background:#64748b}.swatch-3{background:#94a3b8}.swatch-4{background:#475569}.swatch-5{background:#78716c}.swatch-6{background:#a8a29e}.swatch-7{background:#cbd5e1}.chart-data{margin-top:12px}.chart-data summary{cursor:pointer;color:var(--info);font-weight:700}.chart-data .table-scroll{margin-top:10px}.chart-note,.quality-note{margin:10px 0;color:var(--muted);font-size:12px}.distribution-layout{display:grid;grid-template-columns:minmax(240px,.8fr) minmax(280px,1.2fr);gap:28px;align-items:center}.distribution-list{display:grid;gap:16px}.distribution-row small{display:block;margin-top:4px;color:var(--muted)}.distribution-label strong{margin-left:auto}.progress-track{height:8px;margin-top:6px;overflow:hidden;border-radius:var(--radius-pill);background:var(--line)}.progress-fill{display:block;height:100%;border-radius:inherit;background:var(--accent)}.radar-layout{display:grid;grid-template-columns:minmax(320px,.85fr) minmax(400px,1.15fr);gap:24px;align-items:start}.quote-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}.quote-card{margin:0;padding:18px;border-left:4px solid var(--line-strong);border-radius:0 var(--radius-content) var(--radius-content) 0;background:var(--surface)}.quote-card blockquote{margin:0;font-size:16px}.quote-card figcaption{margin-top:12px;color:var(--muted);font-size:12px}.sentiment-negative{border-left-color:var(--critical)}.sentiment-positive{border-left-color:var(--good)}.sentiment-mixed{border-left-color:var(--warning)}.tag-cloud{display:flex;flex-wrap:wrap;gap:9px;align-items:center;margin-bottom:18px;padding:18px;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}.topic-tag{display:inline-flex;align-items:baseline;gap:6px;padding:5px 10px;border:1px solid var(--line);border-radius:var(--radius-pill);background:var(--surface)}.topic-tag small{color:var(--muted);font-size:10px}.tag-size-1{font-size:12px}.tag-size-2{font-size:14px}.tag-size-3{font-size:16px}.tag-size-4{font-size:19px}.tag-size-5{font-size:23px;font-weight:800}.swot-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.swot-quadrant{padding:18px;border:1px solid var(--line);border-radius:var(--radius-content);background:var(--surface)}.swot-quadrant h4{margin:0 0 10px;font-size:18px}.swot-quadrant ul{margin:0;padding-left:20px}.swot-quadrant li+li{margin-top:8px}.swot-strengths{border-top:4px solid var(--good)}.swot-weaknesses{border-top:4px solid var(--critical)}.swot-opportunities{border-top:4px solid var(--info)}.swot-threats{border-top:4px solid var(--warning)}.evidence-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}.evidence-figure{margin:0;border:1px solid var(--line);border-radius:var(--radius-content);overflow:hidden;background:var(--surface)}.evidence-figure img{display:block;width:100%;max-height:520px;object-fit:contain;background:var(--surface-soft)}.evidence-figure figcaption{padding:11px 13px;color:var(--muted);font-size:12px}.evidence-compare{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.compare-label{margin:0 0 8px;font-weight:800}.narrative{max-width:900px}.narrative p{margin:0 0 1em;font-size:16px}.checklist li{grid-template-columns:18px minmax(0,1fr) auto}.check-mark{width:15px;height:15px;margin-top:4px;border:2px solid var(--line-strong);border-radius:4px}.check-done .check-mark{border-color:var(--good);background:var(--good)}.check-warning .check-mark{border-color:var(--warning);background:var(--warning)}.check-blocked .check-mark{border-color:var(--critical);background:var(--critical)}.quality-summary{padding:20px;border:1px solid var(--critical);border-radius:var(--radius-content);background:var(--surface)}.quality-summary>p{font-size:17px;font-weight:700}.blocked-panel{border-bottom-color:var(--critical)}.demo-closing{margin-top:30px;padding:18px;border:2px solid #c2410c;border-radius:var(--radius-content);background:#fff7ed;color:#7c2d12}.demo-closing strong{font-size:20px}.demo-closing p{margin:4px 0 0}footer{display:flex;justify-content:space-between;gap:20px;padding:22px 0 38px;border-top:1px solid var(--line);color:var(--muted);font-size:12px}.family-knowledge .report-shell{width:min(1120px,calc(100% - 40px))}.family-knowledge .narrative{max-width:760px}.family-insight .hero-facts{border-left-color:var(--info)}

table :is(th,td){word-break:normal;line-break:strict;overflow-wrap:break-word}
.table-scroll{width:100%;min-width:0;overflow-x:auto;overflow-y:hidden;overscroll-behavior-inline:contain;scrollbar-gutter:stable;scrollbar-color:var(--line-strong) var(--surface-soft);contain:inline-size paint}
.table-layout-wide,.table-layout-dense{table-layout:auto}.table-layout-wide{min-width:1480px}.table-layout-dense{min-width:2780px}.table-col-numeric{width:1%;white-space:nowrap;font-variant-numeric:tabular-nums;text-align:right}.table-col-compact{width:1%;white-space:nowrap}.table-col-primary,.table-col-text{white-space:normal;overflow-wrap:break-word;word-break:normal}.table-col-short{width:1%;white-space:nowrap;overflow-wrap:normal;word-break:keep-all}.table-col-ordinal{width:1%;white-space:nowrap;text-align:center;font-variant-numeric:tabular-nums}.table-col-expanded{white-space:normal;overflow-wrap:break-word;word-break:normal}.table-col-capped{max-width:48em;white-space:normal!important;overflow-wrap:anywhere!important;word-break:normal!important}.table-cell-priority{width:1%;white-space:nowrap!important;overflow-wrap:normal!important;word-break:keep-all!important}
.back-to-top{position:fixed;z-index:30;right:max(16px,env(safe-area-inset-right));bottom:max(16px,env(safe-area-inset-bottom));display:grid;place-items:center;width:44px;height:44px;border:1px solid var(--line-strong);border-radius:var(--radius-control);background:var(--surface);color:var(--text);box-shadow:var(--shadow);font-size:20px;font-weight:800;line-height:1;text-decoration:none;transition:opacity .18s ease,transform .18s ease,visibility .18s ease}.back-to-top:hover{border-color:var(--accent);background:var(--surface-soft)}.back-to-top[data-enhanced="true"]{opacity:0;visibility:hidden;pointer-events:none;transform:translateY(8px)}.back-to-top[data-enhanced="true"].is-visible{opacity:1;visibility:visible;pointer-events:auto;transform:none}
""" + adaptive_table_width_css() + progress_css() + r"""
@media (prefers-color-scheme: dark){html[data-theme="system"]{--bg:#0f141c;--surface:#171e29;--surface-soft:#1d2633;--text:#eef2f7;--muted:#a9b3c2;--line:#303b49;--line-strong:#465366;--shadow:none}}
html[data-theme="dark"]{--bg:#0f141c;--surface:#171e29;--surface-soft:#1d2633;--text:#eef2f7;--muted:#a9b3c2;--line:#303b49;--line-strong:#465366;--shadow:none}html[data-theme="dark"] .partial-banner{background:#3b2a12;color:#fde68a}html[data-theme="dark"] .demo-closing{background:#3a2015;color:#fed7aa}
@media (max-width:980px){.hero-grid,.page-layout.with-toc,.radar-layout{grid-template-columns:minmax(0,1fr)}.toc{position:static;max-height:none;display:none}.hero-facts{max-width:620px}.report-shell{width:min(100% - 28px,1380px)}}
@media (max-width:680px){body{font-size:14px}.topbar{height:54px;padding:0 14px}.brand-lockup span:last-child{display:none}.hero{padding:34px 0 24px}.hero h1{font-size:clamp(34px,11vw,46px)}.hero-grid{gap:24px}.hero-facts{padding-left:16px}.page-layout{padding-top:24px}.report-section{padding-bottom:36px;margin-bottom:36px}.distribution-layout,.swot-grid,.evidence-compare{grid-template-columns:minmax(0,1fr)}.quote-grid,.evidence-grid,.kpi-grid{grid-template-columns:minmax(0,1fr)}.insight-list li,.limitation-list li{grid-template-columns:minmax(0,1fr)}.checklist li{grid-template-columns:18px minmax(0,1fr)}.checklist .status-pill{grid-column:2}.radar-layout>div{min-width:0}footer{flex-direction:column}.demo-banner{font-size:12px}}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}*{transition:none!important;animation:none!important}.back-to-top{transition:none!important}}
@media print{:root,html[data-theme="dark"],html[data-theme="system"]{color-scheme:light;--bg:#fff;--surface:#fff;--surface-soft:#f6f7f9;--text:#111827;--muted:#4b5563;--line:#d1d5db;--line-strong:#9ca3af;--info:#1d4ed8;--good:#166534;--warning:#92400e;--critical:#991b1b;--shadow:none}.topbar,.skip-link,.toc,.theme-toggle,.back-to-top,.chart-data summary{display:none!important}.demo-banner{position:static!important;display:block!important;color:#7c2d12!important;background:#fff7ed!important;border:2px solid #c2410c}.partial-banner{color:#78350f!important;background:#fffbeb!important}.report-shell{width:100%;margin:0}.hero{padding:20px 0}.page-layout,.page-layout.with-toc{display:block;padding:20px 0}.report-section{break-inside:auto;page-break-inside:auto}.report-component,.kpi-card,.quote-card,.swot-quadrant,.evidence-figure,.summary-box{break-inside:avoid;page-break-inside:avoid}.chart-data[open],.chart-data{display:block}.chart-data:not([open])>*:not(summary){display:block}.table-scroll{overflow:visible}.data-table,.comparison-table,.chart-summary-table{min-width:0;font-size:10px}.evidence-figure img{max-height:360px}.demo-closing{display:block!important}footer{padding-bottom:0}@page{size:auto;margin:12mm}}
@media print{table.table-layout-standard,table.table-layout-wide,table.table-layout-dense{min-width:0;table-layout:auto}table.table-layout-standard :is(th,td),table.table-layout-wide :is(th,td),table.table-layout-dense :is(th,td){width:auto!important;min-width:0!important;max-width:none!important;white-space:normal!important;overflow-wrap:anywhere!important;word-break:normal!important;text-align:left}}
"""


def theme_script(zh: bool) -> str:
    labels = (
        {"system": "跟随系统", "light": "浅色", "dark": "深色"}
        if zh
        else {"system": "System", "light": "Light", "dark": "Dark"}
    )
    labels_json = json.dumps(labels, ensure_ascii=False, separators=(",", ":"))
    return (
        "(()=>{'use strict';const root=document.documentElement;const button=document.getElementById('theme-toggle');"
        "const label=document.getElementById('theme-label');const order=['system','light','dark'];"
        f"const labels={labels_json};"
        "const render=()=>{const value=root.dataset.theme||'system';label.textContent=labels[value];"
        "button.setAttribute('aria-label',labels[value]);};"
        "button.addEventListener('click',()=>{const current=root.dataset.theme||'system';"
        "root.dataset.theme=order[(order.indexOf(current)+1)%order.length];render();});render();})();"
        "(()=>{'use strict';const link=document.getElementById('back-to-top');const hero=document.querySelector('.hero');"
        "if(!link||!hero||!('IntersectionObserver' in window))return;link.dataset.enhanced='true';"
        "const observer=new IntersectionObserver(([entry])=>{link.classList.toggle('is-visible',!entry.isIntersecting);},"
        "{rootMargin:'-58px 0px 0px 0px',threshold:0});observer.observe(hero);})();"
    )


def validate_html_document(document: str) -> dict[str, Any]:
    lowered = document.lower()
    h1_count = len(re.findall(r"<h1\b", lowered))
    ids = re.findall(r'\bid=["\']([^"\']+)["\']', document)
    internal_fragments = re.findall(r'\bhref=["\']#([^"\']+)["\']', document)
    tags = re.findall(r"<[^>]+>", document, re.DOTALL)
    event_attributes = [tag for tag in tags if re.search(r"\son[a-z]+\s*=", tag, re.IGNORECASE)]
    external_resources = [
        tag
        for tag in tags
        if re.match(r"<\s*(?:script|link|img|source|iframe|video|audio)\b", tag, re.IGNORECASE)
        and re.search(r'''\b(?:src|href)\s*=\s*["'](?:https?:)?//''', tag, re.IGNORECASE)
    ]
    tables = re.findall(r"<table\b[\s\S]*?</table>", document, re.IGNORECASE)
    svgs = re.findall(r"<svg\b[\s\S]*?</svg>", document, re.IGNORECASE)
    images = [tag for tag in tags if re.match(r"<\s*img\b", tag, re.IGNORECASE)]
    checks = {
        "schema_valid": True,
        "privacy_valid": True,
        "offline_valid": not external_resources,
        "csp_present": "content-security-policy" in lowered and "connect-src" in lowered,
        "no_unresolved_placeholders": "{{" not in document and "{%" not in document,
        "unique_h1": h1_count == 1,
        "unique_ids": len(ids) == len(set(ids)),
        "internal_links_valid": all(fragment in set(ids) for fragment in internal_fragments),
        "print_style_present": "@media print" in lowered,
        "tables_accessible": all(
            "<caption" in table.lower() and re.search(r"<th\b[^>]*\bscope=", table, re.IGNORECASE)
            for table in tables
        ),
        "charts_accessible": all("<title" in svg.lower() and "<desc" in svg.lower() for svg in svgs),
        "images_accessible": all(
            re.search(r'''\balt=["'][^"']+["']''', tag, re.IGNORECASE) for tag in images
        ),
        "no_event_handlers": not event_attributes,
        "readback_verified": True,
    }
    failed = sorted(key for key, passed in checks.items() if passed is not True)
    if failed:
        fail("HTML_VALIDATION_FAILED", f"generated HTML failed checks: {', '.join(failed)}", "output")
    return checks


def parse_json_bytes(payload: bytes) -> dict[str, Any]:
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        fail("SPEC_ENCODING_ERROR", "spec must be UTF-8 JSON", "spec")

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                fail("JSON_DUPLICATE_KEY", f"duplicate JSON key: {key}", "spec")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        fail("JSON_NONFINITE_NUMBER", f"non-finite JSON number: {value}", "spec")

    try:
        parsed = json.loads(
            text,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_constant,
        )
    except RenderError:
        raise
    except json.JSONDecodeError as exc:
        fail("SPEC_JSON_ERROR", f"invalid JSON at line {exc.lineno}, column {exc.colno}", "spec")
    return require_dict(parsed, "$")


def write_staging_file(directory: Path, prefix: str, payload: bytes) -> Path:
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=prefix,
            suffix=".tmp",
            dir=directory,
            delete=False,
        ) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            return Path(handle.name)
    except OSError:
        fail("STAGING_WRITE_ERROR", "could not write staging artifact", "output")


def atomic_commit_pair(
    output_path: Path,
    receipt_path: Path,
    html_payload: bytes,
    receipt_payload: bytes,
    overwrite: bool,
) -> None:
    parent = output_path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        fail("OUTPUT_DIRECTORY_ERROR", "could not create output directory", "--output")
    if not overwrite and (output_path.exists() or receipt_path.exists()):
        fail("OUTPUT_EXISTS", "output or receipt already exists; use --overwrite to replace", "--output")

    html_stage = write_staging_file(parent, f".{output_path.name}.", html_payload)
    receipt_stage = write_staging_file(parent, f".{receipt_path.name}.", receipt_payload)
    backups: dict[Path, Path] = {}
    committed: list[Path] = []
    try:
        if html_stage.read_bytes() != html_payload or receipt_stage.read_bytes() != receipt_payload:
            fail("STAGING_READBACK_ERROR", "staging artifact readback mismatch", "output")
        if not overwrite and (output_path.exists() or receipt_path.exists()):
            fail("OUTPUT_EXISTS", "output appeared during render; no artifact was replaced", "--output")
        if overwrite:
            for target in (output_path, receipt_path):
                if target.exists():
                    backup = target.with_name(f".{target.name}.backup-{os.getpid()}-{len(backups)}")
                    if backup.exists():
                        fail("BACKUP_CONFLICT", "transaction backup path already exists", "output")
                    os.replace(target, backup)
                    backups[target] = backup
        mover = os.replace if overwrite else os.rename
        mover(html_stage, output_path)
        committed.append(output_path)
        mover(receipt_stage, receipt_path)
        committed.append(receipt_path)
        if output_path.read_bytes() != html_payload or receipt_path.read_bytes() != receipt_payload:
            raise OSError("committed readback mismatch")
    except RenderError:
        for target in committed:
            try:
                target.unlink(missing_ok=True)
            except OSError:
                pass
        for target, backup in backups.items():
            if backup.exists():
                os.replace(backup, target)
        raise
    except OSError:
        for target in committed:
            try:
                target.unlink(missing_ok=True)
            except OSError:
                pass
        for target, backup in backups.items():
            try:
                if backup.exists():
                    os.replace(backup, target)
            except OSError:
                pass
        fail("ATOMIC_COMMIT_ERROR", "artifact commit or readback failed", "output")
    finally:
        for staging in (html_stage, receipt_stage):
            try:
                staging.unlink(missing_ok=True)
            except OSError:
                pass
    for backup in backups.values():
        try:
            backup.unlink(missing_ok=True)
        except OSError:
            fail("BACKUP_CLEANUP_ERROR", "artifacts committed but transaction backup cleanup failed", "output")


def component_type_list(spec: dict[str, Any]) -> list[str]:
    return sorted(
        {
            component["type"]
            for section in spec["sections"]
            for component in section["components"]
        }
    )


def execute_render(
    *,
    spec_path: Path,
    output_path: Path,
    family_override: str,
    validate_only: bool,
    overwrite: bool,
    receipt_path_mode: str = "absolute",
) -> dict[str, object]:
    if receipt_path_mode not in {"absolute", "relative"}:
        fail("CLI_ARGUMENT_ERROR", "invalid receipt path mode", "--receipt-path-mode")
    if family_override not in FAMILIES:
        fail("CLI_ARGUMENT_ERROR", "invalid family override", "--family")
    spec_file = spec_path.expanduser().resolve()
    if not spec_file.is_file():
        fail("SPEC_NOT_FOUND", "spec file does not exist", "--spec")
    try:
        raw_payload = spec_file.read_bytes()
    except OSError:
        fail("SPEC_READ_ERROR", "spec file could not be read", "--spec")
    if len(raw_payload) > MAX_SPEC_BYTES:
        fail("SPEC_TOO_LARGE", "spec exceeds 25 MiB", "--spec")
    spec = validate_spec(parse_json_bytes(raw_payload))
    semantic_hash = sha256_bytes(canonical_bytes(spec))
    raw_hash = sha256_bytes(raw_payload)
    family, family_warnings = select_family(spec, family_override)
    prepared, image_hashes, image_bytes = prepare_images(spec, spec_file.parent)

    target = output_path.expanduser().resolve()
    if target.suffix.lower() != ".html":
        fail("OUTPUT_EXTENSION_ERROR", "output path must end in .html", "--output")
    receipt_path = target.with_suffix(".render-receipt.json")
    if not validate_only and not overwrite and (target.exists() or receipt_path.exists()):
        fail("OUTPUT_EXISTS", "output or receipt already exists; use --overwrite to replace", "--output")

    renderer = ReportRenderer(prepared, family)
    document = renderer.render_document(semantic_hash)
    validation = validate_html_document(document)
    validation.update(
        {
            "image_count": len(image_hashes),
            "image_bytes": image_bytes,
            "component_types": component_type_list(spec),
        }
    )
    warnings = family_warnings + renderer.warnings
    render_plan = {
        "template_version": TEMPLATE_VERSION,
        "family": family,
        "theme": spec["render"]["theme"],
        "show_toc": spec["render"]["show_toc"],
        "component_types": [
            component["type"]
            for section in spec["sections"]
            for component in section["components"]
        ],
    }
    plan_fingerprint = sha256_bytes(canonical_bytes(render_plan))
    state_hash = sha256_bytes(
        canonical_bytes(
            {
                "input_semantic_hash": semantic_hash,
                "render_plan_fingerprint": plan_fingerprint,
                "image_hashes": image_hashes,
            }
        )
    )
    html_payload = document.encode("utf-8")
    html_hash = sha256_bytes(html_payload)
    if validate_only:
        return {
            "ok": True,
            "status": "VALIDATED",
            "report_status": spec["report"]["status"],
            "family": family,
            "input_semantic_hash": semantic_hash,
            "render_plan_fingerprint": plan_fingerprint,
            "warnings": warnings,
            "validation": validation,
        }

    period = spec["report"]["period"]
    receipt: dict[str, Any] = {
        "protocol": RECEIPT_PROTOCOL,
        "ok": True,
        "status": spec["report"]["status"],
        "report_id": spec["report"]["report_id"],
        "report_type": spec["report"]["report_type"],
        "data_mode": spec["report"]["data_mode"],
        "family": family,
        "template_version": TEMPLATE_VERSION,
        "input_semantic_hash": semantic_hash,
        "source_spec_raw_hash": raw_hash,
        "render_plan_fingerprint": plan_fingerprint,
        "render_state_hash": state_hash,
        "html_hash": html_hash,
        "html_bytes": len(html_payload),
        "output_path": target.name if receipt_path_mode == "relative" else str(target),
        "receipt_path": receipt_path.name if receipt_path_mode == "relative" else str(receipt_path),
        "data_as_of": period.get("data_as_of", period.get("end")),
        "cutoff": period.get("end"),
        "image_hashes": image_hashes,
        "warnings": warnings,
        "validation": validation,
    }
    if receipt_path_mode == "relative":
        # 相对路径在完整目录搬迁后仍可复核，不改变实际写入目标或覆盖权限。
        receipt["artifact_path_base"] = "receipt_directory"
    receipt["manifest_hash"] = sha256_bytes(canonical_bytes(receipt))
    receipt_payload = (json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    atomic_commit_pair(target, receipt_path, html_payload, receipt_payload, overwrite)
    if sha256_bytes(target.read_bytes()) != html_hash:
        fail("FINAL_READBACK_ERROR", "final HTML hash mismatch after commit", "output")
    committed_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if committed_receipt.get("manifest_hash") != receipt["manifest_hash"]:
        fail("FINAL_READBACK_ERROR", "final receipt readback mismatch after commit", "receipt")
    return {
        "ok": True,
        "status": "RENDERED",
        "report_status": spec["report"]["status"],
        "family": family,
        "output_path": str(target),
        "receipt_path": str(receipt_path),
        "input_semantic_hash": semantic_hash,
        "html_hash": html_hash,
        "warnings": warnings,
    }
