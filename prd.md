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
4. The backend analyzes the claim. It uses Gemini or OpenAI when configured; if no key is available or the provider fails, deterministic code and dependency inspection completes the audit.
5. The dashboard renders repository metadata, score/verdict, evidence-linked claim breakdown, findings, warnings and exactly three grounded viva questions.
6. The user can submit an answer from a question card through `POST /api/evaluate-viva` and receive a score, concept feedback, and an ideal answer. This also works without an LLM key.

## What We're Building

- A single-file Python FastAPI service with a dashboard served at `/`, a health endpoint at `/api/health`, three repeatable offline sample cases, repository URL validation, resilient GitHub retrieval and caching, optional Gemini/OpenAI analysis with heuristic fallback, structured audit responses, and viva answer evaluation.
- A responsive dark-mode dashboard in `static/index.html` using Tailwind CSS and Lucide icons. It consumes the same-origin REST API and displays audit evidence and viva grading results without page reloads.
- A frontend path that works without credentials on the bundled sample flow.
- Explicit warnings for bounded scans, unavailable data, provider fallback, and unverified coverage. A missing indicator means only that support was not found in inspected files.

## API Behavior and Acceptance Criteria

### Dashboard, Health and Samples

- `GET /` serves the dashboard; `GET /api/health` returns service status, version, docs path, and booleans indicating whether GitHub and any LLM key are configured.
- The dashboard polls health to show backend availability and fetches sample options during page initialization.
- `GET /api/samples` returns three labeled request payloads and bundled snapshots that the audit endpoint recognizes offline: an exaggerated FastAPI/Redis/JWT claim, an Express scalability claim, and a Python ML/testing/Docker claim.
- CORS allows all origins, methods, and headers and enables credentials, as requested for independent frontend development. Browser clients should not send cookie credentials with wildcard origins.

### Audit Request

`POST /api/audit` accepts `repo_url`, `claim`, optional `github_token`, `llm_api_key`, `llm_provider` (`auto`, `gemini`, or `openai`), and optional dedicated Gemini/OpenAI keys. Credentials may also be supplied in `X-GitHub-Token`, `X-Gemini-Key`, or `X-OpenAI-Key` headers or environment variables. Request values override headers, which override environment values. Omitted credentials are valid.

Acceptance:

- Parse only valid GitHub repository URLs, including `.git`, tree/blob paths, query strings, and trailing slashes. Empty, malformed, and non-GitHub inputs return a helpful JSON 400 response.
- Return repository metadata, scan file paths, analysis engine and cache state, an integer score from 0–100, one of the three documented verdicts, a summary, claim breakdown, findings, and exactly three viva questions.
- Each citation points to an actual fetched file and valid 1-based line range. Never invent citations. Missing evidence is described as not found in the inspected files.
- Public repository 404/private responses are clear structured errors. GitHub rate limits and network failures produce structured warnings/fallback behavior, not an unhandled 500.
- Ignore binary, lock, minified, generated, and dependency-vendor files; cap file count and bytes; disclose truncation and scan limitations.
- A provider error or invalid/malformed provider response falls back to the deterministic analyzer.
- The dashboard displays loading progress, structured errors, findings and scan limits without reloading the page.

### Viva Answer Evaluation

`POST /api/evaluate-viva` accepts a question id, question, expected concepts, candidate answer, optional code context, and optional LLM key. It returns an integer score, pass flag, verdict, matched/missed concepts, feedback, and an ideal answer. With no usable LLM key, concept coverage and explanatory depth determine the score.

Acceptance:

- Works without external credentials.
- An empty or irrelevant answer receives a low score and actionable feedback.
- A strong answer that addresses expected concepts and explains relevant trade-offs can pass.
- Provider errors transparently use the deterministic evaluator rather than failing the endpoint.

## States and Boundaries

- **Ready:** service responds to health and sample calls.
- **Sample audit:** known sample URLs resolve to embedded snapshots even when offline.
- **Live audit:** only validated public GitHub repository URLs are fetched.
- **Cache hit:** a fresh in-memory snapshot is reused for its owner/repository key.
- **LLM unavailable:** heuristic analysis proceeds and the engine/warning explains the fallback.
- **Partial scan:** output lists scanned files and limits; it never equates absence in the scan with absence in the full repository.
- **Fetch error:** return a structured 4xx/503 error or a sample fallback, never an unhandled server exception.
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
- The app includes three deterministic offline sample snapshots, in-memory TTL repository caching, bounded GitHub retrieval, line-numbered evidence, deterministic fallback analysis, and optional live LLM analysis.
- The required endpoints are `GET /`, `GET /api/health`, `GET /api/samples`, `POST /api/audit`, and `POST /api/evaluate-viva`.
- The code is a human-review aid, not an automated hiring decision.
- A separate frontend deployment remains possible, but the default demo serves its dashboard from FastAPI.
