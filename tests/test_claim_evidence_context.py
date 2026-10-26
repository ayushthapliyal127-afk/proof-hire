import unittest

import main


def audit_claim(claim, files):
    request = main.AuditRequest(
        repo_url="https://github.com/example/project",
        claim=claim,
    )
    snapshot = {
        "metadata": {"owner": "example", "repo": "project", "stars": 0, "language": "Python"},
        "files": files,
    }
    return main.build_heuristic_audit(request, snapshot)


class ClaimEvidenceContextTests(unittest.TestCase):
    def test_requests_import_and_relevant_call_supports_requests_claim(self):
        report = audit_claim(
            "Used Requests to retrieve remote JSON.",
            {
                "client.py": (
                    "import requests\n"
                    "response = requests.get('https://example.test/api', timeout=5)\n"
                )
            },
        )
        assertion = next(item for item in report.claim_breakdown if item.claimed_feature == "Requests")
        self.assertEqual(assertion.verification_verdict, "SUPPORTED")
        self.assertEqual(assertion.evidence_file, "client.py")
        self.assertEqual(assertion.evidence_lines, "2")

    def test_repository_requests_usage_is_supported(self):
        report = audit_claim(
            "The repository uses Requests for outbound HTTP calls.",
            {
                "main.py": (
                    "import requests\n"
                    "def fetch(url):\n"
                    "    response = requests.get(url, timeout=5)\n"
                    "    return response.json()\n"
                )
            },
        )
        assertion = next(item for item in report.claim_breakdown if item.claimed_feature == "Requests")
        self.assertEqual(assertion.verification_verdict, "SUPPORTED")
        self.assertEqual(assertion.evidence_lines, "3")

    def test_requests_library_import_without_call_is_partial(self):
        report = audit_claim(
            "Used Requests for outbound HTTP calls.",
            {"client.py": "import requests\n"},
        )
        assertion = next(item for item in report.claim_breakdown if item.claimed_feature == "Requests")
        self.assertEqual(assertion.verification_verdict, "PARTIALLY_SUPPORTED")

    def test_requests_package_manifest_alone_is_not_active_implementation(self):
        report = audit_claim(
            "Used Requests for outbound HTTP calls.",
            {"requirements.txt": "requests==2.32.0\n"},
        )
        assertion = next(item for item in report.claim_breakdown if item.claimed_feature == "Requests")
        self.assertEqual(assertion.verification_verdict, "PARTIALLY_SUPPORTED")

    def test_requests_upstream_api_definition_is_supported(self):
        report = audit_claim(
            "Built the Requests library.",
            {
                "src/requests/api.py": (
                    "def request(method, url, **kwargs):\n"
                    "    return Session().request(method=method, url=url, **kwargs)\n"
                )
            },
        )
        assertion = next(item for item in report.claim_breakdown if item.claimed_feature == "Requests")
        self.assertEqual(assertion.verification_verdict, "SUPPORTED")
        self.assertEqual(assertion.evidence_file, "src/requests/api.py")
        self.assertEqual(assertion.evidence_lines, "1")

    def test_upstream_framework_definitions_are_supported(self):
        cases = [
            ("Built FastAPI.", "src/fastapi/applications.py", "class FastAPI:\n    pass\n", "FastAPI"),
            ("Built Flask.", "src/flask/app.py", "class Flask:\n    pass\n", "Flask"),
            ("Built a REST API.", "src/fastapi/routing.py", "class APIRouter:\n    pass\n", "REST API"),
        ]
        for claim, path, source, expected_feature in cases:
            with self.subTest(feature=expected_feature):
                report = audit_claim(claim, {path: source})
                assertion = next(
                    item for item in report.claim_breakdown
                    if item.claimed_feature == expected_feature
                )
                self.assertEqual(assertion.verification_verdict, "SUPPORTED")

    def test_feature_extraction_does_not_emit_descriptive_claim_fragments(self):
        self.assertEqual(
            main.extract_claimed_features(
                "Developed a lightweight modern web application using Flask."
            ),
            ["Flask"],
        )
        self.assertEqual(
            main.extract_claimed_features("Built a Flask application with WSGI support."),
            ["Flask", "WSGI"],
        )

    def test_requests_call_without_requests_import_is_not_supported(self):
        report = audit_claim(
            "Used Requests for outbound HTTP calls.",
            {"client.py": "response = requests.get(url)\n"},
        )
        assertion = next(item for item in report.claim_breakdown if item.claimed_feature == "Requests")
        self.assertEqual(assertion.verification_verdict, "INSUFFICIENT_EVIDENCE")

    def test_pytorch_suggestion_string_is_not_active_implementation(self):
        report = audit_claim(
            "The project trains models using PyTorch.",
            {"suggestions.py": 'FIX = "optimizer.zero_grad(); loss.backward(); optimizer.step()"\n'},
        )
        assertion = next(item for item in report.claim_breakdown if item.claimed_feature == "PyTorch")
        self.assertEqual(assertion.verification_verdict, "INSUFFICIENT_EVIDENCE")

    def test_redis_suggestion_string_is_not_active_implementation(self):
        report = audit_claim(
            "The project uses Redis caching.",
            {"suggestions.py": 'FIX = "cache = Redis.from_url(REDIS_URL)"\n'},
        )
        assertion = next(item for item in report.claim_breakdown if item.claimed_feature == "Redis")
        self.assertEqual(assertion.verification_verdict, "INSUFFICIENT_EVIDENCE")

    def test_package_manifest_does_not_prove_redis_use(self):
        report = audit_claim(
            "The project uses Redis caching.",
            {"requirements.txt": "redis==5.0.0\n"},
        )
        assertion = next(item for item in report.claim_breakdown if item.claimed_feature == "Redis")
        self.assertEqual(assertion.verification_verdict, "PARTIALLY_SUPPORTED")

    def test_generic_requests_call_does_not_prove_rest_api(self):
        report = audit_claim(
            "Built a REST API.",
            {"client.py": "import requests\nresponse = requests.get(url)\n"},
        )
        assertion = next(item for item in report.claim_breakdown if item.claimed_feature == "REST API")
        self.assertEqual(assertion.verification_verdict, "INSUFFICIENT_EVIDENCE")

    def test_comments_and_docstrings_do_not_establish_redis_or_torch(self):
        report = audit_claim(
            "Used Redis and PyTorch.",
            {
                "notes.py": (
                    "# Redis.from_url(REDIS_URL)\n"
                    '"""loss.backward(); optimizer.step()"""\n'
                    "def noop():\n"
                    "    return None\n"
                )
            },
        )
        assertions = {item.claimed_feature: item for item in report.claim_breakdown}
        self.assertEqual(assertions["Redis"].verification_verdict, "INSUFFICIENT_EVIDENCE")
        self.assertEqual(assertions["PyTorch"].verification_verdict, "INSUFFICIENT_EVIDENCE")

    def test_redis_expression_without_redis_binding_is_not_supported(self):
        report = audit_claim(
            "The project uses Redis caching.",
            {"cache.py": "client = Redis.from_url(REDIS_URL)\n"},
        )
        assertion = next(item for item in report.claim_breakdown if item.claimed_feature == "Redis")
        self.assertEqual(assertion.verification_verdict, "INSUFFICIENT_EVIDENCE")

    def test_genuine_redis_import_and_client_calls_are_supported(self):
        report = audit_claim(
            "The project uses Redis caching.",
            {
                "cache.py": (
                    "from redis import Redis\n"
                    "client = Redis.from_url(REDIS_URL)\n"
                    "client.set('health', 'ok')\n"
                )
            },
        )
        assertion = next(item for item in report.claim_breakdown if item.claimed_feature == "Redis")
        self.assertEqual(assertion.verification_verdict, "SUPPORTED")
        self.assertEqual(assertion.evidence_file, "cache.py")
        self.assertEqual(assertion.evidence_lines, "2")

    def test_redis_cache_aside_implementation_supports_caching_claim(self):
        report = audit_claim(
            "The project uses Redis caching.",
            {
                "cache.py": (
                    "from redis import Redis\n"
                    "client = Redis.from_url(REDIS_URL)\n"
                    "def get_user(user_id):\n"
                    "    key = f'user:{user_id}'\n"
                    "    cached = client.get(key)\n"
                    "    if cached:\n"
                    "        return cached\n"
                    "    user = load_user(user_id)\n"
                    "    client.set(key, user, ex=300)\n"
                    "    return user\n"
                )
            },
        )
        assertions = {item.claimed_feature: item for item in report.claim_breakdown}
        self.assertEqual(assertions["Redis"].verification_verdict, "SUPPORTED")
        self.assertEqual(assertions["caching"].verification_verdict, "SUPPORTED")
        self.assertEqual(assertions["caching"].evidence_file, "cache.py")
        self.assertEqual(assertions["caching"].evidence_lines, "9")

    def test_redis_get_and_set_on_different_keys_do_not_prove_caching(self):
        report = audit_claim(
            "The project uses Redis caching.",
            {
                "store.py": (
                    "from redis import Redis\n"
                    "client = Redis.from_url(REDIS_URL)\n"
                    "def load_record(record_id):\n"
                    "    client.get(record_id)\n"
                    "    client.set('last-record', record_id)\n"
                )
            },
        )
        assertions = {item.claimed_feature: item for item in report.claim_breakdown}
        self.assertEqual(assertions["Redis"].verification_verdict, "SUPPORTED")
        self.assertEqual(assertions["caching"].verification_verdict, "INSUFFICIENT_EVIDENCE")

    def test_generic_optimizer_methods_without_torch_binding_are_not_supported(self):
        report = audit_claim(
            "The project trains models using PyTorch.",
            {
                "train.py": (
                    "optimizer.zero_grad()\n"
                    "loss.backward()\n"
                    "optimizer.step()\n"
                )
            },
        )
        assertion = next(item for item in report.claim_breakdown if item.claimed_feature == "PyTorch")
        self.assertEqual(assertion.verification_verdict, "INSUFFICIENT_EVIDENCE")

    def test_genuine_torch_import_and_tensor_operation_are_supported(self):
        report = audit_claim(
            "The project trains models using PyTorch.",
            {
                "train.py": (
                    "import torch\n"
                    "loss = torch.tensor(1.0, requires_grad=True)\n"
                    "loss.backward()\n"
                    "optimizer.step()\n"
                )
            },
        )
        assertion = next(item for item in report.claim_breakdown if item.claimed_feature == "PyTorch")
        self.assertEqual(assertion.verification_verdict, "SUPPORTED")
        self.assertEqual(assertion.evidence_file, "train.py")
        self.assertEqual(assertion.evidence_lines, "2")

    def test_generic_feature_is_supported_by_strong_executable_source_tokens(self):
        report = audit_claim(
            "Built a payment reconciliation pipeline.",
            {"billing.py": "def payment_reconciliation_pipeline(invoice, payment):\n    return invoice == payment\n"},
        )
        assertion = report.claim_breakdown[0]
        self.assertEqual(assertion.claimed_feature, "payment reconciliation pipeline")
        self.assertEqual(assertion.verification_verdict, "SUPPORTED")
        self.assertEqual(assertion.evidence_file, "billing.py")

    def test_generic_feature_in_readme_is_verified(self):
        report = audit_claim(
            "Built a payment reconciliation pipeline.",
            {"README.md": "# Payment reconciliation pipeline\n"},
        )
        assertion = report.claim_breakdown[0]
        self.assertEqual(assertion.verification_verdict, "SUPPORTED")
        self.assertEqual(assertion.evidence_file, "README.md")
        self.assertEqual(assertion.evidence_lines, "1")

    def test_generic_claim_matches_across_five_line_source_window_and_docstrings(self):
        report = audit_claim(
            "Built a text-to-handwriting renderer.",
            {
                "renderer.py": (
                    '"""Text rendering subsystem.\n'
                    "It converts plain text into handwriting output.\n"
                    '"""\n'
                    "def render(value):\n"
                    "    return value\n"
                )
            },
        )
        assertion = report.claim_breakdown[0]
        self.assertEqual(assertion.verification_verdict, "SUPPORTED")
        self.assertEqual(assertion.evidence_file, "renderer.py")

    def test_generic_manifest_metadata_can_verify_a_claim(self):
        report = audit_claim(
            "Built a text-to-handwriting renderer.",
            {
                "pyproject.toml": (
                    '[project]\n'
                    'name = "text-to-handwriting"\n'
                    'description = "Convert text to handwriting output"\n'
                )
            },
        )
        assertion = report.claim_breakdown[0]
        self.assertEqual(assertion.verification_verdict, "SUPPORTED")
        self.assertEqual(assertion.evidence_file, "pyproject.toml")

    def test_source_priority_deprioritizes_examples_and_prefers_core_files(self):
        self.assertGreater(
            main.source_priority("docs/main.py")[0],
            main.source_priority("src/main.py")[0],
        )
        self.assertGreater(
            main.source_priority("examples/app.py")[0],
            main.source_priority("src/app.py")[0],
        )

    def test_added_web_source_extensions_are_scanned(self):
        self.assertTrue(all(
            extension in main.SOURCE_EXTENSIONS
            for extension in (".html", ".htm", ".css", ".scss", ".vue", ".svelte")
        ))
        report = audit_claim(
            "Built a payment reconciliation pipeline.",
            {"src/App.vue": "<template><payment-reconciliation-pipeline /></template>\n"},
        )
        self.assertEqual(report.claim_breakdown[0].verification_verdict, "SUPPORTED")
        self.assertEqual(report.claim_breakdown[0].evidence_file, "src/App.vue")


if __name__ == "__main__":
    unittest.main()
