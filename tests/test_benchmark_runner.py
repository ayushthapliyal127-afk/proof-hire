import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main
from benchmarks.run_benchmark import _aggregate_metrics, _class_metrics, _write_new_report, run_benchmark


def make_case(case_id, claim, target, expected, *, status="provisional_synthetic", refs=None):
    return {
        "id": case_id,
        "repository_url": "synthetic://tests",
        "claim": claim,
        "target_assertion": target,
        "expected_verdict": expected,
        "repository_revision": "synthetic:test",
        "version_assumptions": {"fixture": "test fixture", "verifier": "working tree"},
        "label_status": status,
        "fixture": {"kind": "synthetic", "id": "source"},
        "evidence_basis": {
            "rationale": "Test evidence basis.",
            "reasoning": "Expected label reflects the test fixture.",
            "references": refs or [],
            "authoritative_sources": [],
            "authority_review_status": "not_independently_reviewed",
            "source_validation_status": (
                "fixture_excerpt_checked_by_runner" if refs else "no_source_evidence_reference"
            ),
        },
    }


class BenchmarkRunnerTests(unittest.TestCase):
    def write_json(self, root, name, data):
        path = root / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def run_fixture(self, root, cases, fixture_files, predictor):
        dataset = {"schema_version": 2, "dataset_status": "mixed_provisional", "cases": cases}
        dataset_path = self.write_json(root, "cases.json", dataset)
        fixtures_path = self.write_json(root, "fixtures.json", {"source": fixture_files})
        report = run_benchmark(dataset_path, fixtures_path, root, predictor=predictor)
        return report, dataset_path

    def test_metrics_include_confusion_balanced_accuracy_false_positives_and_abstentions(self):
        cases = [
            make_case("a", "claim a", "a", "SUPPORTED"),
            make_case("b", "claim b", "b", "CONTRADICTED"),
            make_case("c", "claim c", "c", "CONTRADICTED"),
            make_case("d", "claim d", "d", "INSUFFICIENT_EVIDENCE"),
        ]
        predictions = [
            {"id": "a", "predicted": "SUPPORTED", "citation_present": False, "citation_valid": False},
            {"id": "b", "predicted": "SUPPORTED", "citation_present": False, "citation_valid": False},
            {"id": "c", "predicted": "INSUFFICIENT_EVIDENCE", "citation_present": False, "citation_valid": False},
            {"id": "d", "predicted": "INSUFFICIENT_EVIDENCE", "citation_present": False, "citation_valid": False},
        ]
        metrics = _aggregate_metrics(cases, predictions)
        self.assertEqual(metrics["overall_accuracy"], 0.5)
        self.assertAlmostEqual(metrics["balanced_accuracy"], (1.0 + 0.0 + 1.0) / 3)
        self.assertEqual(metrics["false_positive_supported_cases"], ["b"])
        self.assertEqual(metrics["false_negative_supported_cases"], [])
        self.assertEqual(metrics["abstention_rate"], 0.5)
        self.assertEqual(metrics["confusion_matrix"]["CONTRADICTED"]["INSUFFICIENT_EVIDENCE"], 1)
        self.assertEqual(metrics["per_class"]["SUPPORTED"]["precision"], 0.5)
        self.assertEqual(metrics["per_class"]["CONTRADICTED"]["recall"], 0.0)
        self.assertAlmostEqual(metrics["per_class"]["SUPPORTED"]["f1"], 2 / 3)

    def test_reviewed_metrics_are_separate_from_provisional_agreement(self):
        reviewed_case = make_case("reviewed", "claim A", "a", "SUPPORTED", status="reviewed")
        provisional_case = make_case("provisional", "claim B", "b", "CONTRADICTED")
        cases = [reviewed_case, provisional_case]
        predictions = [
            {"id": "reviewed", "predicted": "SUPPORTED", "citation_present": False, "citation_valid": False},
            {"id": "provisional", "predicted": "SUPPORTED", "citation_present": False, "citation_valid": False},
        ]
        metrics = _class_metrics(cases, predictions)
        self.assertEqual(metrics["reviewed_ground_truth_metrics"]["overall_accuracy"], 1.0)
        self.assertEqual(metrics["provisional_or_unreviewed_label_agreement"]["rate"], 0.0)

    def test_report_writer_never_overwrites_existing_file(self):
        with tempfile.TemporaryDirectory() as temp:
            report_path = Path(temp) / "report.json"
            _write_new_report(report_path, '{"original": true}')
            with self.assertRaisesRegex(FileExistsError, "Refusing to overwrite"):
                _write_new_report(report_path, '{"replacement": true}')
            self.assertEqual(report_path.read_text(encoding="utf-8"), '{"original": true}')

    def test_citation_validity_and_dataset_immutability_are_reported(self):
        case = make_case(
            "supported",
            "Built a FastAPI service.",
            "FastAPI",
            "SUPPORTED",
            refs=[{"file": "main.py", "line_start": 2, "line_end": 2, "excerpt": "app = FastAPI()"}],
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            def predictor(_case, _files):
                return {
                    "verdict": "SUPPORTED",
                    "evidence_file": "main.py",
                    "evidence_lines": "2",
                    "analysis_engine": "heuristic",
                }

            report, dataset_path = self.run_fixture(
                root,
                [case],
                {"main.py": "from fastapi import FastAPI\napp = FastAPI()\n"},
                predictor,
            )
            before_after = json.loads(dataset_path.read_text(encoding="utf-8"))
        self.assertEqual(report["dataset_evidence_reference_count"], 1)
        self.assertEqual(
            report["provisional_or_unreviewed_label_metrics"]["citation_correctness"],
            {"valid": 1, "cited": 1, "rate": 1.0},
        )
        self.assertEqual(report["results"][0]["citation_valid"], True)
        self.assertNotIn("predicted", before_after["cases"][0])
        self.assertEqual(report["reviewed_case_count"], 0)
        self.assertIsNone(report["reviewed_ground_truth_metrics"])
        self.assertEqual(report["provisional_or_unreviewed_label_agreement"]["case_count"], 1)
        self.assertEqual(report["label_review_summary"]["needs_review_case_count"], 1)
        self.assertIn(
            "authoritative_documentation_not_independently_reviewed",
            report["results"][0]["review_flags"],
        )

    def test_invalid_expected_evidence_excerpt_is_rejected(self):
        case = make_case(
            "bad-evidence",
            "Built a FastAPI service.",
            "FastAPI",
            "SUPPORTED",
            refs=[{"file": "main.py", "line_start": 1, "line_end": 1, "excerpt": "invented"}],
        )
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "excerpt does not match"):
                self.run_fixture(
                    Path(temp),
                    [case],
                    {"main.py": "actual\n"},
                    lambda *_: "SUPPORTED",
                )

    def test_duplicate_case_ids_and_duplicate_cases_are_rejected(self):
        first = make_case("one", "Built a FastAPI service.", "FastAPI", "SUPPORTED")
        second = copy.deepcopy(first)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dataset_path = self.write_json(
                root,
                "cases.json",
                {"schema_version": 2, "dataset_status": "mixed_provisional", "cases": [first, second]},
            )
            fixtures_path = self.write_json(root, "fixtures.json", {"source": {"main.py": "app = FastAPI()\n"}})
            with self.assertRaisesRegex(ValueError, "IDs must be unique"):
                run_benchmark(dataset_path, fixtures_path, root, predictor=lambda *_: "SUPPORTED")

        second["id"] = "two"
        second["claim"] = "  Built a FastAPI service! "
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dataset_path = self.write_json(
                root,
                "cases.json",
                {"schema_version": 2, "dataset_status": "mixed_provisional", "cases": [first, second]},
            )
            fixtures_path = self.write_json(root, "fixtures.json", {"source": {"main.py": "app = FastAPI()\n"}})
            with self.assertRaisesRegex(ValueError, "duplicate benchmark case"):
                run_benchmark(dataset_path, fixtures_path, root, predictor=lambda *_: "SUPPORTED")

    def test_invalid_label_status_is_rejected(self):
        case = make_case("unknown-status", "claim", "target", "SUPPORTED")
        case["label_status"] = "quietly_ground_truth"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dataset_path = self.write_json(
                root,
                "cases.json",
                {"schema_version": 2, "dataset_status": "mixed_provisional", "cases": [case]},
            )
            fixtures_path = self.write_json(root, "fixtures.json", {"source": {"app.py": "source\n"}})
            with self.assertRaisesRegex(ValueError, "invalid or missing label_status"):
                run_benchmark(dataset_path, fixtures_path, root, predictor=lambda *_: "SUPPORTED")

    def test_predictions_embedded_in_expected_labels_are_rejected(self):
        case = make_case("circular", "claim", "target", "SUPPORTED")
        case["evidence_basis"]["predicted"] = "SUPPORTED"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dataset_path = self.write_json(
                root,
                "cases.json",
                {"schema_version": 2, "dataset_status": "mixed_provisional", "cases": [case]},
            )
            fixtures_path = self.write_json(root, "fixtures.json", {"source": {"app.py": "source\n"}})
            with self.assertRaisesRegex(ValueError, "prediction data must not be stored"):
                run_benchmark(dataset_path, fixtures_path, root, predictor=lambda *_: "SUPPORTED")

    def test_reviewed_label_requires_source_and_authoritative_review_evidence(self):
        case = make_case("unsubstantiated-review", "Built a FastAPI service.", "FastAPI", "SUPPORTED",
                         status="reviewed")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dataset_path = self.write_json(
                root,
                "cases.json",
                {"schema_version": 2, "dataset_status": "mixed_provisional", "cases": [case]},
            )
            fixtures_path = self.write_json(root, "fixtures.json", {"source": {"main.py": "app = FastAPI()\n"}})
            with self.assertRaisesRegex(ValueError, "reviewed labels require cited source evidence"):
                run_benchmark(dataset_path, fixtures_path, root, predictor=lambda *_: "SUPPORTED")

    def test_invalid_prediction_citation_is_counted_as_incorrect(self):
        case = make_case("bad-citation", "Built a FastAPI service.", "FastAPI", "SUPPORTED")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report, _ = self.run_fixture(
                root,
                [case],
                {"main.py": "app = FastAPI()\n"},
                lambda *_: {
                    "verdict": "SUPPORTED",
                    "evidence_file": "main.py",
                    "evidence_lines": "99",
                },
            )
        metrics = report["provisional_or_unreviewed_label_metrics"]["citation_correctness"]
        self.assertEqual(metrics, {"valid": 0, "cited": 1, "rate": 0.0})
        self.assertFalse(report["results"][0]["citation_valid"])

    def test_runner_uses_real_verifier_for_heuristic_mode(self):
        case = make_case(
            "fastapi-supported",
            "Built a FastAPI service.",
            "FastAPI",
            "SUPPORTED",
            refs=[{"file": "main.py", "line_start": 2, "line_end": 2, "excerpt": "app = FastAPI()"}],
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dataset_path = self.write_json(
                root,
                "cases.json",
                {"schema_version": 2, "dataset_status": "mixed_provisional", "cases": [case]},
            )
            fixtures_path = self.write_json(
                root,
                "fixtures.json",
                {"source": {"main.py": "from fastapi import FastAPI\napp = FastAPI()\n"}},
            )
            report = run_benchmark(dataset_path, fixtures_path, root, mode="heuristic")
        self.assertEqual(report["mode"], "heuristic")
        self.assertEqual(report["results"][0]["predicted"], "SUPPORTED")

    def test_llm_provider_failure_is_reported_as_fallback(self):
        case = make_case("provider-fallback", "Built a FastAPI service.", "FastAPI", "SUPPORTED")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dataset_path = self.write_json(
                root,
                "cases.json",
                {"schema_version": 2, "dataset_status": "mixed_provisional", "cases": [case]},
            )
            fixtures_path = self.write_json(
                root,
                "fixtures.json",
                {"source": {"main.py": "from fastapi import FastAPI\napp = FastAPI()\n"}},
            )
            with patch.object(main, "build_llm_audit", side_effect=main.ProviderError("gemini", "rate_limited")):
                report = run_benchmark(
                    dataset_path,
                    fixtures_path,
                    root,
                    mode="llm",
                    provider="gemini",
                    api_key="test-key",
                )
        self.assertEqual(report["fallback_case_count"], 1)
        self.assertEqual(report["results"][0]["fallback_reason"], "rate_limited")
        self.assertEqual(report["results"][0]["analysis_engine"], "heuristic")

    def test_identical_runs_are_reproducible(self):
        case = make_case("repeatable", "Built a FastAPI service.", "FastAPI", "SUPPORTED")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dataset_path = self.write_json(
                root,
                "cases.json",
                {"schema_version": 2, "dataset_status": "mixed_provisional", "cases": [case]},
            )
            fixtures_path = self.write_json(
                root,
                "fixtures.json",
                {"source": {"main.py": "from fastapi import FastAPI\napp = FastAPI()\n"}},
            )
            first = run_benchmark(dataset_path, fixtures_path, root, mode="heuristic")
            second = run_benchmark(dataset_path, fixtures_path, root, mode="heuristic")
        self.assertEqual(first, second)
        self.assertEqual(
            set(first["reproducibility"]["sha256"]),
            {"dataset", "fixtures", "verifier", "benchmark_runner"},
        )


if __name__ == "__main__":
    unittest.main()
