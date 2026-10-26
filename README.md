# ProofHire AI

**Evidence-Driven Technical Claim & GitHub Repository Auditor — “Proof, not promises.”**

## Demo Video

**Submission video:** _Add the public demo-video link here before submitting._

ProofHire cross-examines a technical resume claim against a bounded set of source files from a public GitHub repository. It returns evidence with exact 1-based line citations, clearly states what its scan cannot establish, and can generate and grade an interactive Technical Viva.

## The problem and the solution

Technical claims are easy to make and difficult to verify quickly. ProofHire gathers a deliberately limited, inspectable set of repository files and evaluates each claim against the evidence it actually found. Citations must point to retrieved files and valid line ranges; a missing match in a bounded scan is not treated as proof that a feature does not exist.

Each claim assertion receives an evidence verdict:

- `SUPPORTED`
- `PARTIALLY_SUPPORTED`
- `CONTRADICTED`
- `INSUFFICIENT_EVIDENCE`

The numeric credibility score is a transparent evidence heuristic from 0–100, not a probability of honesty, authorship, competence, or hiring suitability. It scores each extracted assertion against its verdict and citation, then adjusts for scan coverage. LLM output is optional and its citations are validated before they are returned.

### Explicit LLM failure policies

- `llm_cascade` (default): use configured providers within a bounded attempt budget; it does **not** silently fall back to heuristic analysis.
- `llm_required`: require the selected provider; do not switch providers or use the heuristic.
- `allow_heuristic`: permit clearly labeled deterministic analysis when credentials are absent or LLM analysis is unavailable.

Selecting `allow_heuristic` keeps the sample/offline workflow usable without provider credentials. It also permits deterministic results when an LLM is unavailable. Without credentials, select **Allow clearly labeled heuristic fallback** in the dashboard (or set `fallback_policy` to `allow_heuristic` in an API request). The default `llm_cascade` policy does not silently use heuristics.

## Architecture and features

- **Bounded repository scanner:** reads the README and recognized dependency manifests, plus up to six prioritized source files. It skips unsuitable content and discloses scan limits and safe truncation.
- **Evidence-grounded analysis:** validates citations against inspected source and uses one-based line numbers. The deterministic scoring heuristic is explainable; optional LLM analysis uses Gemini `gemini-2.5-flash` or OpenAI `gpt-4o-mini` by default.
- **Explicit failure controls:** select `llm_cascade`, `llm_required`, or `allow_heuristic` for audit and Viva requests. When heuristic fallback is explicitly enabled, an LLM outage can still produce a clearly identified result for that request without restarting the service; it is never enabled silently.
- **Offline sample snapshots:** bundled sample repositories make the demo repeatable without GitHub access. An in-memory TTL cache reduces repeated GitHub retrievals.
- **Interactive Technical Viva:** audits generate three repository-grounded questions; submit an answer for concept/depth grading and feedback, with LLM or permitted deterministic evaluation.
- **Privacy-minded local setup:** no database or persistent audit history. Optional browser keys are held in page memory, not browser storage.

## Quick start

Works on Windows, macOS, and Linux with Python 3.10 or newer.

1. (Optional) Create and activate a virtual environment, then install dependencies from the repository root:

   ```bash
   python -m venv .venv
   # Windows PowerShell: .venv\Scripts\Activate.ps1
   # macOS/Linux: source .venv/bin/activate
   python -m pip install -r requirements.txt
   ```

2. Optional: copy `.env.example` to `.env` and set provider or GitHub variables. Leave API keys empty for a zero-key demo. Keep real keys out of source control.

3. Start the service:

   ```bash
   python -m uvicorn main:app --reload
   ```

   Alternatively, run `python main.py`.

4. Open:

   - Dashboard: <http://127.0.0.1:8000>
   - Swagger API docs: <http://127.0.0.1:8000/docs>

5. In the dashboard, load a sample repository and choose **Allow clearly labeled heuristic fallback** under **Failure policy** to run the offline demo without API keys. For API clients, send `"fallback_policy": "allow_heuristic"` with the audit or Viva request.

### Optional environment variables

| Variable | Purpose |
|---|---|
| `GITHUB_TOKEN` | Optional GitHub API token for repository retrieval. |
| `GEMINI_API_KEY` | Optional Gemini provider credential. |
| `GEMINI_MODEL` | Gemini model ID; defaults to `gemini-2.5-flash`. |
| `GEMINI_ALTERNATE_MODELS` | Optional comma-separated Gemini model IDs, tried after an invalid-model/endpoint response. |
| `OPENAI_API_KEY` | Optional OpenAI provider credential. |
| `OPENAI_MODEL` | OpenAI model ID; defaults to `gpt-4o-mini`. |
| `OPENAI_ALTERNATE_MODELS` | Optional comma-separated OpenAI model IDs, tried after an invalid-model/endpoint response. |
| `LLM_MAX_PROVIDER_ATTEMPTS` | Shared provider-attempt budget; defaults to 3 and is bounded to 1–10. |

## API endpoints

| Method and path | Description |
|---|---|
| `GET /` | Serves the dashboard. |
| `GET /api/health` | Returns service status, version, docs path, and whether environment credentials are configured. |
| `GET /api/samples` | Returns the three bundled sample requests and their offline snapshots. |
| `POST /api/audit` | Audits a `repo_url` and technical `claim`; supports optional credentials, provider selection, repository refresh, and failure policy. Returns score, verdicts, findings, citations, scan limitations, provider attribution, and three Viva questions. |
| `POST /api/evaluate-viva` | Grades a Viva answer using its question, expected concepts, answer, and selected failure policy; returns score, feedback, matched/missed concepts, and an ideal answer. |

Example zero-key audit request:

```json
{
  "repo_url": "https://github.com/proofhire-samples/fastapi-redis-jwt",
  "claim": "Built a FastAPI backend with Redis caching and JWT authentication.",
  "fallback_policy": "allow_heuristic"
}
```

For request and response schemas, open `/docs` after starting the app.

## Tests and benchmarks

Run the 112 unit tests:

```bash
python -m unittest discover -s tests -v
```

Run the deterministic claim-verification benchmark without credentials:

```bash
python -m benchmarks.run_benchmark --mode heuristic
```

See [`benchmarks/README.md`](benchmarks/README.md) for dataset limitations, LLM-mode requirements, and report options. Benchmark labels are not independently reviewed ground truth; consult that guide before interpreting metrics.

## Scope and limitations

ProofHire scans public GitHub repositories with bounded file selection; it is not a complete repository indexer. Its evidence supports human review and does not establish candidate authorship, competence, truthfulness, or hiring suitability. No finding in the inspected files is not proof of absence elsewhere in the repository.
