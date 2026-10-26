import json
import unittest
from unittest.mock import patch

import main


def make_request(claim):
    return main.AuditRequest(
        repo_url="https://github.com/example/project",
        claim=claim,
    )


def make_snapshot(files):
    return {
        "metadata": {"owner": "example", "repo": "project", "stars": 0, "language": "Python"},
        "files": files,
    }


class ClaimVerificationTests(unittest.TestCase):
    def analyze(self, claim, files, **kwargs):
        return main.build_heuristic_audit(
            make_request(claim),
            make_snapshot(files),
            **kwargs,
        )

    def test_supported_claim_has_grounded_source_evidence(self):
        source = "from fastapi import FastAPI\napp = FastAPI()\n"
        report = self.analyze(
            "Built a FastAPI service.",
            {"main.py": source},
        )
        assertion = report.claim_breakdown[0]
        self.assertEqual(assertion.verification_verdict, "SUPPORTED")
        self.assertEqual(assertion.evidence_file, "main.py")
        self.assertEqual(assertion.evidence_lines, "2")
        citation = main.cited_excerpt(assertion.evidence_file, assertion.evidence_lines, {"main.py": source})
        self.assertEqual(citation, "2: app = FastAPI()")
        self.assertEqual(citation.split(": ", 1)[1], source.splitlines()[1])

    def test_missing_and_scan_placeholder_are_not_valid_source_citations(self):
        files = {"main.py": "from fastapi import FastAPI\napp = FastAPI()\n"}
        self.assertFalse(main.citation_is_valid(None, None, files))
        self.assertFalse(main.citation_is_valid("Repository scan", "N/A", files))
        self.assertFalse(main.citation_is_valid("main.py", "N/A", files))
        self.assertFalse(main.citation_is_valid("main.py", "1-3", files))
        self.assertFalse(main.citation_is_valid(["main.py"], "2", files))

    def test_explicitly_negated_claim_is_contradicted_by_source(self):
        report = self.analyze(
            "The service does not use Redis.",
            {
                "cache.py": (
                    "from redis import Redis\n"
                    "client = Redis.from_url(REDIS_URL)\n"
                    "client.get('health')\n"
                )
            },
        )
        assertion = report.claim_breakdown[0]
        self.assertEqual(assertion.verification_verdict, "CONTRADICTED")
        self.assertEqual(assertion.status, "missing")
        self.assertEqual(assertion.evidence_file, "cache.py")

    def test_compound_claim_keeps_partially_supported_assertions(self):
        report = self.analyze(
            "Built a FastAPI service with Redis caching.",
            {
                "main.py": "from fastapi import FastAPI\napp = FastAPI()\n",
                "requirements.txt": "redis==5.0.0\n",
            },
        )
        by_feature = {item.claimed_feature: item for item in report.claim_breakdown}
        self.assertEqual(by_feature["FastAPI"].verification_verdict, "SUPPORTED")
        self.assertEqual(by_feature["Redis"].verification_verdict, "PARTIALLY_SUPPORTED")
        self.assertEqual(by_feature["caching"].verification_verdict, "INSUFFICIENT_EVIDENCE")

    def test_claim_decomposition_preserves_context_and_avoids_keyword_false_positives(self):
        claim = (
            "Built a FastAPI backend with Redis caching and JWT authentication for secure, scalable requests."
        )
        assertions = main.extract_claimed_features(claim)
        self.assertEqual(
            [feature for feature in assertions if feature in {"FastAPI", "Redis", "caching", "JWT", "scalability"}],
            ["FastAPI", "Redis", "caching", "JWT", "scalability"],
        )
        self.assertIn("authentication for secure", assertions)
        self.assertNotIn("Requests", assertions)
        self.assertNotIn("scalability", main.extract_claimed_features(
            "Designed a production-scale Express API."
        ))

        report = self.analyze(claim, {"main.py": "app = FastAPI()\n"})
        self.assertTrue(all(item.source_claim == claim for item in report.claim_breakdown))

    def test_ambiguous_claim_is_insufficient_not_contradicted(self):
        report = self.analyze("Built a zero-latency global system.", {"main.py": "def run():\n    return True\n"})
        self.assertTrue(report.claim_breakdown)
        self.assertTrue(
            all(item.verification_verdict == "INSUFFICIENT_EVIDENCE" for item in report.claim_breakdown)
        )
        self.assertTrue(all(item.status == "partial" for item in report.claim_breakdown))
        self.assertTrue(all(item.evidence_file is None and item.evidence_lines is None for item in report.claim_breakdown))

    def test_flask_claim_matches_flask_routes_and_rest_api(self):
        report = self.analyze(
            "Built a Flask REST API with route handlers.",
            {
                "app.py": (
                    "from flask import Flask as WebApp\n"
                    "application = WebApp(__name__)\n"
                    "@application.get('/health')\n"
                    "def health(): return {'ok': True}\n"
                )
            },
        )
        self.assertEqual(
            {item.claimed_feature: item.verification_verdict for item in report.claim_breakdown},
            {"Flask": "SUPPORTED", "REST API": "SUPPORTED"},
        )

    def test_not_only_compound_claim_keeps_both_frameworks_positive(self):
        report = self.analyze(
            "The service uses not only FastAPI but also Flask.",
            {
                "fastapi_app.py": "from fastapi import FastAPI\napp = FastAPI()\n",
                "flask_app.py": "from flask import Flask\napp = Flask(__name__)\n",
            },
        )
        self.assertEqual(
            {item.claimed_feature: item.verification_verdict for item in report.claim_breakdown},
            {"FastAPI": "SUPPORTED", "Flask": "SUPPORTED"},
        )

    def test_negated_and_positive_compound_assertions_have_correct_scope(self):
        report = self.analyze(
            "The service does not use Redis but uses JWT.",
            {
                "cache.py": (
                    "from redis import Redis\n"
                    "client = Redis.from_url(REDIS_URL)\n"
                    "client.set('health', 'ok')\n"
                ),
                "auth.py": (
                    "from jose import jwt\n"
                    "token = jwt.encode({'sub': user_id}, SECRET, algorithm='HS256')\n"
                ),
            },
        )
        self.assertEqual(
            {item.claimed_feature: item.verification_verdict for item in report.claim_breakdown},
            {"Not Redis": "CONTRADICTED", "JWT": "SUPPORTED"},
        )

    def test_exaggerated_assertions_are_not_omitted_from_score(self):
        report = self.analyze(
            "Built a FastAPI system with quantum teleportation, zero latency, and unbreakable security.",
            {"main.py": "from fastapi import FastAPI\napp = FastAPI()\n"},
        )
        self.assertIn("FastAPI", {item.claimed_feature for item in report.claim_breakdown})
        unresolved = [item for item in report.claim_breakdown if item.verification_verdict == "INSUFFICIENT_EVIDENCE"]
        self.assertGreaterEqual(len(unresolved), 3)
        self.assertLess(report.credibility_score, 100)

    def test_omitted_or_truncated_files_remain_unresolved(self):
        omitted = self.analyze(
            "Built a Flask service.",
            {},
            scan_limits=["The repository tree was truncated; some paths were omitted."],
        )
        self.assertEqual(omitted.claim_breakdown[0].verification_verdict, "INSUFFICIENT_EVIDENCE")
        self.assertIsNone(omitted.claim_breakdown[0].evidence_file)

        payload = ("\n".join(["# filler"] * main.MAX_FILE_LINES + ["app = Flask(__name__)"])).encode()

        class Response:
            status_code = 200
            headers = {}
            content = payload

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return None

            def iter_content(self, chunk_size):
                return iter([self.content])

        with patch.object(main.requests, "get", return_value=Response()):
            content, truncated, warning = main.download_text_file("https://example.test/source.py")
        self.assertIsNone(warning)
        self.assertTrue(truncated)
        self.assertEqual(len(content.splitlines()), main.MAX_FILE_LINES)

        truncated_report = self.analyze(
            "Built a Flask service.",
            {"app.py": content},
            warnings=["app.py was truncated to stay within the file-size/line limit."],
            scan_limits=["Only the first 400 lines were inspected."],
        )
        self.assertEqual(truncated_report.claim_breakdown[0].verification_verdict, "INSUFFICIENT_EVIDENCE")

    def test_flask_route_does_not_verify_express_claim(self):
        report = self.analyze(
            "Built an Express API.",
            {
                "app.py": (
                    "from flask import Flask\n"
                    "app = Flask(__name__)\n"
                    "@app.get('/health')\n"
                    "def health(): return 'ok'\n"
                )
            },
        )
        self.assertEqual(report.claim_breakdown[0].verification_verdict, "INSUFFICIENT_EVIDENCE")

    def test_invalid_or_missing_llm_claim_citation_uses_heuristic_citation(self):
        request = make_request("Built a FastAPI service.")
        snapshot = make_snapshot({"main.py": "from fastapi import FastAPI\napp = FastAPI()\n"})
        baseline = main.build_heuristic_audit(request, snapshot)
        invalid_response = {
            "summary": "FastAPI is present.",
            "claim_breakdown": [{
                "claimed_feature": "FastAPI",
                "status": "verified",
                "evidence_file": "missing.py",
                "evidence_lines": "2",
                "explanation": "Evidence.",
            }],
            "findings": [],
            "viva_questions": [{
                "id": index,
                "file": "main.py",
                "line_range": "2",
                "difficulty": "Foundational",
                "question": "Explain the application.",
                "why_asked": "Verify understanding.",
                "expected_concepts": ["FastAPI"],
                "code_context": "",
                "refactored_fix_snippet": "",
            } for index in range(1, 4)],
        }
        valid_response = json.loads(json.dumps(invalid_response))
        valid_response["claim_breakdown"][0]["evidence_file"] = "main.py"
        with patch.object(main, "call_llm", return_value=json.dumps(valid_response)):
            llm_report = main.build_llm_audit(request, snapshot, baseline, "gemini", "test-key")
        self.assertEqual(llm_report.claim_breakdown[0].verification_verdict, "SUPPORTED")
        self.assertEqual(llm_report.claim_breakdown[0].evidence_lines, "2")

        with patch.object(main, "call_llm", return_value=json.dumps(invalid_response)):
            llm_report = main.build_llm_audit(request, snapshot, baseline, "gemini", "test-key")
        self.assertEqual(llm_report.claim_breakdown[0].evidence_file, "main.py")
        self.assertEqual(llm_report.claim_breakdown[0].evidence_lines, "2")

        missing_response = json.loads(json.dumps(valid_response))
        missing_response["claim_breakdown"][0]["evidence_file"] = None
        missing_response["claim_breakdown"][0]["evidence_lines"] = None
        with patch.object(main, "call_llm", return_value=json.dumps(missing_response)):
            llm_report = main.build_llm_audit(request, snapshot, baseline, "gemini", "test-key")
        self.assertEqual(llm_report.claim_breakdown[0].evidence_file, "main.py")
        self.assertEqual(llm_report.claim_breakdown[0].evidence_lines, "2")

    def test_missing_claim_features_falls_back_to_extracted_assertions(self):
        request = make_request("Built a FastAPI service with Redis caching.")
        snapshot = make_snapshot({
            "main.py": "from fastapi import FastAPI\napp = FastAPI()\n",
            "requirements.txt": "redis==5.0.0\n",
        })
        baseline = main.build_heuristic_audit(request, snapshot)
        response = {
            "summary": "The assertions were checked against the inspected files.",
            "claim_breakdown": [{
                "claimed_feature": "API",
                "status": "missing",
                "evidence_file": None,
                "evidence_lines": None,
                "explanation": "Fallback should use extracted claim assertions.",
            }],
            "findings": [],
            "viva_questions": [{
                "id": index,
                "file": "main.py",
                "line_range": "2",
                "difficulty": "Foundational",
                "question": "Explain the implementation.",
                "why_asked": "Connect the claim to source evidence.",
                "expected_concepts": ["implementation evidence"],
                "code_context": "",
                "refactored_fix_snippet": "",
            } for index in range(1, 4)],
        }
        with patch.object(main, "call_llm", return_value=json.dumps(response)):
            report = main.build_llm_audit(request, snapshot, baseline, "gemini", "test-key")

        self.assertEqual(
            [item.claimed_feature for item in report.claim_breakdown],
            main.extract_claimed_features(request.claim),
        )

    def test_llm_partial_verdict_without_citation_is_not_accepted(self):
        request = make_request("Built a quantum teleporter.")
        snapshot = make_snapshot({"main.py": "def run():\n    return True\n"})
        baseline = main.build_heuristic_audit(request, snapshot)
        response = {
            "summary": "Every assertion is fully supported.",
            "claim_breakdown": [{
                "claimed_feature": baseline.claim_breakdown[0].claimed_feature,
                "status": "partial",
                "evidence_file": None,
                "evidence_lines": None,
                "explanation": "No relevant implementation evidence was found.",
            }],
            "findings": [],
            "viva_questions": [{
                "id": index,
                "file": "main.py",
                "line_range": "1",
                "difficulty": "Foundational",
                "question": "What code would substantiate the claim?",
                "why_asked": "Connect the claim to source evidence.",
                "expected_concepts": ["implementation evidence"],
                "code_context": "",
                "refactored_fix_snippet": "",
            } for index in range(1, 4)],
        }
        with patch.object(main, "call_llm", return_value=json.dumps(response)):
            report = main.build_llm_audit(request, snapshot, baseline, "gemini", "test-key")
        self.assertEqual(report.claim_breakdown[0].verification_verdict, "INSUFFICIENT_EVIDENCE")
        self.assertIsNone(report.claim_breakdown[0].evidence_file)
        self.assertIsNone(report.claim_breakdown[0].evidence_lines)
        self.assertFalse(report.summary.startswith("Every assertion is fully supported."))
        self.assertIn("Score rationale", report.summary)


if __name__ == "__main__":
    unittest.main()
