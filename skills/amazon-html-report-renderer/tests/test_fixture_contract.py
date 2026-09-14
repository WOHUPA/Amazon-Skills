from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"
GOLDEN_CASES_PATH = SKILL_ROOT / "evals" / "golden-cases.json"

ALL_COMPONENTS = {
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


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


class GoldenFixtureContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = load_json(GOLDEN_CASES_PATH)
        cls.specs = {
            case["case_id"]: load_json(SKILL_ROOT / case["fixture"])
            for case in cls.cases
        }

    def test_exactly_six_anonymous_golden_cases_are_registered(self) -> None:
        self.assertEqual(len(self.cases), 6)
        self.assertEqual(len({case["case_id"] for case in self.cases}), 6)
        for case in self.cases:
            fixture_path = SKILL_ROOT / case["fixture"]
            self.assertTrue(fixture_path.is_file(), fixture_path)
            raw = fixture_path.read_text(encoding="utf-8").lower()
            for forbidden_identity in (
                "sellercentral",
                "access_token",
                "refresh_token",
                "client_secret",
                "@gmail.com",
                "@qq.com",
            ):
                self.assertNotIn(forbidden_identity, raw, case["case_id"])

    def test_protocol_layouts_modes_and_statuses_are_covered(self) -> None:
        families: set[str] = set()
        statuses: set[str] = set()
        modes: set[str] = set()
        for case in self.cases:
            spec = self.specs[case["case_id"]]
            self.assertEqual(spec["protocol"], "amazon-html-report/v1")
            self.assertEqual(spec["render"]["family"], case["family"])
            self.assertEqual(spec["report"]["status"], case["expected_status"])
            self.assertTrue(spec["report"]["privacy"]["redaction_status"])
            families.add(spec["render"]["family"])
            statuses.add(spec["report"]["status"])
            modes.add(spec["report"]["data_mode"])

        self.assertEqual(families, {"performance", "insight", "operations", "knowledge"})
        self.assertTrue({"COMPLETE", "PARTIAL", "BLOCKED"}.issubset(statuses))
        self.assertTrue({"REAL", "DEMO"}.issubset(modes))

    def test_all_required_components_are_exercised(self) -> None:
        actual_components: set[str] = set()
        for spec in self.specs.values():
            for section in spec["sections"]:
                actual_components.update(component["type"] for component in section["components"])
        self.assertEqual(actual_components, ALL_COMPONENTS)

    def test_components_reference_existing_metrics_and_datasets(self) -> None:
        for case_id, spec in self.specs.items():
            metric_ids = {metric["metric_id"] for metric in spec["metrics"]}
            dataset_ids = {dataset["dataset_id"] for dataset in spec["datasets"]}
            for section in spec["sections"]:
                for component in section["components"]:
                    for metric_id in component.get("metric_ids", []):
                        self.assertIn(metric_id, metric_ids, f"{case_id}:{metric_id}")
                    if "dataset_id" in component:
                        self.assertIn(component["dataset_id"], dataset_ids)

    def test_all_explicit_ids_are_unique_inside_each_spec(self) -> None:
        for case_id, spec in self.specs.items():
            for collection, key in (
                (spec["sources"], "source_id"),
                (spec["metrics"], "metric_id"),
                (spec["datasets"], "dataset_id"),
                (spec["sections"], "section_id"),
                (spec["limitations"], "limitation_id"),
            ):
                values = [item[key] for item in collection]
                self.assertEqual(len(values), len(set(values)), f"{case_id}:{key}")
            component_ids = [
                component["component_id"]
                for section in spec["sections"]
                for component in section["components"]
            ]
            self.assertEqual(len(component_ids), len(set(component_ids)), f"{case_id}:component_id")

    def test_all_numeric_metrics_and_cells_have_sources(self) -> None:
        for case_id, spec in self.specs.items():
            source_ids = {source["source_id"] for source in spec["sources"]}
            self.assertTrue(source_ids, case_id)
            for metric in spec["metrics"]:
                if isinstance(metric["value"], (int, float)) and not isinstance(metric["value"], bool):
                    self.assertTrue(metric["source_refs"], f"{case_id}:{metric['metric_id']}")
                    self.assertTrue(set(metric["source_refs"]).issubset(source_ids))
                if metric["value_status"] == "DERIVED":
                    derivation = metric.get("derivation")
                    self.assertIsInstance(derivation, dict)
                    self.assertTrue(derivation.get("formula"))
                    self.assertTrue(derivation.get("input_refs"))
                    self.assertTrue(derivation.get("calculation_receipt"))

            for dataset in spec["datasets"]:
                column_ids = {column["column_id"] for column in dataset["columns"]}
                for row in dataset["rows"]:
                    self.assertEqual(
                        {cell["column_id"] for cell in row["values"]},
                        column_ids,
                        f"{case_id}:{dataset['dataset_id']}:{row['row_id']}",
                    )
                    for cell in row["values"]:
                        value = cell["value"]
                        if isinstance(value, (int, float)) and not isinstance(value, bool):
                            self.assertTrue(cell["source_refs"])
                            self.assertTrue(set(cell["source_refs"]).issubset(source_ids))

    def test_missing_zero_negative_conflict_and_demo_are_frozen(self) -> None:
        serialized = json.dumps(self.specs, ensure_ascii=False)
        self.assertIn('"value": null', serialized)
        self.assertIn('"value": 0', serialized)
        self.assertRegex(serialized, r'"value":\s*-\d')
        self.assertIn('"value_status": "CONFLICT"', serialized)
        self.assertIn('"data_mode": "DEMO"', serialized)


if __name__ == "__main__":
    unittest.main()
