---
doc: spec
status: approved
---

# ProofHire — Technical Spec

## How This Works, In Plain Language

FastAPI serves the static dashboard at `/` and the JSON API from the same process. The dashboard checks backend health, loads one of three bundled sample payloads, and sends the repository URL and claim to the backend. The backend validates the URL, retrieves a bounded set of public repository files (or uses a bundled snapshot), numbers lines, and routes a structured analysis through configured providers. Deterministic analysis runs only when the request explicitly selects `allow_heuristic`. Citations are checked against retrieved files and feature relevance. Nothing is saved to a database.

## The Core Journey Through the System

1. Browser opens `/`; FastAPI serves the dashboard, which checks backend status at `GET /api/health` and loads samples from `GET /api/samples`. Health does not claim that an LLM provider is reachable. Implements `prd.md > The Core Journey`, `prd.md > Health and Samples`.
2. Dashboard submits a repository URL, claim, and optional credential/provider overrides to `POST /api/audit`. FastAPI validates input, resolves secrets by request body → header → environment priority, and rejects non-GitHub URLs. Implements `prd.md > Audit Request`.
3. Repository service checks the sample snapshot map and TTL cache, then uses GitHub REST metadata and recursive tree APIs for live public repositories. It selects README and recognized manifests plus up to six prioritized source files, rejects binary/vendor/minified/lock content, bounds bytes, and numbers lines. Implements `prd.md > Audit Request`.
4. The analysis service uses one request-scoped provider-attempt budget. `llm_cascade` tries the selected provider and other explicitly configured providers; `llm_required` uses only the selected provider and never switches to heuristics; deterministic inspection runs only under explicit `allow_heuristic`. All returned citations are checked against retrieved paths, line ranges, and feature relevance. Implements `prd.md > Audit Request`.
5. Dashboard renders metadata, score/verdict, claim breakdown, findings, warnings, and three viva questions. The user can post an answer to `POST /api/evaluate-viva`, which evaluates via LLM when usable or via concept/depth scoring. Implements `prd.md > Viva Answer Evaluation`.

## Stack

- Python 3.10 or newer.
- FastAPI for REST routing, Pydantic for validation/response schemas, and Uvicorn for local serving.
- `requests` for GitHub and LLM REST calls; `python-dotenv` for optional local `.env` configuration.
- The dependency set is pure Python / wheel-distributable on Windows and does not require a C++ compiler.
- Frontend is one static HTML document with Tailwind CSS and Lucide icons loaded from CDN; vanilla JavaScript calls same-origin API routes and handles results and errors.
- No database, frontend framework, or persistent cache.

## Where It Runs and How Someone Tries It

From the project root, install with `python -m pip install -r requirements.txt`, copy `.env.example` to `.env` if optional credentials are needed, and run `python -m uvicorn main:app --reload`. Open `http://127.0.0.1:8000/` for the dashboard or `/docs` for the API explorer. For a zero-key audit of an embedded sample, choose `allow_heuristic` in the dashboard's Failure policy control (or set `fallback_policy` in the request); the snapshot path does not require GitHub access.

## Components

### FastAPI application

One `main.py` defines Pydantic request/response schemas, CORS middleware, root/health/sample/audit/evaluation endpoints, and JSON error handling. CORS uses all origins, methods, headers, and credentials as requested. No browser cookie session is used.

### Static dashboard

`static/index.html` contains the responsive dashboard, accessible forms, status polling, sample selector, loading/alert states, score and evidence rendering, viva answer submission, and optional in-memory API-key settings. User-provided and API-returned text is escaped before insertion in the page. Credentials are not stored in localStorage or sent to analytics.

### GitHub URL and repository reader

The URL parser accepts `github.com/owner/repo` with optional scheme, `.git`, tree/blob suffix, query, or trailing slash; it accepts no other host. The reader requests metadata and a recursive default-branch tree with explicit timeouts and an optional token. It fetches README and root dependency manifests (`requirements.txt`, `package.json`, `pyproject.toml`, `pom.xml`, `Cargo.toml`, `go.mod`) plus up to six source files prioritized for entrypoints and routes/controllers/models/auth. It skips binary, lock, vendored, generated, and minified files, and truncates oversized files and trees while returning warnings. Each included line has a 1-based `N: ` prefix.

### Cache and offline samples

`REPO_CACHE` is a process-local, lock-protected TTL dictionary keyed by normalized `owner/repo`; cache hits avoid repeated GitHub API calls until expiry. Three named sample repositories map to embedded metadata and synthetic source snapshots. `GET /api/samples` returns title, request payload, and matching fallback snapshot; auditing a sample URL uses the snapshot immediately and works offline.

### Audit engine

Feature extraction recognizes common frameworks and capabilities (FastAPI, Flask, Express, REST APIs, React, JWT, OAuth, Redis, caching, Docker/Kubernetes, SQL/NoSQL databases, async/await, testing, rate limiting, WebSockets, microservices, and common ML libraries) and preserves additional technical assertions in compound claims instead of dropping them. Source evidence is checked in framework context; README text is not implementation proof. Manifest-only or import-only references are partial evidence.

Each claim-breakdown item retains the legacy `status` (`verified`, `partial`, or `missing`) and adds `verification_verdict`: `SUPPORTED`, `CONTRADICTED`, `PARTIALLY_SUPPORTED`, or `INSUFFICIENT_EVIDENCE`. This per-assertion evidence verdict is separate from the numerical credibility score. Contradiction requires inspected implementation evidence that conflicts with an explicit negated assertion. No match in the bounded scan is `INSUFFICIENT_EVIDENCE`, never proof that a feature is absent.

The deterministic credibility score is a transparent evidence heuristic, not a probability of honesty, competence, or hiring success, and it cannot establish candidate authorship. For each extracted assertion, award 100 points for `SUPPORTED` with a valid citation to inspected implementation source; 55 for `PARTIALLY_SUPPORTED` with a valid source citation; 35 for partial evidence cited only in a README or dependency manifest; and 55 when a nominally supported assertion cites only documentation or a manifest. A valid source citation for `CONTRADICTED` receives 0. `INSUFFICIENT_EVIDENCE`, or a missing/invalid citation on a non-unresolved verdict, receives 20; this low evidence credit is not a contradiction. Average these points across every extracted assertion, so unresolved compound assertions remain in the denominator. Multiply by a scan factor: 1.00 when no limitation is reported, 0.90 for a normal bounded scan, 0.75 when truncation or omitted repository content is reported, and 0.50 when no files are available; round to the nearest integer. Opposing positive and negated assertions are both scored, allowing their conflict to lower the average. The response summary reports assertion counts, citation validity, scan limitations, and the heuristic's limits. The legacy top-level `verdict` remains a score band for API compatibility; it does not replace per-assertion verdicts.

Provider configuration is resolved in one place. Provider-specific request body credentials take precedence over provider-specific headers, which take precedence over environment variables (`GEMINI_API_KEY`, `OPENAI_API_KEY`); the selected provider is primary. A generic request key is assigned to the selected provider, or inferred for `auto` (`sk-` selects OpenAI; otherwise Gemini). Model IDs come from `GEMINI_MODEL` (default `gemini-2.5-flash`) and `OPENAI_MODEL` (default `gpt-4o-mini`). Optional comma-separated `GEMINI_ALTERNATE_MODELS` and `OPENAI_ALTERNATE_MODELS` are tried only after invalid-model/endpoint responses. Gemini IDs are normalized before constructing the fixed `v1beta` `generateContent` endpoint; OpenAI uses the fixed Chat Completions endpoint. Invalid model identifiers are rejected locally.

`LLM_MAX_PROVIDER_ATTEMPTS` defaults to 3 and is bounded to 1–10; this budget is shared across providers and transient retries for one audit. Each eligible transient request is retried at most once with bounded backoff and `Retry-After` when it fits the shared 65-second deadline. Quota exhaustion, authentication failure, malformed output, and invalid configuration are not retried against the same endpoint. No response-repair attempt is made. A backend health response or configured key does not indicate provider availability. Failure logs contain only sanitized categories and provider status codes, never credentials, provider message bodies, or prompt content.

Audit responses identify requested and actual provider/model, per-component analysis source, fallback policy, attempt count, failure category, and completeness. Reports with deterministic component fallback are marked `partial` and accurately labeled as mixed provenance. `llm_cascade` may try other configured providers; `llm_required` tries only the selected provider and returns a structured 503 if no validated result is available; only explicit `allow_heuristic` returns deterministic analysis after LLM failure. No provider result is cached. The process-local repository snapshot cache is separate and may be bypassed through `refresh_repository`.

### Viva evaluator

The evaluator may use a configured LLM, but validates its output. Its LLM fallback behavior follows the request policy; deterministic grading is labeled and returned only under explicit `allow_heuristic`. The local evaluator matches expected concepts and measures explanatory depth, then returns score, pass status, matched/missed concepts, feedback, and an ideal answer.

## API and Data Model

### Health responses

`GET /` serves `static/index.html`. `GET /api/health` reports backend/configuration status only. `auth_configured.llm_key` means a key exists; it does not imply provider reachability or quota. It returns:

```json
{
  "status": "ok",
  "service": "ProofHire API",
  "version": "1.0.0",
  "docs_url": "/docs",
  "auth_configured": {"github_token": false, "llm_key": false}
}
```

### Audit

Request: `repo_url`, `claim`, optional `github_token`, `llm_api_key`, `llm_provider`, `fallback_policy`, `gemini_api_key`, and `openai_api_key`. Equivalent optional secrets can be supplied by `X-GitHub-Token`, `X-Gemini-Key`, and `X-OpenAI-Key` headers or environment variables.

Response: `repo_metadata` (`owner`, `repo`, `stars`, `language`, `files_scanned`, `analysis_engine`, `cached`), `credibility_score` (0–100), `verdict`, `summary`, `claim_breakdown` (`claimed_feature`, legacy `status`, additive `verification_verdict`, evidence file/lines, explanation, `analysis_source`), `findings`, exactly three `viva_questions`, `warnings`/`scan_limits`, `result_status`, and `provider_attribution` (`requested_provider`, `requested_model`, `actual_provider`, `actual_model`, `fallback_policy`, `failure_category`, `attempt_count`). A 503 `llm_unavailable` error is returned when policy disallows heuristics and no validated provider result is available.

### Viva evaluation

Request: `question_id`, `question`, `expected_concepts`, `user_answer`, optional `code_context`, and optional `llm_api_key`.

Response: `score`, `passed`, `verdict`, `matched_concepts`, `missed_concepts`, `feedback`, and `ideal_answer`.

### Errors

Invalid input returns structured HTTP 400. Unknown/private repository returns a clear 404. GitHub rate limits/network timeout return a structured 503 unless a matching sample snapshot can be used. Provider failures produce a structured 503 unless the request explicitly selects `allow_heuristic`. Empty repositories return a bounded-scan result only under that policy, without fabricated citations. No external exception is allowed to become an unhandled 500.

## File Structure

```text
proof-hire/
├── README.md               # Setup, API, tests, and benchmark guide
├── main.py                 # Self-contained API, schemas, samples, fetcher and analyzers
├── requirements.txt        # FastAPI, Uvicorn, Requests, Pydantic, python-dotenv
├── .env.example            # Secret-free optional configuration names/defaults
├── .gitignore              # Local secrets, Python artifacts, private learner profile
├── static/
│   └── index.html
├── scope.md
├── prd.md
├── spec.md
├── tests/
│   ├── __init__.py
│   └── test_*.py            # Unit tests for audit, providers, and benchmarks
├── benchmarks/
│   ├── README.md
│   ├── __init__.py
│   ├── cases.json
│   ├── fixtures.json
│   ├── run_benchmark.py
│   └── reports/             # Reproducible benchmark reports
└── devpost/
    ├── app-map.html
    ├── scope.md
    ├── prd.md
    ├── spec.md
    └── checklist.md
```

## External Services and Dependencies

- GitHub REST API metadata and recursive tree calls use bounded timeouts, optional `GITHUB_TOKEN`, and an in-memory cache. Raw public file reads use `raw.githubusercontent.com`.
- Gemini REST and OpenAI Chat Completions are optional; `GEMINI_API_KEY` and `OPENAI_API_KEY` are never required to load samples or use deterministic analysis when `allow_heuristic` is selected.
- Optional model and attempt settings include `GEMINI_MODEL`, `GEMINI_ALTERNATE_MODELS`, `OPENAI_MODEL`, `OPENAI_ALTERNATE_MODELS`, and `LLM_MAX_PROVIDER_ATTEMPTS`; see `.env.example`.
- Tailwind CSS and Lucide browser assets are loaded from a public CDN; styling/icons require internet access, while API sample behavior is served locally.
- External calls are bounded by timeouts and checked status codes. Secrets are accepted from environment, headers, or JSON fields with request values taking priority; do not persist them.

## Failure Modes and Safety Boundaries

- Invalid URL or non-GitHub host: structured 400; no request to arbitrary hosts.
- Not found/private: clear 404; do not pretend that a private repository was scanned.
- Rate limit, timeout, or provider outage: use only configured providers within the shared attempt budget; if none produces a validated result, return 503 unless `allow_heuristic` was explicitly selected.
- Empty/binary/oversized/minified/vendor files: skip or safely truncate and report scan limits.
- LLM malformed JSON or unsupported citations: discard the invalid component; use deterministic analysis only under `allow_heuristic`, otherwise return a structured 503 when no other configured provider succeeds.
- Missing feature: report only that it was not found in the inspected files.
- CORS `*` plus credentials is retained per request; browser frontends should not use cookie credentials for this API.
- The dashboard requires CDN access for Tailwind/Lucide; native forms and API behavior remain understandable if those assets fail to load.

## Decisions

- Approved: Python FastAPI backend with a same-origin static dashboard served by the same app.
- Approved: optional GitHub/Gemini/OpenAI credentials via environment, headers, or body, with unauthenticated operation supported.
- Approved: process-local TTL cache, three embedded sample snapshots, optional Gemini/OpenAI REST analysis, deterministic analysis only under explicit `allow_heuristic`, and five specified endpoints.
- Approved: public GitHub repositories only; bounded file selection; line-grounded findings; no database and no hiring recommendation.
- Approved: serve a dark Tailwind/Lucide dashboard from `/` and static assets from `/static`, with same-origin API calls and browser-session-only key settings.
