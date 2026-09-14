from __future__ import annotations

import json
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
TRIGGER_PATH = SKILL_ROOT / "evals" / "trigger-evals.json"


class TriggerEvalContractTests(unittest.TestCase):
    def test_trigger_cases_cover_positive_and_boundary_requests(self) -> None:
        cases = json.loads(TRIGGER_PATH.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(cases), 12)
        self.assertEqual(
            [case["id"] for case in cases],
            [f"TR-{index:03d}" for index in range(1, len(cases) + 1)],
        )
        self.assertEqual(len({case["id"] for case in cases}), len(cases))
        self.assertGreaterEqual(sum(case["should_trigger"] is True for case in cases), 6)
        self.assertGreaterEqual(sum(case["should_trigger"] is False for case in cases), 6)

        for case in cases:
            self.assertIs(type(case["should_trigger"]), bool)
            for field in ("category", "input", "expected_behavior", "pass_criteria"):
                self.assertIsInstance(case[field], str)
                self.assertTrue(case[field].strip(), f"{case['id']}.{field}")

        negatives = [case for case in cases if not case["should_trigger"]]
        negative_text = "\n".join(case["input"] for case in negatives)
        self.assertIn("LinkFox", negative_text)
        self.assertIn("微信", negative_text)
        self.assertIn("四千字", negative_text)
        negative_categories = {case["category"] for case in negatives}
        self.assertIn("generic_analysis", negative_categories)


if __name__ == "__main__":
    unittest.main()
