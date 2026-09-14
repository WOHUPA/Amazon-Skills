from __future__ import annotations

import copy
import html
import json
import re
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
CLI_PATH = SKILL_ROOT / "scripts" / "render_report.py"
FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"
GOLDEN_CASES_PATH = SKILL_ROOT / "evals" / "golden-cases.json"
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from report_renderer import column_width_profile, visible_width_units


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


class InternalLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.internal_links: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if values.get("id"):
            self.ids.append(values["id"])
        if tag == "a" and values.get("href", "").startswith("#"):
            self.internal_links.append(values)


class RenderReportIntegrationTests(unittest.TestCase):
    maxDiff = 3000

    def test_relative_receipt_survives_pair_relocation_without_rewriting(self) -> None:
        import hashlib
        spec = load_json(FIXTURE_ROOT / "voc-insight.json")
        result, html_path, receipt_path, temporary = self._run(spec, extra_args=["--receipt-path-mode", "relative"])
        try:
            self.assertEqual(result.returncode, 0, result.stdout)
            receipt = load_json(receipt_path)
            self.assertEqual(receipt["artifact_path_base"], "receipt_directory")
            self.assertEqual(receipt["output_path"], html_path.name)
            destination = html_path.parent / "relocated"
            destination.mkdir()
            html_path.rename(destination / html_path.name)
            receipt_path.rename(destination / receipt_path.name)
            self.assertEqual(receipt["html_hash"], hashlib.sha256((destination / receipt["output_path"]).read_bytes()).hexdigest())
            self.assertEqual(load_json(destination / receipt["receipt_path"]), receipt)
        finally:
            temporary.cleanup()

    def test_default_receipt_keeps_absolute_paths(self) -> None:
        result, html_path, receipt_path, temporary = self._run(load_json(FIXTURE_ROOT / "voc-insight.json"))
        try:
            self.assertEqual(result.returncode, 0, result.stdout)
            receipt = load_json(receipt_path)
            self.assertEqual(receipt["output_path"], str(html_path.resolve()))
            self.assertNotIn("artifact_path_base", receipt)
        finally:
            temporary.cleanup()

    @classmethod
    def setUpClass(cls) -> None:
        if not CLI_PATH.is_file():
            raise unittest.SkipTest(f"renderer CLI 尚未生成：{CLI_PATH}")
        cls.cases = load_json(GOLDEN_CASES_PATH)

    def _run(
        self,
        spec: dict[str, Any],
        *,
        output_name: str = "report.html",
        extra_args: list[str] | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], Path, Path, tempfile.TemporaryDirectory[str]]:
        temp_dir = tempfile.TemporaryDirectory(prefix="amazon-html-render-test-")
        root = Path(temp_dir.name)
        spec_path = root / "spec.json"
        output_path = root / output_name
        spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
        command = [
            sys.executable,
            str(CLI_PATH),
            "--spec",
            str(spec_path),
            "--output",
            str(output_path),
        ]
        if extra_args:
            command.extend(extra_args)
        result = subprocess.run(command, text=True, capture_output=True, encoding="utf-8")
        receipt_path = output_path.with_suffix(".render-receipt.json")
        return result, output_path, receipt_path, temp_dir

    def _assert_machine_stdout(self, result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
        stripped = result.stdout.strip()
        self.assertTrue(stripped, result.stderr)
        self.assertFalse(stripped.startswith("[") and "\n" in stripped)
        payload = json.loads(stripped)
        self.assertIsInstance(payload, dict)
        return payload

    def _single_row_table_spec(self, columns: list[dict[str, Any]]) -> dict[str, Any]:
        spec = load_json(FIXTURE_ROOT / "ads-performance.json")
        dataset = next(item for item in spec["datasets"] if item["dataset_id"] == "ds-search-terms")
        dataset["columns"] = [
            {
                "column_id": column.get("column_id", f"column-{index}"),
                "label": column["label"],
                "data_type": column.get("data_type", "string"),
            }
            for index, column in enumerate(columns)
        ]
        dataset["rows"] = [
            {
                "row_id": "adaptive-width-row",
                "values": [
                    {
                        "column_id": dataset["columns"][index]["column_id"],
                        "value": column.get("value"),
                        "status": column.get(
                            "status",
                            "MISSING" if column.get("value") is None else "OBSERVED",
                        ),
                        "source_refs": ["src-ads-export"],
                    }
                    for index, column in enumerate(columns)
                ],
            }
        ]
        spec["sections"] = [
            {
                "section_id": "adaptive-width-section",
                "title": "自适应列宽验证",
                "components": [
                    {
                        "component_id": "adaptive-width-table",
                        "type": "data_table",
                        "dataset_id": "ds-search-terms",
                    }
                ],
            }
        ]
        return spec

    def test_six_golden_cases_render_and_emit_verified_receipts(self) -> None:
        for case in self.cases:
            with self.subTest(case=case["case_id"]):
                spec = load_json(SKILL_ROOT / case["fixture"])
                result, output_path, receipt_path, temp_dir = self._run(spec)
                try:
                    payload = self._assert_machine_stdout(result)
                    self.assertEqual(result.returncode, 0, payload)
                    self.assertTrue(output_path.is_file())
                    self.assertTrue(receipt_path.is_file())
                    receipt = load_json(receipt_path)
                    self.assertEqual(receipt["status"], case["expected_status"])
                    for field in (
                        "input_semantic_hash",
                        "html_hash",
                        "template_version",
                        "warnings",
                        "validation",
                    ):
                        self.assertIn(field, receipt)
                    self.assertTrue(receipt["input_semantic_hash"])
                    self.assertTrue(receipt["html_hash"])
                    self.assertTrue(payload["ok"])
                finally:
                    temp_dir.cleanup()

    def test_same_spec_produces_same_semantic_html_hash(self) -> None:
        spec = load_json(FIXTURE_ROOT / "ads-performance.json")
        first = self._run(spec, output_name="first.html")
        second = self._run(spec, output_name="second.html")
        try:
            first_result, first_output, first_receipt_path, _ = first
            second_result, second_output, second_receipt_path, _ = second
            self.assertEqual(first_result.returncode, 0, first_result.stdout or first_result.stderr)
            self.assertEqual(second_result.returncode, 0, second_result.stdout or second_result.stderr)
            first_receipt = load_json(first_receipt_path)
            second_receipt = load_json(second_receipt_path)
            self.assertEqual(first_receipt["input_semantic_hash"], second_receipt["input_semantic_hash"])
            self.assertEqual(first_receipt["html_hash"], second_receipt["html_hash"])
            self.assertEqual(first_output.read_bytes(), second_output.read_bytes())
        finally:
            first[3].cleanup()
            second[3].cleanup()

    def test_static_html_is_self_contained_accessible_and_printable(self) -> None:
        spec = load_json(FIXTURE_ROOT / "ads-performance.json")
        result, output_path, _, temp_dir = self._run(spec)
        try:
            self.assertEqual(result.returncode, 0, result.stderr)
            document = output_path.read_text(encoding="utf-8")
            lowered = document.lower()
            self.assertEqual(len(re.findall(r"<h1\b", lowered)), 1)
            ids = re.findall(r'\bid=["\']([^"\']+)["\']', document)
            self.assertEqual(len(ids), len(set(ids)))
            self.assertIn("content-security-policy", lowered)
            self.assertRegex(lowered, r"default-src\s+'none'")
            self.assertRegex(lowered, r"connect-src\s+'none'")
            self.assertIn("<caption", lowered)
            self.assertRegex(lowered, r"<th\b[^>]*\bscope=")
            self.assertRegex(lowered, r"<svg\b[\s\S]*?<title\b")
            self.assertRegex(lowered, r"<svg\b[\s\S]*?<desc\b")
            self.assertIn("@media print", lowered)
            self.assertNotIn("{{", document)
            self.assertNotIn("{%", document)
            self.assertNotRegex(lowered, r'<(?:script|link|img)\b[^>]*(?:src|href)=["\']https?://')
            self.assertNotRegex(lowered, r"\bon[a-z]+\s*=")
            for network_api in ("fetch(", "xmlhttprequest", "websocket("):
                self.assertNotIn(network_api, lowered)
        finally:
            temp_dir.cleanup()

    def test_wide_tables_preserve_column_roles_and_scroll_inside_their_container(self) -> None:
        spec = load_json(FIXTURE_ROOT / "ads-performance.json")
        dataset = next(item for item in spec["datasets"] if item["dataset_id"] == "ds-search-terms")
        source_row = copy.deepcopy(dataset["rows"][0])
        extra_columns = [
            ("spend", "花费", "number", 123.45),
            ("sales", "销售额", "number", 456.78),
            ("acos", "ACoS", "number", 27.06),
            ("action", "建议", "string", "保留人工复核并在同口径周期复盘"),
        ]
        for column_id, label, data_type, value in extra_columns:
            dataset["columns"].append(
                {"column_id": column_id, "label": label, "data_type": data_type}
            )
            source_row["values"].append(
                {
                    "column_id": column_id,
                    "value": value,
                    "status": "OBSERVED",
                    "source_refs": ["src-ads-export"],
                }
            )
        dataset["rows"] = [source_row]
        spec["sections"] = [
            {
                "section_id": "wide-table-section",
                "title": "宽表验证",
                "components": [
                    {
                        "component_id": "wide-table",
                        "type": "data_table",
                        "dataset_id": "ds-search-terms",
                    }
                ],
            }
        ]
        result, output_path, _, temp_dir = self._run(spec)
        try:
            self.assertEqual(result.returncode, 0, result.stdout or result.stderr)
            document = output_path.read_text(encoding="utf-8")
            self.assertIn('class="data-table table-layout-wide"', document)
            self.assertIn(
                'class="table-col-primary table-col-short table-cell-priority">匿名搜索词</th>', document
            )
            self.assertIn(
                'class="table-col-numeric table-col-short table-cell-priority">花费</th>', document
            )
            self.assertIn(
                'class="table-col-text table-col-expanded table-col-width-20">建议</th>',
                document,
            )
            self.assertIn('.table-layout-wide{min-width:1480px}', document)
            self.assertIn('overflow-x:auto', document)
        finally:
            temp_dir.cleanup()

    def test_content_heavy_table_keeps_short_leading_cells_on_one_line(self) -> None:
        spec = load_json(FIXTURE_ROOT / "ads-performance.json")
        dataset = next(item for item in spec["datasets"] if item["dataset_id"] == "ds-search-terms")
        source_row = copy.deepcopy(dataset["rows"][0])
        extra_columns = [
            ("ratio", "样本占比", "number", 0.38),
            (
                "evidence",
                "中文说明与原文证据",
                "string",
                "中文说明：用于集中整理和收纳各类玩具。；英文原文："
                + "This is a deliberately long evidence excerpt. " * 4,
            ),
        ]
        for column_id, label, data_type, value in extra_columns:
            dataset["columns"].append(
                {"column_id": column_id, "label": label, "data_type": data_type}
            )
            source_row["values"].append(
                {
                    "column_id": column_id,
                    "value": value,
                    "status": "OBSERVED",
                    "source_refs": ["src-ads-export"],
                }
            )
        dataset["rows"] = [source_row]
        spec["sections"] = [
            {
                "section_id": "content-heavy-table-section",
                "title": "内容密集宽表验证",
                "components": [
                    {
                        "component_id": "content-heavy-table",
                        "type": "data_table",
                        "dataset_id": "ds-search-terms",
                    }
                ],
            }
        ]
        result, output_path, _, temp_dir = self._run(spec)
        try:
            self.assertEqual(result.returncode, 0, result.stdout or result.stderr)
            document = output_path.read_text(encoding="utf-8")
            self.assertIn('class="data-table table-layout-wide"', document)
            self.assertIn(
                'class="table-col-primary table-col-short table-cell-priority">匿名搜索词</th>', document
            )
            self.assertIn(
                'class="table-col-numeric table-col-short table-cell-priority">样本占比</th>', document
            )
            self.assertIn(
                'class="table-col-text table-col-expanded table-col-width-48 table-col-capped">中文说明与原文证据</th>',
                document,
            )
            self.assertIn(
                '.table-cell-priority{width:1%;white-space:nowrap!important', document
            )
            self.assertIn('overscroll-behavior-inline:contain', document)
        finally:
            temp_dir.cleanup()

    def test_short_rank_column_uses_compact_width(self) -> None:
        spec = load_json(FIXTURE_ROOT / "ads-performance.json")
        dataset = next(item for item in spec["datasets"] if item["dataset_id"] == "ds-search-terms")
        dataset["columns"][0] = {"column_id": "rank", "label": "排名", "data_type": "integer"}
        for rank, row in enumerate(dataset["rows"], start=1):
            row["values"][0] = {
                "column_id": "rank",
                "value": rank,
                "status": "OBSERVED",
                "source_refs": ["src-ads-export"],
            }
        for column_id, label, data_type, value in [
            ("scenario", "使用场景", "string", "日常玩具收纳"),
            ("evidence", "中文说明与原文证据", "string", "原文证据" * 30),
        ]:
            dataset["columns"].append(
                {"column_id": column_id, "label": label, "data_type": data_type}
            )
            for row in dataset["rows"]:
                row["values"].append(
                    {
                        "column_id": column_id,
                        "value": value,
                        "status": "OBSERVED",
                        "source_refs": ["src-ads-export"],
                    }
                )
        spec["sections"] = [
            {
                "section_id": "ordinal-table-section",
                "title": "紧凑排名列验证",
                "components": [
                    {
                        "component_id": "ordinal-table",
                        "type": "data_table",
                        "dataset_id": "ds-search-terms",
                    }
                ],
            }
        ]
        result, output_path, _, temp_dir = self._run(spec)
        try:
            self.assertEqual(result.returncode, 0, result.stdout or result.stderr)
            document = output_path.read_text(encoding="utf-8")
            self.assertIn(
                'class="table-col-primary table-col-numeric table-col-short table-col-ordinal table-cell-priority">排名</th>',
                document,
            )
            self.assertIn(
                '.table-col-numeric{width:1%;white-space:nowrap',
                document,
            )
            self.assertIn(
                '.table-col-ordinal{width:1%;white-space:nowrap',
                document,
            )
            self.assertIn(
                '.table-col-short{width:1%;white-space:nowrap',
                document,
            )
        finally:
            temp_dir.cleanup()

    def test_visible_width_units_follow_unicode_contract(self) -> None:
        self.assertEqual(visible_width_units("中文ＡＢ"), 4.0)
        self.assertEqual(visible_width_units("中文AB12"), 4.0)
        self.assertEqual(visible_width_units("A\u0301"), 0.5)
        self.assertEqual(visible_width_units("\u0301\u0000"), 0.0)
        self.assertEqual(visible_width_units("甲\n\t乙"), 2.5)

    def test_adaptive_width_buckets_cover_new_and_legacy_boundaries(self) -> None:
        cases = (
            ("甲" * 10, 10.0, None),
            ("甲" * 10 + "A", 10.5, 16),
            ("甲" * 11, 11.0, 16),
            ("甲" * 20, 20.0, 24),
            ("甲" * 21, 21.0, 24),
            ("中文" + "A" * 18, 11.0, 16),
        )
        for value, expected_units, expected_width in cases:
            with self.subTest(value=value):
                max_units, width_em = column_width_profile("列", [value])
                self.assertEqual(max_units, expected_units)
                self.assertEqual(width_em, expected_width)

    def test_column_audit_expands_first_and_middle_columns_and_keeps_missing_visible(self) -> None:
        spec = self._single_row_table_spec(
            [
                {"label": "首列", "value": "短首"},
                {"label": "短列", "value": "短值"},
                {"label": "中间列", "value": "短中"},
                {"label": "缺失状态", "value": None},
            ]
        )
        dataset = next(item for item in spec["datasets"] if item["dataset_id"] == "ds-search-terms")
        later_row = copy.deepcopy(dataset["rows"][0])
        later_row["row_id"] = "adaptive-width-later-row"
        later_row["values"][0]["value"] = "甲" * 11
        later_row["values"][2]["value"] = "乙" * 21
        dataset["rows"].append(later_row)
        result, output_path, _, temp_dir = self._run(spec)
        try:
            self.assertEqual(result.returncode, 0, result.stdout or result.stderr)
            document = output_path.read_text(encoding="utf-8")
            self.assertIn('class="data-table table-layout-wide"', document)
            self.assertIn(
                'class="table-col-primary table-col-expanded table-col-width-16">首列</th>',
                document,
            )
            self.assertIn(
                'class="table-col-text table-col-expanded table-col-width-24">中间列</th>',
                document,
            )
            self.assertIn(
                'class="table-col-text table-col-short table-cell-priority">缺失状态</th>',
                document,
            )
            self.assertIn(
                'cell-missing table-col-text table-col-short table-cell-priority">缺失<span class="sr-only">',
                document,
            )
            self.assertIn("甲" * 11, document)
            self.assertIn("乙" * 21, document)
        finally:
            temp_dir.cleanup()

    def test_overlong_column_caps_at_48em_preserves_text_and_resets_for_print(self) -> None:
        original = "超长内容" * 30
        spec = self._single_row_table_spec(
            [
                {"label": "项目", "value": "示例"},
                {"label": "完整原文", "value": original},
            ]
        )
        result, output_path, _, temp_dir = self._run(spec)
        try:
            self.assertEqual(result.returncode, 0, result.stdout or result.stderr)
            document = output_path.read_text(encoding="utf-8")
            self.assertIn(
                'class="table-col-text table-col-expanded table-col-width-48 table-col-capped">完整原文</th>',
                document,
            )
            self.assertIn(original, document)
            self.assertIn('.table-col-width-48{width:48em;min-width:48em}', document)
            self.assertIn(
                'table.table-layout-standard :is(th,td),table.table-layout-wide :is(th,td),table.table-layout-dense :is(th,td){width:auto!important;min-width:0!important;max-width:none!important;white-space:normal!important',
                document,
            )
        finally:
            temp_dir.cleanup()

    def test_four_five_and_fourteen_column_layout_tiers_remain_stable(self) -> None:
        cases = (
            (4, False, "table-layout-standard"),
            (4, True, "table-layout-wide"),
            (5, False, "table-layout-wide"),
            (14, False, "table-layout-dense"),
        )
        for column_count, expanded, expected in cases:
            with self.subTest(column_count=column_count, expanded=expanded):
                columns = [
                    {"label": f"列{index + 1}", "value": f"值{index + 1}"}
                    for index in range(column_count)
                ]
                if expanded:
                    columns[2]["value"] = "甲" * 11
                result, output_path, _, temp_dir = self._run(self._single_row_table_spec(columns))
                try:
                    self.assertEqual(result.returncode, 0, result.stdout or result.stderr)
                    document = output_path.read_text(encoding="utf-8")
                    first_table = re.search(
                        r'<table class="data-table (table-layout-[a-z]+)">',
                        document,
                    )
                    self.assertIsNotNone(first_table)
                    self.assertEqual(first_table.group(1), expected)
                finally:
                    temp_dir.cleanup()

    def test_source_appendix_uses_the_same_adaptive_width_audit(self) -> None:
        spec = load_json(FIXTURE_ROOT / "ads-performance.json")
        long_source_name = "来源" * 5 + "甲"
        spec["sources"][0]["name"] = long_source_name
        result, output_path, _, temp_dir = self._run(spec)
        try:
            self.assertEqual(result.returncode, 0, result.stdout or result.stderr)
            document = output_path.read_text(encoding="utf-8")
            self.assertIn('id="source-appendix"', document)
            self.assertIn(
                'class="table-col-primary table-col-expanded table-col-width-16">来源</th>',
                document,
            )
            self.assertIn(long_source_name, document)
        finally:
            temp_dir.cleanup()

    def test_chart_radar_and_keyword_tables_share_the_adaptive_width_audit(self) -> None:
        long_label = "列名" * 5 + "甲"
        cases = (
            ("ads-performance.json", "ds-daily-trend", "chart-summary-table"),
            ("mcp-insight.json", "ds-tool-radar", "comparison-table"),
            ("voc-insight.json", "ds-topics", "data-table"),
        )
        for fixture_name, dataset_id, table_class in cases:
            with self.subTest(fixture=fixture_name):
                spec = load_json(FIXTURE_ROOT / fixture_name)
                dataset = next(item for item in spec["datasets"] if item["dataset_id"] == dataset_id)
                dataset["columns"][0]["label"] = long_label
                result, output_path, _, temp_dir = self._run(spec)
                try:
                    self.assertEqual(result.returncode, 0, result.stdout or result.stderr)
                    document = output_path.read_text(encoding="utf-8")
                    self.assertIn(f'class="{table_class} table-layout-standard"', document)
                    self.assertIn(
                        f'class="table-col-primary table-col-expanded table-col-width-16">{long_label}</th>',
                        document,
                    )
                finally:
                    temp_dir.cleanup()

    def test_javascript_is_progressive_enhancement_and_images_have_alt(self) -> None:
        spec = load_json(FIXTURE_ROOT / "voc-insight.json")
        result, output_path, _, temp_dir = self._run(spec)
        try:
            self.assertEqual(result.returncode, 0, result.stdout or result.stderr)
            document = output_path.read_text(encoding="utf-8")
            without_scripts = re.sub(
                r"<script\b[^>]*>[\s\S]*?</script>",
                "",
                document,
                flags=re.IGNORECASE,
            )
            self.assertIn("匿名商品 VOC 洞察", without_scripts)
            self.assertIn("The zipper failed after light use.", without_scripts)
            image_tags = re.findall(r"<img\b[^>]*>", without_scripts, flags=re.IGNORECASE)
            self.assertTrue(image_tags)
            for image_tag in image_tags:
                self.assertRegex(image_tag, r'\balt=["\'][^"\']+["\']')
        finally:
            temp_dir.cleanup()

    def test_back_to_top_anchor_localization_and_internal_link_contract(self) -> None:
        zh_spec = load_json(FIXTURE_ROOT / "ads-performance.json")
        result, output_path, _, temp_dir = self._run(zh_spec)
        try:
            self.assertEqual(result.returncode, 0, result.stdout or result.stderr)
            document = output_path.read_text(encoding="utf-8")
            parser = InternalLinkParser()
            parser.feed(document)

            back_links = [
                link
                for link in parser.internal_links
                if "back-to-top" in link.get("class", "").split()
            ]
            self.assertEqual(len(back_links), 1)
            self.assertEqual(back_links[0].get("id"), "back-to-top")
            self.assertEqual(back_links[0].get("href"), "#report-top")
            self.assertEqual(back_links[0].get("aria-label"), "回到顶部")
            self.assertEqual(parser.ids.count("report-top"), 1)
            self.assertNotIn("hidden", back_links[0])
            self.assertNotEqual(back_links[0].get("aria-hidden"), "true")

            id_counts = {item_id: parser.ids.count(item_id) for item_id in set(parser.ids)}
            self.assertEqual(len(parser.ids), len(id_counts))
            for link in parser.internal_links:
                href = link["href"]
                self.assertRegex(href, r"^#[A-Za-z][A-Za-z0-9_.:-]*$")
                self.assertEqual(id_counts.get(href[1:]), 1, href)
        finally:
            temp_dir.cleanup()

        en_spec = load_json(FIXTURE_ROOT / "ads-performance.json")
        en_spec["report"]["locale"] = "en-US"
        en_result, en_output, _, en_temp_dir = self._run(en_spec)
        try:
            self.assertEqual(en_result.returncode, 0, en_result.stdout or en_result.stderr)
            en_document = en_output.read_text(encoding="utf-8")
            en_parser = InternalLinkParser()
            en_parser.feed(en_document)
            en_back_links = [
                link
                for link in en_parser.internal_links
                if "back-to-top" in link.get("class", "").split()
            ]
            self.assertEqual(len(en_back_links), 1)
            self.assertEqual(en_back_links[0].get("href"), "#report-top")
            self.assertEqual(en_back_links[0].get("aria-label"), "Back to top")
        finally:
            en_temp_dir.cleanup()

    def test_back_to_top_uses_intersection_observer_without_scroll_listener(self) -> None:
        spec = load_json(FIXTURE_ROOT / "ads-performance.json")
        result, output_path, _, temp_dir = self._run(spec)
        try:
            self.assertEqual(result.returncode, 0, result.stdout or result.stderr)
            document = output_path.read_text(encoding="utf-8")
            scripts = "\n".join(
                re.findall(r"<script\b[^>]*>([\s\S]*?)</script>", document, flags=re.IGNORECASE)
            )
            self.assertIn("IntersectionObserver", scripts)
            self.assertNotRegex(
                scripts,
                r"addEventListener\s*\(\s*['\"]scroll['\"]|\bonscroll\s*=",
            )
            self.assertNotIn("window.scrollTo", scripts)
        finally:
            temp_dir.cleanup()

    def test_text_injection_is_rendered_as_text_not_markup(self) -> None:
        spec = load_json(FIXTURE_ROOT / "operations-operations.json")
        payloads = [
            "<script>globalThis.pwned=true</script>",
            "<img src=x onerror=alert(1)>",
            "javascript:alert(1)",
            "</section><script>alert(2)</script>",
        ]
        spec["sections"][0]["components"][0]["paragraphs"].extend(payloads)
        result, output_path, _, temp_dir = self._run(spec)
        try:
            self.assertEqual(result.returncode, 0, result.stderr)
            document = output_path.read_text(encoding="utf-8")
            self.assertNotIn("<script>globalThis.pwned", document)
            self.assertNotIn("<img src=x onerror", document)
            self.assertNotIn("</section><script>alert(2)", document)
            for payload in payloads:
                self.assertIn(html.escape(payload, quote=True), document)
        finally:
            temp_dir.cleanup()

    def test_svg_charts_preserve_null_zero_negative_and_large_finite_values(self) -> None:
        spec = load_json(FIXTURE_ROOT / "ads-performance.json")
        trend = next(dataset for dataset in spec["datasets"] if dataset["dataset_id"] == "ds-daily-trend")
        spend_cells = [
            next(cell for cell in row["values"] if cell["column_id"] == "spend")
            for row in trend["rows"]
        ]
        sales_cells = [
            next(cell for cell in row["values"] if cell["column_id"] == "sales")
            for row in trend["rows"]
        ]
        spend_cells[0]["value"] = -10
        spend_cells[1]["value"] = 0
        spend_cells[2]["value"] = 1_000_000_000
        sales_cells[1]["value"] = None
        sales_cells[1]["status"] = "MISSING"

        result, output_path, _, temp_dir = self._run(spec)
        try:
            self.assertEqual(result.returncode, 0, result.stdout or result.stderr)
            document = output_path.read_text(encoding="utf-8")
            self.assertIn("-10", document)
            self.assertIn("1000000000", document.replace(",", ""))
            self.assertTrue("缺失" in document or "MISSING" in document)
            self.assertNotRegex(document.lower(), r"\b(?:nan|infinity|inf)\b")
        finally:
            temp_dir.cleanup()

    def test_unknown_component_raw_fields_and_derived_without_formula_are_rejected(self) -> None:
        base = load_json(FIXTURE_ROOT / "ads-performance.json")
        mutations: list[tuple[str, dict[str, Any]]] = []

        unknown = copy.deepcopy(base)
        unknown["sections"][0]["components"].append({"type": "html", "raw_html": "<b>x</b>"})
        mutations.append(("unknown component", unknown))

        raw_js = copy.deepcopy(base)
        raw_js["render"]["raw_javascript"] = "alert(1)"
        mutations.append(("raw javascript", raw_js))

        no_formula = copy.deepcopy(base)
        no_formula["metrics"][0]["value_status"] = "DERIVED"
        no_formula["metrics"][0]["derivation"] = {
            "input_refs": ["spend", "sales"],
            "calculation_receipt": "missing formula fixture",
        }
        mutations.append(("derived missing formula", no_formula))

        for label, spec in mutations:
            with self.subTest(label=label):
                result, output_path, receipt_path, temp_dir = self._run(spec)
                try:
                    payload = self._assert_machine_stdout(result)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse(payload["ok"])
                    self.assertFalse(output_path.exists())
                    self.assertFalse(receipt_path.exists())
                finally:
                    temp_dir.cleanup()

    def test_remote_signed_credential_pii_and_illegal_image_paths_are_rejected(self) -> None:
        base = load_json(FIXTURE_ROOT / "voc-insight.json")
        unsafe_values = {
            "remote": "https://example.invalid/evidence.png",
            "signed_url": "https://example.invalid/x.png?X-Amz-Signature=secret",
            "credential": "data:image/png;base64,AKIAIOSFODNN7EXAMPLE",
            "pii": "C:\\private\\buyer-13800138000.png",
            "illegal_path": "..\\..\\secret.png",
        }
        for label, unsafe_src in unsafe_values.items():
            with self.subTest(label=label):
                spec = copy.deepcopy(base)
                spec["sections"][-1]["components"][0]["images"][0]["src"] = unsafe_src
                result, output_path, receipt_path, temp_dir = self._run(spec)
                try:
                    payload = self._assert_machine_stdout(result)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse(payload["ok"])
                    self.assertFalse(output_path.exists())
                    self.assertFalse(receipt_path.exists())
                finally:
                    temp_dir.cleanup()

    def test_unredacted_privacy_pii_credentials_and_private_ids_are_rejected(self) -> None:
        base = load_json(FIXTURE_ROOT / "ads-performance.json")
        mutations: list[tuple[str, dict[str, Any]]] = []

        unredacted = copy.deepcopy(base)
        unredacted["report"]["privacy"]["contains_private_identifiers"] = True
        mutations.append(("privacy flag", unredacted))

        email = copy.deepcopy(base)
        email["report"]["title"] = "联系 buyer@example.com 复核报告"
        mutations.append(("email", email))

        credential = copy.deepcopy(base)
        credential["report"]["title"] = "api_key=secret-example-value"
        mutations.append(("credential", credential))

        private_id = copy.deepcopy(base)
        private_id["report"]["title"] = "Campaign ID: CAMP1234"
        mutations.append(("private identifier", private_id))

        for label, spec in mutations:
            with self.subTest(label=label):
                result, output_path, receipt_path, temp_dir = self._run(spec)
                try:
                    payload = self._assert_machine_stdout(result)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse(payload["ok"])
                    self.assertFalse(output_path.exists())
                    self.assertFalse(receipt_path.exists())
                finally:
                    temp_dir.cleanup()

    def test_evidence_image_size_limits_are_enforced(self) -> None:
        spec = load_json(FIXTURE_ROOT / "voc-insight.json")
        spec["sections"][-1]["components"][0]["images"][0]["src"] = (
            "data:image/png;base64," + ("A" * (5 * 1024 * 1024 * 4 // 3 + 128))
        )
        result, output_path, receipt_path, temp_dir = self._run(spec)
        try:
            payload = self._assert_machine_stdout(result)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(payload["ok"])
            self.assertFalse(output_path.exists())
            self.assertFalse(receipt_path.exists())
        finally:
            temp_dir.cleanup()

    def test_evidence_image_total_limit_is_enforced(self) -> None:
        spec = load_json(FIXTURE_ROOT / "voc-insight.json")
        payload = "data:image/png;base64," + ("A" * (4_300_000 * 4 // 3))
        image_template = spec["sections"][-1]["components"][0]["images"][0]
        spec["sections"][-1]["components"][0]["images"] = [
            {**copy.deepcopy(image_template), "src": payload, "alt": f"匿名证据图 {index}"}
            for index in range(1, 6)
        ]
        result, output_path, receipt_path, temp_dir = self._run(spec)
        try:
            payload = self._assert_machine_stdout(result)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(payload["ok"])
            self.assertFalse(output_path.exists())
            self.assertFalse(receipt_path.exists())
        finally:
            temp_dir.cleanup()

    def test_default_no_overwrite_and_validate_only(self) -> None:
        spec = load_json(FIXTURE_ROOT / "ads-performance.json")
        result, output_path, receipt_path, temp_dir = self._run(spec)
        try:
            self.assertEqual(result.returncode, 0, result.stderr)
            spec_path = Path(temp_dir.name) / "spec.json"
            second = subprocess.run(
                [
                    sys.executable,
                    str(CLI_PATH),
                    "--spec",
                    str(spec_path),
                    "--output",
                    str(output_path),
                ],
                text=True,
                capture_output=True,
                encoding="utf-8",
            )
            self.assertNotEqual(second.returncode, 0)
            self.assertFalse(self._assert_machine_stdout(second)["ok"])

            validate_output = Path(temp_dir.name) / "validate-only.html"
            validate = subprocess.run(
                [
                    sys.executable,
                    str(CLI_PATH),
                    "--spec",
                    str(spec_path),
                    "--output",
                    str(validate_output),
                    "--validate-only",
                ],
                text=True,
                capture_output=True,
                encoding="utf-8",
            )
            self.assertEqual(validate.returncode, 0, validate.stderr)
            self.assertTrue(self._assert_machine_stdout(validate)["ok"])
            self.assertFalse(validate_output.exists())
            self.assertFalse(validate_output.with_suffix(".render-receipt.json").exists())
            self.assertTrue(receipt_path.exists())
        finally:
            temp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
