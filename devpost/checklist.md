---
doc: checklist
status: approved
---

# Build Checklist

Build mode: fast

## Slices

- [x] **1. Sample-backed audits return usable evidence**
  Becomes usable: The FastAPI service starts and a frontend can check health, load offline demo samples, and submit a sample audit that returns line-numbered evidence, a score, and three viva questions without credentials.
  Why now: Bootstrapping is part of the first working behavior, and the unique claim-to-evidence kernel is proven immediately with deterministic sample data before network or model complexity is added.
  PRD ref: `prd.md > The Core Journey`, `prd.md > Health and Samples`, `prd.md > Audit Request`
  Spec ref: `spec.md > Stack`, `spec.md > Components`, `spec.md > API and Data Model`
  Build: Add the single-file FastAPI app, request/response models, CORS, environment/key resolution, health and sample routes, three embedded snapshots, line numbering, and a deterministic sample audit path. Add `.gitignore`, `requirements.txt`, and `.env.example`.
  Verify (mechanical): Install `requirements.txt`, run the app locally, then call `/api/health`, `/api/samples`, and `/api/audit` for each bundled sample; confirm 200 JSON responses, 3 samples/questions, scores within 0–100, and citations whose line numbers exist in returned file contents.
  Learner check: Start the backend, open `/docs`, load one sample from `/api/samples`, submit its payload to `/api/audit`, and check that a cited file and line appear in the response.
  Commit: `Build sample-backed ProofHire audit API`

- [x] **2. Live GitHub audits and resilient optional LLM analysis work**
  Becomes usable: A frontend can audit a real public GitHub repository with bounded file retrieval, caching, exact citations, and optional Gemini/OpenAI analysis that falls back to deterministic results when keys or providers are unavailable.
  Why now: Sample-backed behavior already proves the core output contract; this slice adds the external data and provider risks without making the demo dependent on them.
  PRD ref: `prd.md > Audit Request`, `prd.md > States and Boundaries`
  Spec ref: `spec.md > GitHub URL and repository reader`, `spec.md > Cache and offline samples`, `spec.md > Audit engine`, `spec.md > Failure Modes and Safety Boundaries`
  Build: Implement strict GitHub URL parsing, bounded metadata/tree/file retrieval, optional token support, TTL cache, fetch warnings/errors, language/dependency/source heuristics, Gemini/OpenAI REST calls, strict JSON parsing, citation validation, and fallback to heuristic analysis.
  Verify (mechanical): Run focused checks for URL formats and invalid hosts; mock or exercise GitHub success/404/rate-limit/timeout responses; verify line citations resolve to fetched content; confirm repeated repository requests hit cache and malformed/failed LLM responses fall back without 500 errors.
  Learner check: Submit a public repository URL and one claim through `/docs`; compare one returned citation with the actual file path and line, then repeat the request and inspect the cache/engine metadata.
  Commit: `Add resilient GitHub and LLM audit engines`

- [x] **3. Viva evaluation and complete API behavior are verified**
  Becomes usable: The separate frontend can evaluate candidate answers with or without an LLM key, and all requested endpoints, error paths, sample flows, and setup instructions have been checked together.
  Why now: Viva evaluation depends on stable question output from the audit; final integration checks verify the full backend contract after its dependencies are in place.
  PRD ref: `prd.md > Viva Answer Evaluation`, `prd.md > API Behavior and Acceptance Criteria`, `prd.md > States and Boundaries`
  Spec ref: `spec.md > Viva evaluator`, `spec.md > API and Data Model`, `spec.md > Where It Runs and How Someone Tries It`
  Build: Implement deterministic concept/depth scoring and optional LLM answer evaluation with fallback; validate all API response shapes, structured errors, CORS behavior, and local setup instructions.
  Verify (mechanical): Exercise `GET /`, `/api/health`, `/api/samples`, `POST /api/audit`, and `POST /api/evaluate-viva`; test weak and strong answers, invalid URL, empty repository, and offline samples; confirm JSON shapes and no unhandled 500 responses.
  Learner check: Use one sample question with an empty answer and then a thoughtful answer in `/docs`; compare scores, matched/missed concepts, and feedback.
  Commit: `Complete viva evaluation and verify backend`

## Hands-on Checkpoints

- [x] Early usable behavior explored — after slice 1, before live GitHub/provider work
- [x] Final kick-the-tires exploration and feedback completed

## Final Review

- [x] Final review complete — feedback resolved and learner confirms ready to ship

## Code Tour and App Map

- [x] Learning activity complete — evidence-based recap connected to the learner's goal and verified endpoint behavior
- [x] Optional edit and transfer reflection addressed — not requested; learner asked to proceed without extra questions
- [x] `devpost/app-map.html` generated from finished code, checked, and shown, including a project-grounded practice to reuse

Activity and evidence: Final hands-on review at `/docs`: learner tested `GET /api/samples` and `POST /api/audit` and reported clean evidence and viva questions, then confirmed everything looked good. Independent HTTP checks also verified `POST /api/evaluate-viva` returns 200 on ports 8000 and 8001; all endpoint smoke checks passed.
Route and stops: Reference route only (not toured live): `main.py` `audit` → `repository_key`/`fetch_repository` → `build_heuristic_audit` or `build_llm_audit`; viva answers enter `evaluate_viva`.
Edit outcome: Not applicable; no final-review changes were requested.
Reflection: Not requested; learner asked to proceed without additional questions.
Activity mode: Evidence-based recap after learner's live API review; static code route provided in the app map.

## Revisions
