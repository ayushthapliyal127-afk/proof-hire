import unittest

import main


def audit(claim, files, **kwargs):
    request = main.AuditRequest(
        repo_url="https://github.com/example/project",
        claim=claim,
    )
    snapshot = {
        "metadata": {"owner": "example", "repo": "project", "stars": 0, "language": "Python"},
        "files": files,
    }
    return main.build_heuristic_audit(request, snapshot, **kwargs)


class CredibilityScoringTests(unittest.TestCase):
    def test_supported_source_claim_scores_high_but_not_as_complete_proof(self):
        report = audit(
            "Built a FastAPI service.",
            {"main.py": "from fastapi import FastAPI\napp = FastAPI()\n"},
        )
        self.assertEqual(report.claim_breakdown[0].verification_verdict, "SUPPORTED")
        self.assertEqual(report.credibility_score, 90)
        self.assertIn("heuristic", report.summary.lower())
        self.assertIn("authorship", report.summary.lower())

    def test_partial_manifest_evidence_receives_revised_partial_credit(self):
        report = audit(
            "Used Redis.",
            {"requirements.txt": "redis==5.0.0\n"},
        )
        self.assertEqual(report.claim_breakdown[0].verification_verdict, "PARTIALLY_SUPPORTED")
        self.assertEqual(report.credibility_score, 32)

    def test_contradicted_assertion_scores_zero_without_changing_its_verdict(self):
        report = audit(
            "The service does not use Redis.",
            {
                "cache.py": (
                    "from redis import Redis\n"
                    "client = Redis.from_url(REDIS_URL)\n"
                    "client.get('health')\n"
                )
            },
        )
        self.assertEqual(report.claim_breakdown[0].verification_verdict, "CONTRADICTED")
        self.assertEqual(report.credibility_score, 0)

    def test_ambiguous_assertion_is_unresolved_not_contradicted(self):
        report = audit("Built a zero-latency global system.", {"main.py": "def run(): return True\n"})
        self.assertTrue(all(
            item.verification_verdict == "INSUFFICIENT_EVIDENCE"
            for item in report.claim_breakdown
        ))
        self.assertLess(report.credibility_score, 30)
        self.assertIn("remain unresolved", report.summary)

    def test_valid_citation_does_not_remove_truncated_repository_coverage_penalty(self):
        report = audit(
            "Built a FastAPI service.",
            {"main.py": "from fastapi import FastAPI\napp = FastAPI()\n"},
            scan_limits=["GitHub truncated the repository tree; some paths were omitted."],
        )
        self.assertEqual(report.claim_breakdown[0].verification_verdict, "SUPPORTED")
        self.assertEqual(report.credibility_score, 75)

    def test_valid_citation_does_not_remove_truncated_source_coverage_penalty(self):
        report = audit(
            "Built a FastAPI service.",
            {"main.py": "from fastapi import FastAPI\napp = FastAPI()\n"},
            warnings=["main.py was truncated to stay within the file-size limit."],
            scan_limits=["Only the first 400 lines were inspected."],
        )
        self.assertEqual(report.claim_breakdown[0].verification_verdict, "SUPPORTED")
        self.assertEqual(report.credibility_score, 75)

    def test_supported_documentation_citation_uses_documented_lower_weight(self):
        item = main.ClaimBreakdownItem(
            claimed_feature="Repository architecture",
            status="verified",
            verification_verdict="SUPPORTED",
            evidence_file="README.md",
            evidence_lines="2",
            explanation="The repository-level architecture is documented.",
        )
        score, rationale = main.calculate_credibility_score(
            [item],
            {"README.md": "# Overview\nService architecture overview.\n"},
            scan_limits=["Only the listed files were inspected."],
        )
        self.assertEqual(score, 50)
        self.assertIn("1/1 assertions have valid citations", rationale)

    def test_no_evidence_is_unresolved_not_contradicted(self):
        report = audit("Built a FastAPI service.", {})
        self.assertEqual(report.claim_breakdown[0].verification_verdict, "INSUFFICIENT_EVIDENCE")
        self.assertEqual(report.credibility_score, 10)

    def test_summary_counts_match_final_assertion_and_citation_records(self):
        report = audit(
            "Built a FastAPI service with Redis caching.",
            {
                "main.py": "from fastapi import FastAPI\napp = FastAPI()\n",
                "requirements.txt": "redis==5.0.0\n",
            },
        )
        self.assertIn("1 supported, 1 partially supported", report.summary)
        self.assertIn("1 unresolved assertions were averaged across 3 assertions", report.summary)
        self.assertIn("2/3 assertions have valid citations", report.summary)
        self.assertEqual(len(report.claim_breakdown), 3)

    def test_conflicting_positive_and_negated_assertions_both_reduce_score(self):
        report = audit(
            "The service uses Redis but does not use Redis.",
            {
                "cache.py": (
                    "from redis import Redis\n"
                    "client = Redis.from_url(REDIS_URL)\n"
                    "client.get('health')\n"
                )
            },
        )
        self.assertEqual(
            {item.claimed_feature: item.verification_verdict for item in report.claim_breakdown},
            {"Redis": "SUPPORTED", "Not Redis": "CONTRADICTED"},
        )
        self.assertEqual(report.credibility_score, 45)
        self.assertIn("Conflicting positive and negated assertions", report.summary)

    def test_invalid_citation_cannot_receive_supported_evidence_points(self):
        item = main.ClaimBreakdownItem(
            claimed_feature="FastAPI",
            status="verified",
            verification_verdict="SUPPORTED",
            evidence_file="missing.py",
            evidence_lines="1",
            explanation="Unsupported citation.",
        )
        score, rationale = main.calculate_credibility_score(
            [item],
            {"main.py": "app = FastAPI()\n"},
            scan_limits=[],
        )
        self.assertEqual(score, 20)
        self.assertIn("1 supporting/contradicting citations were absent or invalid", rationale)


if __name__ == "__main__":
    unittest.main()
