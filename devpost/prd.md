---
doc: prd
status: approved
---

# ProofHire — Product Requirements

ProofHire is a FastAPI app with a static dark-mode dashboard for auditing one technical resume claim against a bounded set of files in a GitHub repository.

## The Core Journey

1. The user opens `/`; the dashboard polls `GET /api/health` and loads demo cases from `GET /api/samples`.
2. The user enters a GitHub repository URL and a technical claim, or selects and loads a sample. The dashboard sends one `POST /api/audit` request.
3. The backend validates the URL and request, uses a known offline snapshot or retrieves repository metadata, README, manifests, and up to six high-priority source files, then numbers each source line.
4. The backend analyzes the claim with the selected LLM and, under the configured policy, may try another explicitly configured provider. Deterministic analysis runs only when `allow_heuristic` is selected.
5. The dashboard renders repository metadata, score/verdict, evidence-linked claim breakdown, findings, warnings and exactly three grounded viva questions.
6. The user can submit an answer from a question card through `POST /api/evaluate-viva` and receive a score, concept feedback, and an ideal answer. Without an LLM key, deterministic grading is available when `allow_heuristic` is explicitly selected.

## What We're Building

- A single-file Python FastAPI service with a dashboard served at `/`, a health endpoint at `/api/health`, three repeatable offline sample cases, repository URL validation, resilient GitHub retrieval and caching, optional Gemini/OpenAI analysis, policy-controlled deterministic analysis, structured audit responses, and Viva answer evaluation.
- A responsive dark-mode dashboard in `static/index.html` using Tailwind CSS and Lucide icons. It consumes the same-origin REST API and displays audit evidence and viva grading results without page reloads.
- A bundled sample path that works without GitHub credentials. With no LLM credentials, select `allow_heuristic` for deterministic audit and Viva analysis; other policies return a structured provider-unavailable response.
- Explicit warnings for bounded scans, unavailable data, provider fallback, and unverified coverage. Per-assertion verdicts distinguish supported, contradicted, partially supported, and insufficient evidence; no match in the bounded scan is not proof of absence.

## API Behavior and Acceptance Criteria

### Dashboard, Health and Samples

- `GET /` serves the dashboard; `GET /api/health` returns service status, version, docs path, and booleans indicating whether GitHub and any LLM key are configured.
- The dashboard polls health to show backend availability and fetches sample options during page initialization.
- `GET /api/samples` returns three labeled request payloads and bundled snapshots that the audit endpoint recognizes offline: an exaggerated FastAPI/Redis/JWT claim, an Express scalability claim, and a Python ML/testing/Docker claim.
- CORS allows all origins, methods, and headers and enables credentials, as requested for independent frontend development. Browser clients should not send cookie credentials with wildcard origins.

### Audit Request

`POST /api/audit` accepts `repo_url`, `claim`, optional `github_token`, `llm_api_key`, `llm_provider` (`auto`, `gemini`, or `openai`), `fallback_policy` (`llm_cascade`, `llm_required`, or `allow_heuristic`), and optional dedicated Gemini/OpenAI keys. Credentials may also be supplied in `X-GitHub-Token`, `X-Gemini-Key`, or `X-OpenAI-Key` headers or environment variables. Provider-specific request values override headers, which override environment values. A generic key is assigned to the explicitly selected provider; for `auto`, an `sk-` prefix selects OpenAI and other generic keys select Gemini. The default fallback policy is `llm_cascade`; it does not silently use heuristics. Missing LLM credentials are accepted as request data but result in a structured 503 unless `allow_heuristic` was explicitly selected.

Acceptance:

- Parse only valid GitHub repository URLs, including `.git`, tree/blob paths, query strings, and trailing slashes. Empty, malformed, and non-GitHub inputs return a helpful JSON 400 response.
- Return repository metadata, scan file paths, analysis engine and cache state, an integer score from 0–100, one of the three documented verdicts, a summary, claim breakdown, findings, and exactly three viva questions.
- Report requested and actual provider/model, per-component analysis source, result completeness, fallback policy, attempt count, and sanitized failure category. `llm_required` tries only the selected provider and returns a structured 503 if no validated result is available. `llm_cascade` tries configured providers within one bounded attempt budget. `allow_heuristic` permits a clearly labeled deterministic result.
- Each citation points to an actual fetched file and valid 1-based line range. Never invent citations. Missing evidence is described as not found in the inspected files.
- Public repository 404/private responses are clear structured errors. GitHub rate limits and network failures produce structured errors or warnings according to the request path, not an unhandled 500.
- Ignore binary, lock, minified, generated, and dependency-vendor files; cap file count and bytes; disclose truncation and scan limitations.
- A provider error or invalid/malformed provider response returns a structured 503 unless `allow_heuristic` was explicitly selected.
- The dashboard displays loading progress, structured errors, findings and scan limits without reloading the page.

### Viva Answer Evaluation

`POST /api/evaluate-viva` accepts a question id, question, expected concepts, candidate answer, optional code context, optional provider keys, and a fallback policy. It returns an integer score, pass flag, verdict, matched/missed concepts, feedback, and an ideal answer. A configured LLM is used when available; deterministic grading is returned only when `allow_heuristic` is explicitly selected.

Acceptance:

- With no provider credentials, return a structured 503 unless `allow_heuristic` is selected.
- An empty or irrelevant answer receives a low score and actionable feedback.
- A strong answer that addresses expected concepts and explains relevant trade-offs can pass.
- Provider errors use another configured provider only under `llm_cascade`; otherwise return a structured 503 unless `allow_heuristic` is selected.

## States and Boundaries

- **Ready:** service responds to health and sample calls.
- **Sample audit:** known sample URLs resolve to embedded snapshots even when offline.
- **Live audit:** only validated public GitHub repository URLs are fetched.
- **Cache hit:** a fresh in-memory snapshot is reused for its owner/repository key.
- **LLM unavailable:** `llm_cascade` and `llm_required` return a structured provider-unavailable response; only explicit `allow_heuristic` returns deterministic analysis.
- **Partial scan:** output lists scanned files and limits; it never equates absence in the scan with absence in the full repository.
- **Fetch error:** return a structured 4xx/503 error or warning as applicable, never an unhandled server exception.
- **Persistence:** no database or audit history; the cache is process-local and expires.
- **Dashboard:** `/` serves the static page, `/static/` serves local assets, and optional browser keys are held only in page memory.

## Non-Goals

- User accounts, persistent report storage, private repositories, or broad repository indexing.
- Verifying a candidate's identity, authorship, truthfulness, or hiring suitability.
- Guaranteeing exhaustive source analysis or treating an AI-generated score as an employment decision.
- Claiming production readiness for internet deployment without deployment-specific secret management, quotas, observability, and security review.

## Approved Decisions

- The first implementation is Python FastAPI with a static same-origin dashboard and REST API.
- The service supports optional GitHub, Gemini, and OpenAI credentials via environment, request headers, or request body, and remains useful without keys.
- The app includes three deterministic offline sample snapshots, in-memory TTL repository caching, bounded GitHub retrieval, line-numbered evidence, deterministic analysis under explicit `allow_heuristic`, and optional live LLM analysis.
- The required endpoints are `GET /`, `GET /api/health`, `GET /api/samples`, `POST /api/audit`, and `POST /api/evaluate-viva`.
- The code is a human-review aid, not an automated hiring decision.
- A separate frontend deployment remains possible, but the default demo serves its dashboard from FastAPI.
