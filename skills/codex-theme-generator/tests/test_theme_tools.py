from __future__ import annotations

import json
import os
import hashlib
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
BUILD = SKILL_ROOT / "scripts" / "build_theme.py"
VALIDATE = SKILL_ROOT / "scripts" / "validate_theme.py"
COMPILE_NATIVE = SKILL_ROOT / "scripts" / "compile_native_theme.py"


class ThemeToolTests(unittest.TestCase):
    def run_cli(
        self,
        script: Path,
        *args: str,
        environment: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(script), *args],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=environment,
        )

    def build_valid_theme(self, root: Path) -> Path:
        theme_dir = root / "aurora-calm"
        result = self.run_cli(
            BUILD,
            "--output-dir",
            str(theme_dir),
            "--id",
            "aurora-calm",
            "--name",
            "极光静域",
            "--appearance",
            "dark",
            "--accent",
            "#7C8CFF",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return theme_dir

    def test_build_and_validate_theme_without_background(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            theme_dir = self.build_valid_theme(Path(temporary))
            result = self.run_cli(VALIDATE, "--theme-dir", str(theme_dir))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "COMPLETE")
            self.assertTrue((theme_dir / "preview.html").is_file())
            theme = json.loads((theme_dir / "theme.json").read_text(encoding="utf-8"))
            self.assertEqual(theme["schemaVersion"], 2)
            self.assertEqual(theme["layout"], {
                "mode": "native",
                "sidebarWidth": 240,
                "contentMaxWidth": 920,
                "composerOffset": 0,
                "density": "comfortable",
            })
            self.assertEqual(set(theme["assets"]["icons"]), {
                "newTask", "search", "projects", "history", "attach", "send", "settings", "skills",
            })
            self.assertTrue((theme_dir / "native-theme.json").is_file())
            self.assertTrue((theme_dir / "native-share.txt").is_file())

    def test_build_report_separates_pack_import_and_activation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "status-boundary"
            result = self.run_cli(
                BUILD,
                "--output-dir",
                str(output),
                "--id",
                "status-boundary",
                "--name",
                "状态边界",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["packStatus"], "COMPLETE")
            self.assertEqual(report["handoffStatus"], "READY")
            self.assertEqual(report["importStatus"], "NOT_RUN")
            self.assertEqual(report["activationStatus"], "NOT_RUN")

    def test_pair_builds_two_independent_theme_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "paired"
            result = self.run_cli(BUILD, "--output-dir", str(output), "--id", "aurora", "--name", "极光", "--pair")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for suffix, appearance in (("dark", "dark"), ("light", "light")):
                root = output / "themes" / f"aurora-{suffix}"
                report = self.run_cli(VALIDATE, "--theme-dir", str(root))
                self.assertEqual(report.returncode, 0, report.stdout + report.stderr)
                theme = json.loads((root / "theme.json").read_text(encoding="utf-8"))
                self.assertEqual(theme["appearance"], appearance)

    def test_bundle_contains_strict_manifest_and_verified_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "theme"
            bundle = root / "fantasy.codextheme"
            result = self.run_cli(
                BUILD,
                "--output-dir",
                str(output),
                "--id",
                "aurora-calm",
                "--name",
                "极光静域",
                "--bundle-output",
                str(bundle),
                "--series-id",
                "fantasy",
                "--series-name",
                "幻想系列",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["bundleStatus"], "COMPLETE")
            self.assertEqual(Path(report["bundlePath"]), bundle)
            with zipfile.ZipFile(bundle) as archive:
                manifest = json.loads(archive.read("bundle.json"))
                self.assertEqual(set(manifest), {
                    "schemaVersion", "bundleId", "name", "series", "themes", "files",
                })
                self.assertEqual(manifest["schemaVersion"], 1)
                self.assertEqual(manifest["series"], {"id": "fantasy", "name": "幻想系列"})
                self.assertEqual(manifest["themes"], [{
                    "id": "aurora-calm", "path": "themes/aurora-calm",
                }])
                for entry in manifest["files"]:
                    payload = archive.read(entry["path"])
                    self.assertEqual(len(payload), entry["size"])
                    self.assertEqual(hashlib.sha256(payload).hexdigest(), entry["sha256"])

    def test_pair_can_be_delivered_as_one_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = root / "paired.codextheme"
            result = self.run_cli(
                BUILD,
                "--output-dir",
                str(root / "paired"),
                "--id",
                "aurora",
                "--name",
                "极光",
                "--pair",
                "--bundle-output",
                str(bundle),
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            with zipfile.ZipFile(bundle) as archive:
                manifest = json.loads(archive.read("bundle.json"))
                self.assertEqual(
                    [item["id"] for item in manifest["themes"]],
                    ["aurora-dark", "aurora-light"],
                )

    def test_existing_bundle_blocks_and_rolls_back_theme_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = root / "existing.codextheme"
            bundle.write_bytes(b"keep")
            output = root / "theme"
            result = self.run_cli(
                BUILD,
                "--output-dir",
                str(output),
                "--id",
                "existing-bundle",
                "--name",
                "已有包",
                "--bundle-output",
                str(bundle),
            )
            self.assertEqual(result.returncode, 2)
            self.assertFalse(output.exists())
            self.assertEqual(bundle.read_bytes(), b"keep")

    def test_malicious_svg_fails_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            icons = root / "icons"
            icons.mkdir()
            (icons / "send.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', encoding="utf-8")
            output = root / "unsafe"
            result = self.run_cli(BUILD, "--output-dir", str(output), "--id", "unsafe", "--name", "Unsafe", "--icon-dir", str(icons))
            self.assertEqual(result.returncode, 2)
            self.assertFalse(output.exists())

    def test_validator_rejects_asset_traversal_and_layout_overflow(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            theme_dir = self.build_valid_theme(root)
            payload_path = theme_dir / "theme.json"
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload["assets"]["homeBackground"] = "../outside.png"
            payload["layout"]["sidebarWidth"] = 999
            payload_path.write_text(json.dumps(payload), encoding="utf-8")
            result = self.run_cli(VALIDATE, "--theme-dir", str(theme_dir))
            self.assertEqual(result.returncode, 1)
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "BLOCKED")
            self.assertIn("asset path", result.stdout)
            self.assertIn("sidebarWidth", result.stdout)

    def test_experimental_layout_requires_complete_host_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            environment = os.environ.copy()
            environment["LOCALAPPDATA"] = temporary
            result = self.run_cli(
                BUILD,
                "--output-dir",
                str(Path(temporary) / "experimental"),
                "--id",
                "experimental",
                "--name",
                "实验布局",
                "--layout",
                "cinematic",
                "--codex-version",
                "26.715.8383.0",
                environment=environment,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("Codex Theme Studio is not installed", result.stdout)

    def test_native_compiler_emits_official_share_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            theme_dir = self.build_valid_theme(root)
            output = root / "native-output"
            result = self.run_cli(
                COMPILE_NATIVE,
                "--theme-dir",
                str(theme_dir),
                "--output-dir",
                str(output),
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            native = json.loads((output / "native-theme.json").read_text(encoding="utf-8"))
            self.assertEqual(native["variant"], "dark")
            self.assertEqual(native["codeThemeId"], "codex")
            self.assertEqual(native["theme"]["contrast"], 60)
            self.assertEqual(native["theme"]["fonts"], {"code": None, "ui": None})
            self.assertEqual(native["theme"]["semanticColors"]["diffAdded"], "#40C977")
            self.assertEqual(native["theme"]["semanticColors"]["diffRemoved"], "#FA423E")
            self.assertEqual(native["theme"]["accent"], "#7C8CFF")
            share = (output / "native-share.txt").read_text(encoding="utf-8")
            self.assertTrue(share.startswith("codex-theme-v1:"))
            self.assertEqual(json.loads(share.removeprefix("codex-theme-v1:")), native)

    def test_auto_theme_emits_two_explicit_native_variants(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "automatic"
            result = self.run_cli(
                BUILD,
                "--output-dir",
                str(output),
                "--id",
                "automatic",
                "--name",
                "跟随系统",
                "--appearance",
                "auto",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse((output / "native-theme.json").exists())
            for variant, contrast in (("dark", 60), ("light", 45)):
                native = json.loads(
                    (output / f"native-theme-{variant}.json").read_text(encoding="utf-8")
                )
                self.assertEqual(native["variant"], variant)
                self.assertEqual(native["theme"]["contrast"], contrast)
                share = (output / f"native-share-{variant}.txt").read_text(encoding="utf-8")
                self.assertTrue(share.startswith("codex-theme-v1:"))

    def test_builder_refuses_non_empty_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            theme_dir = Path(temporary) / "existing"
            theme_dir.mkdir()
            (theme_dir / "keep.txt").write_text("keep", encoding="utf-8")
            result = self.run_cli(BUILD, "--output-dir", str(theme_dir), "--id", "existing", "--name", "Existing")
            self.assertEqual(result.returncode, 2)
            self.assertIn("refusing to overwrite", result.stdout)

    def test_builder_rejects_invalid_id(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = self.run_cli(
                BUILD,
                "--output-dir",
                str(Path(temporary) / "invalid"),
                "--id",
                "Invalid Theme",
                "--name",
                "Invalid",
            )
            self.assertEqual(result.returncode, 2)

    def test_validator_rejects_unknown_runtime_field(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            theme_dir = self.build_valid_theme(Path(temporary))
            theme_path = theme_dir / "theme.json"
            payload = json.loads(theme_path.read_text(encoding="utf-8"))
            payload["runtime"] = "third-party"
            theme_path.write_text(json.dumps(payload), encoding="utf-8")
            result = self.run_cli(VALIDATE, "--theme-dir", str(theme_dir))
            self.assertEqual(result.returncode, 1)
            self.assertIn("unknown fields", result.stdout)
            self.assertIn("forbidden", result.stdout)

    def test_native_layout_rejects_misleading_inactive_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            theme_dir = self.build_valid_theme(Path(temporary))
            theme_path = theme_dir / "theme.json"
            payload = json.loads(theme_path.read_text(encoding="utf-8"))
            payload["layout"]["sidebarWidth"] = 300
            theme_path.write_text(json.dumps(payload), encoding="utf-8")
            result = self.run_cli(VALIDATE, "--theme-dir", str(theme_dir))
            self.assertEqual(result.returncode, 1)
            self.assertIn("native layout must use canonical", result.stdout)

    def test_validator_rejects_missing_or_divergent_native_layer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            missing = self.build_valid_theme(root)
            (missing / "native-share.txt").unlink()
            result = self.run_cli(VALIDATE, "--theme-dir", str(missing))
            self.assertEqual(result.returncode, 1)
            self.assertIn("missing required native output", result.stdout)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            divergent = self.build_valid_theme(root)
            native_path = divergent / "native-theme.json"
            native = json.loads(native_path.read_text(encoding="utf-8"))
            native["theme"]["accent"] = "#FFFFFF"
            native_path.write_text(json.dumps(native), encoding="utf-8")
            result = self.run_cli(VALIDATE, "--theme-dir", str(divergent))
            self.assertEqual(result.returncode, 1)
            self.assertIn("does not match Theme Pack data", result.stdout)

    def test_generator_source_does_not_bundle_theme_studio(self) -> None:
        self.assertFalse((SKILL_ROOT / "tool" / "codex-theme-studio").exists())


if __name__ == "__main__":
    unittest.main()
