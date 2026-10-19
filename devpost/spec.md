---
doc: spec
status: approved
---

# ProofHire — Technical Spec

## How This Works, In Plain Language

A separate frontend sends JSON to the FastAPI backend. The backend validates the GitHub URL, retrieves a small set of public repository files (or uses one of three bundled demo snapshots), adds exact line numbers, and analyzes the resume claim. With an API key it can ask Gemini or OpenAI for a structured analysis; otherwise, or if an LLM call fails, a deterministic code/manifest inspector produces the result. The backend checks citations against fetched files before returning them. Nothing is saved to a database.

## The Core Journey Through the System

1. Frontend checks `GET /api/health` and loads samples from `GET /api/samples`. Implements `prd.md > Health and Samples`.
2. Frontend submits a repository URL, claim, and optional credential/provider overrides to `POST /api/audit`. FastAPI validates input, resolves secrets by request body → header → environment priority, and rejects non-GitHub URLs. Implements `prd.md > Audit Request`.
3. Repository service checks the sample snapshot map and TTL cache, then uses GitHub REST metadata and recursive tree APIs for live public repositories. It selects README and recognized manifests plus up to six prioritized source files, rejects binary/vendor/minified/lock content, bounds bytes, and numbers lines. Implements `prd.md > Audit Request`.
4. The analysis service calls the selected LLM through REST with strict JSON instructions, or runs deterministic feature/import/dependency inspection. An LLM error or invalid response switches to the heuristic result. All returned citations are checked against actual fetched files and line ranges. Implements `prd.md > Audit Request`.
5. `POST /api/audit` returns metadata, score/verdict, claim breakdown, findings, warnings, and three viva questions. `POST /api/evaluate-viva` evaluates a defense via LLM when usable or via concept/depth scoring. Implements `prd.md > Viva Answer Evaluation`.

## Stack

- Python 3.10 or newer.
- FastAPI for REST routing, Pydantic for validation/response schemas, and Uvicorn for local serving.
- `requests` for GitHub and LLM REST calls; `python-dotenv` for optional local `.env` configuration.
- The dependency set is pure Python / wheel-distributable on Windows and does not require a C++ compiler.
- No database, frontend framework, or persistent cache.

## Where It Runs and How Someone Tries It

From the project root, install with `python -m pip install -r requirements.txt`, copy `.env.example` to `.env` if optional credentials are needed, and run `python -m uvicorn main:app --reload`. Open `http://127.0.0.1:8000/docs` or call the JSON endpoints from a separate frontend. Without credentials, use a sample URL from `GET /api/samples` and submit its paired claim to `POST /api/audit`. The embedded snapshot path does not require internet access.

## Components

### FastAPI application

One `main.py` defines Pydantic request/response schemas, CORS middleware, root/health/sample/audit/evaluation endpoints, and JSON error handling. CORS uses all origins, methods, headers, and credentials as requested. No browser cookie session is used.

### GitHub URL and repository reader

The URL parser accepts `github.com/owner/repo` with optional scheme, `.git`, tree/blob suffix, query, or trailing slash; it accepts no other host. The reader requests metadata and a recursive default-branch tree with explicit timeouts and an optional token. It fetches README and root dependency manifests (`requirements.txt`, `package.json`, `pyproject.toml`, `pom.xml`, `Cargo.toml`, `go.mod`) plus up to six source files prioritized for entrypoints and routes/controllers/models/auth. It skips binary, lock, vendored, generated, and minified files, and truncates oversized files and trees while returning warnings. Each included line has a 1-based `N: ` prefix.

### Cache and offline samples

`REPO_CACHE` is a process-local, lock-protected TTL dictionary keyed by normalized `owner/repo`; cache hits avoid repeated GitHub API calls until expiry. Three named sample repositories map to embedded metadata and synthetic source snapshots. `GET /api/samples` returns title, request payload, and matching fallback snapshot; auditing a sample URL uses the snapshot immediately and works offline.

### Audit engine

Feature extraction recognizes common frameworks and capabilities (FastAPI, Express, React, JWT, OAuth, Redis, caching, Docker/Kubernetes, SQL/NoSQL databases, async/await, testing, rate limiting, WebSockets, microservices, and common ML libraries). It compares claim terms with manifests and implementation evidence, classifies each feature as `verified`, `partial`, or `missing`, and calculates the deterministic score from those classifications. Manifest-only references do not count as proof of runtime implementation. The deterministic score is an evidence heuristic, not a candidate assessment.

When a key is available, Gemini (`gemini-2.5-flash`, with a supported fallback model) or OpenAI (`gpt-4o-mini`) receives a strict JSON prompt with the claim and bounded, numbered files. The response is parsed and validated; cited paths and line ranges must exist in the fetched file map. Provider errors, malformed JSON, or invalid citations use the deterministic result and add a warning. API keys are never returned or logged.

### Viva evaluator

The evaluator may use a configured LLM, but validates its output and falls back on failure. The local evaluator matches expected concepts and measures explanatory depth, then returns score, pass status, matched/missed concepts, feedback, and an ideal answer.

## API and Data Model

### Health responses

`GET /` and `GET /api/health` return:

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

Request: `repo_url`, `claim`, optional `github_token`, `llm_api_key`, `llm_provider`, `gemini_api_key`, and `openai_api_key`. Equivalent optional secrets can be supplied by `X-GitHub-Token`, `X-Gemini-Key`, and `X-OpenAI-Key` headers or environment variables.

Response: `repo_metadata` (`owner`, `repo`, `stars`, `language`, `files_scanned`, `analysis_engine`, `cached`), `credibility_score` (0–100), `verdict`, `summary`, `claim_breakdown` (`claimed_feature`, status, optional evidence file/lines, explanation), `findings` (severity, file, lines, title, description, code snippet, recommendation), exactly three `viva_questions` (id, file, line range, difficulty, question, why asked, expected concepts, code context, refactored fix snippet), and `warnings`/`scan_limits` describing incomplete coverage or fallback.

### Viva evaluation

Request: `question_id`, `question`, `expected_concepts`, `user_answer`, optional `code_context`, and optional `llm_api_key`.

Response: `score`, `passed`, `verdict`, `matched_concepts`, `missed_concepts`, `feedback`, and `ideal_answer`.

### Errors

Invalid input returns structured HTTP 400. Unknown/private repository returns a clear 404. GitHub rate limits/network timeout return a structured 503 unless a matching sample snapshot can be used. Provider failures do not fail the request; they produce heuristic results with warnings. Empty repositories return a bounded-scan result without fabricated citations. No external exception is allowed to become an unhandled 500.

## File Structure

```text
proof-hire/
├── main.py                 # Self-contained API, schemas, samples, fetcher and analyzers
├── requirements.txt        # FastAPI, Uvicorn, Requests, Pydantic, python-dotenv
├── .env.example            # Secret-free optional credential names
├── .gitignore              # Local secrets, Python artifacts, private learner profile
├── scope.md
├── prd.md
├── spec.md
└── devpost/
    ├── scope.md
    ├── prd.md
    ├── spec.md
    └── checklist.md
```

## External Services and Dependencies

- GitHub REST API metadata and recursive tree calls use bounded timeouts, optional `GITHUB_TOKEN`, and an in-memory cache. Raw public file reads use `raw.githubusercontent.com`.
- Gemini REST and OpenAI Chat Completions are optional; `GEMINI_API_KEY` and `OPENAI_API_KEY` are never required to run samples or heuristic analysis.
- External calls are bounded by timeouts and checked status codes. Secrets are accepted from environment, headers, or JSON fields with request values taking priority; do not persist them.

## Failure Modes and Safety Boundaries

- Invalid URL or non-GitHub host: structured 400; no request to arbitrary hosts.
- Not found/private: clear 404; do not pretend that a private repository was scanned.
- Rate limit, timeout, or provider outage: use a matching embedded sample if possible; otherwise return a structured warning/error or heuristic result where repository evidence is available.
- Empty/binary/oversized/minified/vendor files: skip or safely truncate and report scan limits.
- LLM malformed JSON or unsupported citations: discard the LLM result and fall back to deterministic analysis.
- Missing feature: report only that it was not found in the inspected files.
- CORS `*` plus credentials is retained per request; browser frontends should not use cookie credentials for this API.

## Decisions

- Approved: Python FastAPI backend only in this phase; separate frontend integration later.
- Approved: optional GitHub/Gemini/OpenAI credentials via environment, headers, or body, with unauthenticated operation supported.
- Approved: process-local TTL cache, three embedded offline sample snapshots, deterministic fallback, optional Gemini/OpenAI REST analysis, and five specified endpoints.
- Approved: public GitHub repositories only; bounded file selection; line-grounded findings; no database and no hiring recommendation.
