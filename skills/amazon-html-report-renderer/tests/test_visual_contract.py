from __future__ import annotations

import html
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Iterable


SKILL_ROOT = Path(__file__).resolve().parents[1]
CLI_PATH = SKILL_ROOT / "scripts" / "render_report.py"
FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"


def iter_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for nested in value.values():
            yield from iter_strings(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from iter_strings(nested)


class VisualContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not CLI_PATH.is_file():
            raise unittest.SkipTest(f"renderer CLI 尚未生成：{CLI_PATH}")

    def _render(self, fixture_name: str) -> tuple[str, dict[str, Any]]:
        spec_path = FIXTURE_ROOT / fixture_name
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory(prefix="amazon-html-visual-") as temp_dir:
            output_path = Path(temp_dir) / "report.html"
            result = subprocess.run(
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
            self.assertEqual(result.returncode, 0, result.stdout or result.stderr)
            return output_path.read_text(encoding="utf-8"), spec

    def test_single_amazon_accent_and_shape_tokens_are_fixed(self) -> None:
        document, _ = self._render("ads-performance.json")
        css = re.search(r"<style\b[^>]*>([\s\S]*?)</style>", document, re.IGNORECASE)
        self.assertIsNotNone(css)
        stylesheet = css.group(1)
        compact = re.sub(r"\s+", "", stylesheet.lower())
        self.assertEqual(len(re.findall(r"--accent\s*:", stylesheet)), 1)
        self.assertRegex(compact, r"--accent:#ff9900(?:;|})")
        self.assertRegex(compact, r"--radius-content:12px(?:;|})")
        self.assertRegex(compact, r"--radius-control:8px(?:;|})")
        self.assertRegex(compact, r"--radius-pill:(?:999px|9999px)(?:;|})")
        for forbidden_token in ("--accent-2", "--accent-secondary", "--secondary-accent"):
            self.assertNotIn(forbidden_token, compact)

    def test_theme_is_page_locked_system_aware_and_prints_light(self) -> None:
        document, _ = self._render("ads-performance.json")
        lowered = document.lower()
        self.assertIn("prefers-color-scheme: dark", lowered)
        self.assertIn("@media print", lowered)
        self.assertRegex(lowered, r"color-scheme\s*:\s*light(?:\s+dark)?")
        self.assertNotRegex(lowered, r"<section\b[^>]*\bdata-theme=")
        self.assertRegex(lowered, r"theme[^<]{0,80}(?:toggle|切换)|(?:toggle|切换)[^<]{0,80}theme")

    def test_taste_anti_patterns_are_absent(self) -> None:
        document, _ = self._render("ads-performance.json")
        lowered = document.lower()
        compact = re.sub(r"\s+", "", lowered)
        for forbidden_word in ("purple", "violet", "indigo", "three-card", "step-number", "section-number"):
            self.assertNotIn(forbidden_word, lowered)
        for forbidden_hex in ("#8b5cf6", "#7c3aed", "#a855f7", "#6d28d9"):
            self.assertNotIn(forbidden_hex, lowered)
        self.assertNotIn("repeat(3,1fr)", compact)
        eyebrow_matches = re.findall(r'class=["\'][^"\']*\beyebrow\b[^"\']*["\']', lowered)
        self.assertLessEqual(len(eyebrow_matches), 1)

    def test_template_copy_has_no_em_dash_but_upstream_content_is_preserved(self) -> None:
        document, spec = self._render("operations-operations.json")
        upstream_sentence = "上游原始内容——保留长破折号，不由模板改写。"
        self.assertIn(upstream_sentence, document)

        template_owned = document
        for upstream_text in sorted(set(iter_strings(spec)), key=len, reverse=True):
            template_owned = template_owned.replace(upstream_text, "")
            template_owned = template_owned.replace(html.escape(upstream_text, quote=True), "")
        self.assertNotIn("—", template_owned)

    def test_back_to_top_visual_print_and_reduced_motion_contract(self) -> None:
        document, _ = self._render("ads-performance.json")
        css_match = re.search(r"<style\b[^>]*>([\s\S]*?)</style>", document, re.IGNORECASE)
        self.assertIsNotNone(css_match)
        stylesheet = css_match.group(1)
        compact = re.sub(r"\s+", "", stylesheet.lower())

        base_rule_match = re.search(r"(?<![\w-])\.back-to-top\{([^}]*)\}", compact)
        self.assertIsNotNone(base_rule_match)
        base_rule = base_rule_match.group(1)
        self.assertTrue(
            "width:44px" in base_rule or "min-width:44px" in base_rule,
            base_rule,
        )
        self.assertTrue(
            "height:44px" in base_rule or "min-height:44px" in base_rule,
            base_rule,
        )
        self.assertIn("position:fixed", base_rule)
        self.assertIn("border-radius:var(--radius-control)", base_rule)
        self.assertRegex(
            base_rule,
            r"(?:right|inset-inline-end):(?:max|calc)\([^;]*16px[^;]*safe-area-inset-right[^;]*\)",
        )
        self.assertRegex(
            base_rule,
            r"(?:bottom|inset-block-end):(?:max|calc)\([^;]*16px[^;]*safe-area-inset-bottom[^;]*\)",
        )
        for no_js_hiding in ("display:none", "visibility:hidden", "opacity:0"):
            self.assertNotIn(no_js_hiding, base_rule)

        self.assertRegex(
            compact,
            r"@mediaprint\{[\s\S]*?\.back-to-top[^{]*\{?[^}]*display:none!important",
        )
        self.assertRegex(
            compact,
            r"@media\(prefers-reduced-motion:reduce\)\{[\s\S]*?scroll-behavior:auto",
        )
        self.assertRegex(
            compact,
            r"@media\(prefers-reduced-motion:reduce\)\{[\s\S]*?transition:none!important",
        )

    def test_mobile_viewport_and_wide_tables_do_not_push_fixed_controls_off_screen(self) -> None:
        document, _ = self._render("ads-performance.json")
        self.assertIn(
            '<meta name="viewport" content="width=device-width,initial-scale=1,minimum-scale=1,shrink-to-fit=no,viewport-fit=cover">',
            document,
        )
        css_match = re.search(r"<style\b[^>]*>([\s\S]*?)</style>", document, re.IGNORECASE)
        self.assertIsNotNone(css_match)
        compact = re.sub(r"\s+", "", css_match.group(1).lower())
        self.assertIn(
            ".table-scroll{width:100%;min-width:0;overflow-x:auto;overflow-y:hidden;overscroll-behavior-inline:contain;scrollbar-gutter:stable;scrollbar-color:var(--line-strong)var(--surface-soft);contain:inline-sizepaint}",
            compact,
        )
        self.assertIn(".table-layout-wide{min-width:1480px}", compact)
        self.assertIn(".table-layout-dense{min-width:2780px}", compact)
        self.assertIn("html{max-width:100%;overflow-x:hidden", compact)
        self.assertIn("body{max-width:100%;overflow-x:hidden", compact)
        self.assertIn("@supports(overflow-x:clip){html,body{overflow-x:clip}}", compact)
        self.assertIn(".table-col-numeric{width:1%;white-space:nowrap", compact)
        self.assertIn(".table-col-expanded{white-space:normal", compact)
        self.assertIn(".table-col-capped{max-width:48em", compact)
        self.assertIn(".table-col-width-16{width:16em;min-width:16em}", compact)
        self.assertIn(".table-col-width-48{width:48em;min-width:48em}", compact)
        self.assertIn(".table-cell-priority{width:1%;white-space:nowrap!important", compact)
        self.assertIn(".table-col-ordinal{width:1%;white-space:nowrap", compact)
        self.assertIn(
            ".table-col-numeric{width:1%;white-space:nowrap",
            compact,
        )
        self.assertIn(
            ".table-col-short{width:1%;white-space:nowrap",
            compact,
        )
        self.assertIn(
            "table.table-layout-standard:is(th,td),table.table-layout-wide:is(th,td),table.table-layout-dense:is(th,td){width:auto!important;min-width:0!important;max-width:none!important;white-space:normal!important",
            compact,
        )
        self.assertIn("line-break:strict", compact)
        visual_qa = (SKILL_ROOT / "tests" / "run_visual_qa.mjs").read_text(encoding="utf-8")
        for assertion_name in (
            "tableContainersKeyboardReachable",
            "tableOverflowContained",
            "adaptiveWidthsApplied",
            "scrollHeight",
            "rowHeights",
        ):
            self.assertIn(assertion_name, visual_qa)


if __name__ == "__main__":
    unittest.main()
