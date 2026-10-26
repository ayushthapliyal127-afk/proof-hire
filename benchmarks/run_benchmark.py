"""Run the reproducible, evidence-grounded claim-verification benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
from pathlib import Path
from typing import Callable, Dict, Optional

import main

VERDICTS = (
    "SUPPORTED",
    "CONTRADICTED",
    "PARTIALLY_SUPPORTED",
    "INSUFFICIENT_EVIDENCE",
)
LABEL_STATUSES = {"reviewed", "unreviewed_repository", "provisional_synthetic"}
AUTHORITY_REVIEW_STATUSES = {"not_independently_reviewed", "independently_reviewed"}
SOURCE_VALIDATION_STATUSES = {
    "fixture_excerpt_checked_by_runner",
    "revision_excerpt_checked_by_runner",
    "no_source_evidence_reference",
}


def _read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def _git_file(repo_root: Path, revision: str, path: str) -> str:
    result = subprocess.run(
        ["git", "show", f"{revision}:{path}"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout


def _load_case_files(case: dict, fixtures: dict, repo_root: Path) -> Dict[str, str]:
    fixture = case["fixture"]
    if fixture["kind"] == "synthetic":
        try:
            source_files = dict(fixtures[fixture["id"]])
        except KeyError as exc:
            raise ValueError(f"{case['id']}: unknown synthetic fixture {fixture['id']!r}") from exc
        for path, source in source_files.items():
            if isinstance(source, dict) and set(source) == {"__repeat__"}:
                repeat = source["__repeat__"]
                source_files[path] = "\n".join([repeat["line"]] * repeat["count"]) + "\n"
        return source_files
    if fixture["kind"] == "git":
        path = fixture["path"]
        return {path: _git_file(repo_root, case["repository_revision"], path)}
    raise ValueError(f"{case['id']}: unsupported fixture kind {fixture['kind']!r}")


def _validate_evidence(case: dict, files: Dict[str, str]) -> int:
    references = case["evidence_basis"].get("references", [])
    for reference in references:
        path = reference["file"]
        start = reference["line_start"]
        end = reference["line_end"]
        if path not in files or type(start) is not int or type(end) is not int or start < 1 or end < start:
            raise ValueError(f"{case['id']}: invalid evidence reference {path}:{start}-{end}")
        lines = files[path].splitlines()
        if end > len(lines):
            raise ValueError(f"{case['id']}: evidence line range exceeds {path}")
        excerpt = "\n".join(lines[start - 1:end])
        if excerpt != reference["excerpt"]:
            raise ValueError(f"{case['id']}: evidence excerpt does not match {path}:{start}-{end}")
    return len(references)


def _validate_dataset(dataset: dict) -> list:
    cases = dataset.get("cases")
    if dataset.get("schema_version") != 2:
        raise ValueError("Benchmark dataset schema_version must be 2.")
    if dataset.get("dataset_status") != "mixed_provisional":
        raise ValueError("Benchmark dataset_status must distinguish reviewed and provisional cases.")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Benchmark dataset must contain a non-empty cases list.")
    ids = [case.get("id") for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Benchmark case IDs must be unique.")

    for case in cases:
        case_id = case.get("id", "<unknown>")
        if not isinstance(case.get("id"), str) or not case["id"].strip():
            raise ValueError("Every benchmark case must have a non-empty string id.")
        if case.get("expected_verdict") not in VERDICTS:
            raise ValueError(f"{case_id}: invalid expected verdict {case.get('expected_verdict')!r}")
        if case.get("label_status") not in LABEL_STATUSES:
            raise ValueError(f"{case_id}: invalid or missing label_status")
        if not isinstance(case.get("claim"), str) or not case["claim"].strip():
            raise ValueError(f"{case_id}: missing claim text")
        if not isinstance(case.get("target_assertion"), str) or not case["target_assertion"].strip():
            raise ValueError(f"{case_id}: missing target_assertion")
        version_assumptions = case.get("version_assumptions")
        if not case.get("repository_revision") or not isinstance(version_assumptions, dict) or not version_assumptions:
            raise ValueError(f"{case_id}: repository revision and version assumptions are required")
        repository_url = case.get("repository_url")
        if not isinstance(repository_url, (str, type(None))):
            raise ValueError(f"{case_id}: repository_url must be a URL or null")
        if isinstance(repository_url, str) and not repository_url.startswith(("https://", "synthetic://")):
            raise ValueError(f"{case_id}: repository_url must use https:// or synthetic://")
        if case.get("fixture", {}).get("kind") == "git" and repository_url is None:
            if case.get("repository_url_status") != "unavailable_no_git_remote":
                raise ValueError(f"{case_id}: unavailable repository URL must be disclosed")
        if case.get("fixture", {}).get("kind") == "synthetic" and not str(repository_url).startswith("synthetic://"):
            raise ValueError(f"{case_id}: synthetic fixture requires a synthetic:// repository locator")
        basis = case.get("evidence_basis")
        if (
            not isinstance(basis, dict)
            or not basis.get("rationale")
            or not basis.get("reasoning")
            or not isinstance(basis.get("references"), list)
        ):
            raise ValueError(f"{case_id}: evidence basis must include rationale, reasoning, and references")
        authority_status = basis.get("authority_review_status")
        if authority_status not in AUTHORITY_REVIEW_STATUSES:
            raise ValueError(f"{case_id}: authoritative-document review status must be explicit")
        sources = basis.get("authoritative_sources")
        if not isinstance(sources, list):
            raise ValueError(f"{case_id}: authoritative_sources must be a list")
        for source in sources:
            if (
                not isinstance(source, dict)
                or not isinstance(source.get("url"), str)
                or not source["url"].startswith("https://")
                or not isinstance(source.get("purpose"), str)
                or not source["purpose"].strip()
            ):
                raise ValueError(f"{case_id}: authoritative sources need an HTTPS URL and review purpose")
        source_validation_status = basis.get("source_validation_status")
        if source_validation_status not in SOURCE_VALIDATION_STATUSES:
            raise ValueError(f"{case_id}: source evidence validation status must be explicit")
        if not basis["references"] and source_validation_status != "no_source_evidence_reference":
            raise ValueError(f"{case_id}: cases without source citations must be flagged as unverifiable")
        if basis["references"] and source_validation_status == "no_source_evidence_reference":
            raise ValueError(f"{case_id}: cited source evidence must be validated against its fixture or revision")
        if basis["references"]:
            expected_source_status = {
                "synthetic": "fixture_excerpt_checked_by_runner",
                "git": "revision_excerpt_checked_by_runner",
            }.get(case.get("fixture", {}).get("kind"))
            if source_validation_status != expected_source_status:
                raise ValueError(f"{case_id}: source validation status does not match its fixture type")
        if case["label_status"] == "reviewed":
            review = case.get("label_review")
            if (
                authority_status != "independently_reviewed"
                or not case["evidence_basis"]["references"]
                or not isinstance(review, dict)
                or not all(isinstance(review.get(field), str) and review[field].strip()
                           for field in ("reviewer", "reviewed_at", "decision"))
                or not any(
                    source.get("reviewed_excerpt")
                    for source in sources
                )
            ):
                raise ValueError(
                    f"{case_id}: reviewed labels require cited source evidence, an independent review record, "
                    "and a reviewed authoritative-document excerpt"
                )
        if any(
            str(key).casefold() in {
                "predicted",
                "prediction",
                "predicted_verdict",
                "actual_prediction",
                "prediction_source",
            }
            for key in _nested_keys(case)
        ):
            raise ValueError(f"{case_id}: prediction data must not be stored with expected labels")

    return cases


def _nested_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _nested_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _nested_keys(child)


def _label_review_flags(case: dict) -> list:
    flags = []
    if case["label_status"] != "reviewed":
        flags.append("label_not_independently_reviewed")
    basis = case["evidence_basis"]
    if basis["authority_review_status"] != "independently_reviewed":
        flags.append("authoritative_documentation_not_independently_reviewed")
    if not basis["references"]:
        flags.append("no_source_evidence_reference")
    return flags


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _reproducibility_metadata(dataset_path: Path, fixtures_path: Path, repo_root: Path) -> dict:
    runner_path = Path(__file__).resolve()
    verifier_path = Path(main.__file__).resolve()
    revision_result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    status_result = subprocess.run(
        ["git", "status", "--porcelain", "--", "main.py", "benchmarks/run_benchmark.py"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    revision_available = revision_result.returncode == 0
    status_available = status_result.returncode == 0
    return {
        "python_version": platform.python_version(),
        "repository_revision": revision_result.stdout.strip() if revision_available else None,
        "repository_revision_status": "available" if revision_available else "unavailable",
        "verifier_worktree_status": (
            ("dirty" if status_result.stdout.strip() else "clean")
            if status_available else "unavailable"
        ),
        "sha256": {
            "dataset": _sha256_file(dataset_path),
            "fixtures": _sha256_file(fixtures_path),
            "verifier": _sha256_file(verifier_path),
            "benchmark_runner": _sha256_file(runner_path),
        },
    }


def _heuristic_prediction(case: dict, files: Dict[str, str]) -> dict:
    request = main.AuditRequest(
        repo_url="https://github.com/benchmark/fixture",
        claim=case["claim"],
    )
    snapshot = {
        "metadata": {"owner": "benchmark", "repo": case["id"], "stars": 0, "language": "Unknown"},
        "files": files,
    }
    report = main.build_heuristic_audit(request, snapshot)
    for assertion in report.claim_breakdown:
        if assertion.claimed_feature == case["target_assertion"]:
            return {
                "verdict": assertion.verification_verdict,
                "evidence_file": assertion.evidence_file,
                "evidence_lines": assertion.evidence_lines,
                "analysis_engine": "heuristic",
                "fallback_reason": None,
            }
    raise ValueError(
        f"{case['id']}: target assertion {case['target_assertion']!r} was not extracted from the claim"
    )


def _llm_prediction(case: dict, files: Dict[str, str], provider: str, api_key: str) -> dict:
    request = main.AuditRequest(
        repo_url="https://github.com/benchmark/fixture",
        claim=case["claim"],
        llm_provider=provider,
    )
    snapshot = {
        "metadata": {"owner": "benchmark", "repo": case["id"], "stars": 0, "language": "Unknown"},
        "files": files,
    }
    baseline = main.build_heuristic_audit(request, snapshot)
    try:
        report = main.build_llm_audit(request, snapshot, baseline, provider, api_key)
        engine = report.repo_metadata.analysis_engine
        fallback_reason = None
    except (
        RuntimeError,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        main.ValidationError,
        main.requests.RequestException,
    ) as exc:
        report = baseline
        engine = "heuristic"
        fallback_reason = main.provider_fallback_reason(exc)

    for assertion in report.claim_breakdown:
        if assertion.claimed_feature == case["target_assertion"]:
            return {
                "verdict": assertion.verification_verdict,
                "evidence_file": assertion.evidence_file,
                "evidence_lines": assertion.evidence_lines,
                "analysis_engine": engine,
                "fallback_reason": fallback_reason,
            }
    raise ValueError(
        f"{case['id']}: target assertion {case['target_assertion']!r} was not extracted from the claim"
    )


def _aggregate_metrics(cases: list, results: list) -> dict:
    confusion = {actual: {predicted: 0 for predicted in VERDICTS} for actual in VERDICTS}
    for case, result in zip(cases, results):
        confusion[case["expected_verdict"]][result["predicted"]] += 1

    per_class = {}
    recalls = []
    for label in VERDICTS:
        true_positive = confusion[label][label]
        false_positive = sum(confusion[actual][label] for actual in VERDICTS if actual != label)
        false_negative = sum(confusion[label][predicted] for predicted in VERDICTS if predicted != label)
        precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
        recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {
            "support": sum(confusion[label].values()),
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
        if per_class[label]["support"]:
            recalls.append(recall)

    correct = sum(case["expected_verdict"] == result["predicted"] for case, result in zip(cases, results))
    false_positives = [
        result["id"] for case, result in zip(cases, results)
        if case["expected_verdict"] != "SUPPORTED" and result["predicted"] == "SUPPORTED"
    ]
    false_negatives = [
        result["id"] for case, result in zip(cases, results)
        if case["expected_verdict"] == "SUPPORTED" and result["predicted"] != "SUPPORTED"
    ]
    citations = [result for result in results if result["citation_present"]]
    valid_citations = sum(result["citation_valid"] for result in citations)
    return {
        "confusion_matrix": confusion,
        "per_class": per_class,
        "overall_accuracy": correct / len(cases) if cases else None,
        "balanced_accuracy": sum(recalls) / len(recalls) if recalls else None,
        "balanced_accuracy_classes_present": len(recalls),
        "false_positive_supported_cases": false_positives,
        "false_negative_supported_cases": false_negatives,
        "abstention_rate": sum(result["predicted"] == "INSUFFICIENT_EVIDENCE" for result in results) / len(results)
        if results else None,
        "citation_correctness": {
            "valid": valid_citations,
            "cited": len(citations),
            "rate": valid_citations / len(citations) if citations else None,
        },
    }


def _class_metrics(cases: list, results: list) -> dict:
    reviewed = [
        (case, result) for case, result in zip(cases, results)
        if case["label_status"] == "reviewed"
    ]
    unreviewed = [
        (case, result) for case, result in zip(cases, results)
        if case["label_status"] != "reviewed"
    ]
    reviewed_cases = [pair[0] for pair in reviewed]
    reviewed_results = [pair[1] for pair in reviewed]
    unreviewed_cases = [pair[0] for pair in unreviewed]
    unreviewed_results = [pair[1] for pair in unreviewed]
    reviewed_metrics = _aggregate_metrics(reviewed_cases, reviewed_results) if reviewed else None
    provisional_metrics = _aggregate_metrics(unreviewed_cases, unreviewed_results) if unreviewed else None
    return {
        "reviewed_ground_truth_metrics": reviewed_metrics,
        "provisional_or_unreviewed_label_metrics": provisional_metrics,
        "provisional_or_unreviewed_label_agreement": (
            {
                "case_count": len(unreviewed),
                "agreements": sum(case["expected_verdict"] == result["predicted"] for case, result in unreviewed),
                "rate": provisional_metrics["overall_accuracy"],
                "warning": "Agreement with provisional/unreviewed labels is not validated accuracy.",
            }
            if unreviewed else None
        ),
    }


def _evaluate_mode(cases: list, files_by_id: dict, predictor: Callable) -> dict:
    results = []
    for case in cases:
        prediction = predictor(case, files_by_id[case["id"]])
        if isinstance(prediction, str):
            prediction = {"verdict": prediction}
        predicted = prediction.get("verdict")
        if predicted not in VERDICTS:
            raise ValueError(f"{case['id']}: predictor returned invalid verdict {predicted!r}")
        evidence_file = prediction.get("evidence_file")
        evidence_lines = prediction.get("evidence_lines")
        has_citation = bool(evidence_file or evidence_lines)
        citation_valid = (
            has_citation
            and main.citation_is_valid(evidence_file, evidence_lines, files_by_id[case["id"]])
        )
        results.append({
            "id": case["id"],
            "expected": case["expected_verdict"],
            "predicted": predicted,
            "label_status": case["label_status"],
            "fixture_kind": case["fixture"]["kind"],
            "repository_url": case["repository_url"],
            "repository_revision": case["repository_revision"],
            "claim": case["claim"],
            "target_assertion": case["target_assertion"],
            "analysis_engine": prediction.get("analysis_engine", "custom/test predictor"),
            "fallback_reason": prediction.get("fallback_reason"),
            "expected_reasoning": case["evidence_basis"]["reasoning"],
            "expected_evidence_references": case["evidence_basis"]["references"],
            "authoritative_sources": case["evidence_basis"]["authoritative_sources"],
            "version_assumptions": case["version_assumptions"],
            "source_evidence_validation": (
                "verified_against_fixture_or_revision"
                if case["evidence_basis"]["references"] else "not_verifiable_no_references"
            ),
            "authoritative_documentation_review": case["evidence_basis"]["authority_review_status"],
            "review_flags": _label_review_flags(case),
            "review_status": "reviewed_ground_truth" if not _label_review_flags(case) else "needs_review",
            "evidence_file": evidence_file,
            "evidence_lines": evidence_lines,
            "citation_present": has_citation,
            "citation_valid": bool(citation_valid),
            "match": case["expected_verdict"] == predicted,
        })
    return {"results": results, **_class_metrics(cases, results)}


def run_benchmark(
    dataset_path: Path,
    fixtures_path: Path,
    repo_root: Path,
    predictor: Optional[Callable[[dict, Dict[str, str]], str]] = None,
    mode: str = "heuristic",
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
) -> dict:
    dataset = _read_json(dataset_path)
    fixtures = _read_json(fixtures_path)
    cases = _validate_dataset(dataset)
    files_by_id = {}
    evidence_reference_count = 0
    fingerprints = set()
    for case in cases:
        files = _load_case_files(case, fixtures, repo_root)
        evidence_reference_count += _validate_evidence(case, files)
        normalized_claim = re.sub(r"[^\w]+", " ", case["claim"].casefold()).strip()
        normalized_target = re.sub(r"[^\w]+", " ", case["target_assertion"].casefold()).strip()
        fingerprint = (
            case["repository_url"],
            case["repository_revision"],
            normalized_claim,
            normalized_target,
            tuple(sorted(files.items())),
        )
        if fingerprint in fingerprints:
            raise ValueError(f"{case['id']}: duplicate benchmark case")
        fingerprints.add(fingerprint)
        files_by_id[case["id"]] = files

    if predictor is not None:
        mode = "test_predictor"
        predict = predictor
    elif mode == "heuristic":
        predict = _heuristic_prediction
    elif mode == "llm":
        if provider not in {"gemini", "openai"} or not api_key:
            raise ValueError("LLM mode requires a provider and API key; no key was found or supplied.")
        predict = lambda case, files: _llm_prediction(case, files, provider, api_key)
    else:
        raise ValueError(f"Unsupported benchmark mode {mode!r}")

    report = _evaluate_mode(cases, files_by_id, predict)
    statuses = {status: sum(case["label_status"] == status for case in cases) for status in sorted(LABEL_STATUSES)}
    mismatches = [result for result in report["results"] if not result["match"]]
    flagged_results = [result for result in report["results"] if result["review_flags"]]
    return {
        "schema_version": 3,
        "mode": mode,
        "provider": provider if mode == "llm" else None,
        "dataset_status": dataset.get("dataset_status"),
        "warning": "Only labels explicitly marked reviewed are ground truth; all other metrics describe agreement with provisional or unreviewed labels.",
        "case_count": len(cases),
        "reviewed_case_count": statuses["reviewed"],
        "provisional_or_unreviewed_case_count": len(cases) - statuses["reviewed"],
        "label_status_counts": statuses,
        "label_review_summary": {
            "reviewed_ground_truth_case_count": statuses["reviewed"],
            "needs_review_case_count": len(flagged_results),
            "authoritative_documentation_reviewed_case_count": sum(
                result["authoritative_documentation_review"] == "independently_reviewed"
                for result in report["results"]
            ),
            "cases_needing_review": [
                {"id": result["id"], "flags": result["review_flags"]}
                for result in flagged_results
            ],
        },
        "dataset_evidence_reference_count": evidence_reference_count,
        "reproducibility": _reproducibility_metadata(dataset_path, fixtures_path, repo_root),
        "operational_scenarios": dataset.get("operational_scenarios", []),
        "results": report["results"],
        "mismatches": mismatches,
        "fallback_case_count": sum(result["fallback_reason"] is not None for result in report["results"]),
        **{key: value for key, value in report.items() if key != "results"},
    }


def main_cli() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path(__file__).with_name("cases.json"))
    parser.add_argument("--fixtures", type=Path, default=Path(__file__).with_name("fixtures.json"))
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--mode", choices=("heuristic", "llm"), default="heuristic")
    parser.add_argument("--provider", choices=("gemini", "openai"), help="LLM provider for explicit llm mode")
    parser.add_argument("--output", type=Path, help="Write JSON report to a new, non-existing path")
    args = parser.parse_args()

    provider = args.provider
    api_key = None
    if args.mode == "llm":
        if provider is None:
            provider = "gemini" if os.getenv("GEMINI_API_KEY") else "openai"
        api_key = os.getenv("GEMINI_API_KEY" if provider == "gemini" else "OPENAI_API_KEY")
    report = run_benchmark(
        args.dataset,
        args.fixtures,
        args.repo_root,
        mode=args.mode,
        provider=provider,
        api_key=api_key,
    )
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        output = args.output.resolve()
        if output in {args.dataset.resolve(), args.fixtures.resolve()}:
            raise SystemExit("Refusing to overwrite benchmark input data.")
        output.parent.mkdir(parents=True, exist_ok=True)
        _write_new_report(output, rendered)
    print(rendered, end="")


def _write_new_report(output: Path, rendered: str) -> None:
    try:
        with output.open("x", encoding="utf-8") as stream:
            stream.write(rendered)
    except FileExistsError as exc:
        raise FileExistsError(f"Refusing to overwrite existing report: {output}") from exc


if __name__ == "__main__":
    main_cli()
