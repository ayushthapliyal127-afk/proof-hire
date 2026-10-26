# ProofHire claim-verification benchmark

This benchmark evaluates the existing verifier without changing production
behavior. `cases.json` stores expected labels and evidence provenance;
`fixtures.json` stores synthetic source files. The runner checks every cited
excerpt against the exact fixture or pinned local Git revision before
evaluation, detects duplicate cases, and never writes predictions to the
dataset.

## Reproducible commands

Run deterministic heuristic mode without credentials:

```powershell
python -m benchmarks.run_benchmark --mode heuristic
```

Run the mocked/unit tests:

```powershell
python -m unittest tests.test_benchmark_runner -v
```

LLM mode is explicit and may incur provider charges. It requires a configured
provider key and evaluates each case separately; transient provider failures
are recorded with the actual fallback reason:

```powershell
$env:GEMINI_API_KEY = "..."
python -m benchmarks.run_benchmark --mode llm --provider gemini
```

To save machine-readable output, pass a new path. Existing files and benchmark
input paths are never overwritten:

```powershell
python -m benchmarks.run_benchmark --mode heuristic --output benchmarks/reports/run-unique-name.json
```

Reports separate `reviewed_ground_truth_metrics` from agreement with
provisional/unreviewed labels. Class metrics include confusion matrix,
accuracy, balanced accuracy, per-class precision/recall/F1, supported-claim
false positives/negatives, abstention rate, and verifier-citation validity.
Per-case results include the actual prediction source, evidence citation,
fallback reason, expected rationale, and match status.

## Dataset limits and review state

Dataset schema version 2 contains 41 cases: 34 deterministic synthetic cases
marked `provisional_synthetic` and 7 cases backed by local revision-pinned
source marked `unreviewed_repository`. **There are zero independently reviewed
labels.** Synthetic examples test repeatable behavior, not real-world accuracy.
The source examples' expected excerpts are checked against their pinned Git
objects, but the repository origin is not configured and those labels have not
been independently validated. Their `repository_url` is therefore `null` with
an explicit unavailable-origin status; no URL is guessed.

`authoritative_sources` are review leads only. The runner does not assert that
documentation endorses an expected label; each case explicitly records that
authoritative review has not occurred. Version assumptions state that fixture
technology versions are not pinned and the verifier comes from the current
working tree. Reports include the dataset, fixture, verifier, and runner SHA-256
hashes plus the available Git revision and verifier worktree state to identify
the exact inputs and implementation used. Labels remain outside ground-truth
metrics until their source excerpt, independent review record, and excerpt from
an authoritative document have all been recorded.

The dataset includes compound assertions, wording variants, optional/dependency
only features, missing and truncated evidence, prompt-injection text, invalid
citation controls, and explicit mocked provider-failure scenarios. Provider
failures and fabricated citations are exercised without paid calls by
`tests.test_provider_integration` and benchmark-runner mocks. Metrics against
unreviewed labels are agreement only—not independently measured accuracy.
