"""Behavior tests for the thin Codex Theme Studio CLI proxy."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "theme-selector.ps1"
POWERSHELL = shutil.which("powershell.exe") or shutil.which("powershell")


@unittest.skipUnless(POWERSHELL, "Windows PowerShell is required")
class ThemeSelectorTests(unittest.TestCase):
    def run_selector(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                POWERSHELL,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(SCRIPT),
                *arguments,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8-sig",
            check=False,
        )

    def create_fake_client(self, root: Path) -> Path:
        root.mkdir(parents=True)
        client = root / "CodexThemeStudio.ps1"
        client.write_text(
            "param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Rest)\n"
            "$resultIndex = [Array]::IndexOf($Rest, '--result-file')\n"
            "$payload = [pscustomobject]@{arguments=@($Rest | Select-Object -First $resultIndex)} | ConvertTo-Json -Compress\n"
            "$envelope = [pscustomobject]@{engineVersion='2.7.0';exitCode=0;standardOutput=$payload;standardError=''} | ConvertTo-Json -Compress\n"
            "[System.IO.File]::WriteAllText($Rest[$resultIndex + 1], $envelope, [System.Text.UTF8Encoding]::new($false))\n",
            encoding="utf-8",
        )
        return client

    def test_status_reports_missing_client_without_installing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_selector(
                "-Action",
                "Status",
                "-ClientPath",
                str(Path(directory) / "missing.exe"),
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["installed"])
        self.assertEqual(payload["runtimeStatus"], "NOT_INSTALLED")

    def test_import_calls_only_import(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            theme = root / "theme"
            theme.mkdir()
            client = self.create_fake_client(root / "client")
            result = self.run_selector(
                "-Action",
                "Import",
                "-ClientPath",
                str(client),
                "-PackagePath",
                str(theme),
                "-Confirm",
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["arguments"][:2], ["--engine", "import"])
        self.assertEqual(payload["arguments"][2], "--package")
        self.assertEqual(Path(payload["arguments"][3]), theme)
        self.assertEqual(payload["arguments"][4], "--confirm")

    def test_activate_requires_separate_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client = self.create_fake_client(Path(directory) / "client")
            result = self.run_selector(
                "-Action",
                "Activate",
                "-ClientPath",
                str(client),
                "-ThemeId",
                "aurora-calm",
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires -Confirm", result.stderr)

    def test_install_action_is_not_exposed(self) -> None:
        result = self.run_selector("-Action", "Install")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ValidateSet", result.stderr)


if __name__ == "__main__":
    unittest.main()
