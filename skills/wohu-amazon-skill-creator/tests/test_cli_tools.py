"""Regression tests for report rendering, eval loading, and clean packaging."""
from __future__ import annotations

import importlib
import io
import json
import sys
import tempfile
import types
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from scripts.generate_report import generate_html, load_report_data, main as report_main
from scripts.package_skill import package_skill


def fake_anthropic_module() -> types.ModuleType:
    """Provide the import surface needed to test input loading without network calls."""
    module = types.ModuleType("anthropic")

    class APIError(Exception):
        pass

    class Anthropic:
        pass

    module.APIError = APIError
    module.Anthropic = Anthropic
    return module


class CliToolTests(unittest.TestCase):
    def test_generate_html_handles_empty_history(self) -> None:
        output = generate_html(
            {"history": [], "original_description": "old", "best_description": "new"},
            auto_refresh=True,
            skill_name="A&B",
        )

        self.assertIn("<!DOCTYPE html>", output)
        self.assertIn('http-equiv="refresh"', output)
        self.assertIn("A&amp;B — Skill Description Optimization", output)
        self.assertIn("<tbody>", output)

    def test_generate_html_renders_and_escapes_results(self) -> None:
        train_result = {
            "query": "<train>",
            "should_trigger": True,
            "pass": True,
            "triggers": 2,
            "runs": 2,
        }
        test_result = {
            "query": "test & holdout",
            "should_trigger": False,
            "pass": False,
            "triggers": 1,
            "runs": 2,
        }
        output = generate_html({
            "original_description": "<old>",
            "best_description": "<new>",
            "best_score": "1/2",
            "best_test_score": "1/1",
            "iterations_run": 1,
            "train_size": 1,
            "test_size": 1,
            "history": [{
                "iteration": 1,
                "description": "<script>alert(1)</script>",
                "train_passed": 1,
                "test_passed": 0,
                "train_results": [train_result],
                "test_results": [test_result],
            }],
        })

        self.assertIn("&lt;old&gt;", output)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", output)
        self.assertNotIn("<script>alert(1)</script>", output)
        self.assertIn("test &amp; holdout", output)
        self.assertIn("best-row", output)
        self.assertIn("2/2", output)

    def test_load_report_data_supports_bom_and_rejects_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            valid_path = root / "valid.json"
            invalid_path = root / "invalid.json"
            valid_path.write_text('{"history": []}', encoding="utf-8-sig")
            invalid_path.write_text("{invalid", encoding="utf-8")

            self.assertEqual(load_report_data(str(valid_path)), {"history": []})
            with self.assertRaisesRegex(ValueError, "Input JSON is invalid"):
                load_report_data(str(invalid_path))

    def test_report_cli_returns_error_for_missing_input(self) -> None:
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            exit_code = report_main(["missing-report-input.json"])

        self.assertEqual(exit_code, 2)
        self.assertIn("Input file not found", stderr.getvalue())

    def test_package_includes_evals_and_excludes_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            skill_dir = root / "sample-skill"
            output_dir = root / "dist"
            (skill_dir / "evals").mkdir(parents=True)
            (skill_dir / "tests").mkdir()
            (skill_dir / "scripts" / "__pycache__").mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\nname: sample-skill\ndescription: Use when explicitly testing a sample skill. Not for other tasks.\n---\n\n# Sample\n",
                encoding="utf-8",
            )
            (skill_dir / "evals" / "evals.json").write_text("{}", encoding="utf-8")
            (skill_dir / "tests" / "test_sample.py").write_text("pass\n", encoding="utf-8")
            (skill_dir / "scripts" / "__pycache__" / "sample.pyc").write_bytes(b"cache")

            with redirect_stdout(io.StringIO()):
                package_path = package_skill(skill_dir, output_dir)

            self.assertIsNotNone(package_path)
            with zipfile.ZipFile(package_path) as archive:
                names = archive.namelist()
            self.assertIn("sample-skill/evals/evals.json", names)
            self.assertIn("sample-skill/tests/test_sample.py", names)
            self.assertFalse(any("__pycache__" in name or name.endswith(".pyc") for name in names))

    def test_package_rejects_non_utf8_skill_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_dir = Path(temp_dir) / "invalid-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_bytes(b"\xff\xfe\xfa")

            with redirect_stdout(io.StringIO()):
                package_path = package_skill(skill_dir)

            self.assertIsNone(package_path)

    def test_run_loop_eval_loader_validates_schema(self) -> None:
        fake_anthropic = fake_anthropic_module()
        with mock.patch.dict(sys.modules, {"anthropic": fake_anthropic}):
            run_loop_module = importlib.import_module("scripts.run_loop")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            valid_path = root / "valid.json"
            invalid_path = root / "invalid.json"
            valid_path.write_text(
                json.dumps([{"query": "create a skill", "should_trigger": True}]),
                encoding="utf-8-sig",
            )
            invalid_path.write_text(
                json.dumps([{"query": "missing boolean"}]),
                encoding="utf-8",
            )

            self.assertEqual(len(run_loop_module.load_eval_set(valid_path)), 1)
            with self.assertRaisesRegex(ValueError, "boolean should_trigger"):
                run_loop_module.load_eval_set(invalid_path)


if __name__ == "__main__":
    unittest.main()
