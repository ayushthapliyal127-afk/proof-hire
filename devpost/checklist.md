---
doc: checklist
status: approved
---

# Build Checklist

Build mode: fast

## Slices

- [x] **1. Sample-backed audits return usable evidence**
  Becomes usable: The FastAPI service starts and a frontend can check health, load offline demo samples, and submit a sample audit with `fallback_policy: allow_heuristic` to return line-numbered evidence, a score, and three viva questions without provider credentials.
  Why now: Bootstrapping is part of the first working behavior, and the unique claim-to-evidence kernel is proven immediately with deterministic sample data under the explicitly selected heuristic policy before network or model complexity is added.
  PRD ref: `prd.md > The Core Journey`, `prd.md > Health and Samples`, `prd.md > Audit Request`
  Spec ref: `spec.md > Stack`, `spec.md > Components`, `spec.md > API and Data Model`
  Build: Add the single-file FastAPI app, request/response models, CORS, environment/key resolution, health and sample routes, three embedded snapshots, line numbering, and a deterministic sample audit path. Add `.gitignore`, `requirements.txt`, and `.env.example`.
  Verify (mechanical): Install `requirements.txt`, run the app locally, then call `/api/health`, `/api/samples`, and `/api/audit` for each bundled sample with `fallback_policy: allow_heuristic`; confirm 200 JSON responses, 3 samples/questions, scores within 0–100, and citations whose line numbers exist in returned file contents.
  Learner check: Start the backend, open `/docs`, load one sample from `/api/samples`, submit its payload to `/api/audit`, and check that a cited file and line appear in the response.
  Commit: `Build sample-backed ProofHire audit API`

- [x] **2. Live GitHub audits and resilient optional LLM analysis work**
  Becomes usable: A frontend can audit a real public GitHub repository with bounded file retrieval, caching, exact citations, and optional Gemini/OpenAI analysis; deterministic results are available only when `allow_heuristic` is explicitly selected.
  Why now: Sample-backed behavior already proves the core output contract; this slice adds the external data and provider risks without making the demo dependent on them.
  PRD ref: `prd.md > Audit Request`, `prd.md > States and Boundaries`
  Spec ref: `spec.md > GitHub URL and repository reader`, `spec.md > Cache and offline samples`, `spec.md > Audit engine`, `spec.md > Failure Modes and Safety Boundaries`
  Build: Implement strict GitHub URL parsing, bounded metadata/tree/file retrieval, optional token support, TTL cache, fetch warnings/errors, language/dependency/source heuristics, Gemini/OpenAI REST calls, strict JSON parsing, citation validation, and policy-controlled heuristic analysis.
  Verify (mechanical): Run focused checks for URL formats and invalid hosts; mock or exercise GitHub success/404/rate-limit/timeout responses; verify line citations resolve to fetched content; confirm repeated repository requests hit cache and malformed/failed LLM responses follow the selected policy without unhandled 500 errors.
  Learner check: Submit a public repository URL and one claim through `/docs`; compare one returned citation with the actual file path and line, then repeat the request and inspect the cache/engine metadata.
  Commit: `Add resilient GitHub and LLM audit engines`

- [x] **3. Viva evaluation and complete API behavior are verified**
  Becomes usable: The frontend can evaluate answers with an LLM key or, when `allow_heuristic` is explicitly selected, with deterministic concept/depth grading; all requested endpoints, error paths, sample flows, and setup instructions have been checked together.
  Why now: Viva evaluation depends on stable question output from the audit; final integration checks verify the full backend contract after its dependencies are in place.
  PRD ref: `prd.md > Viva Answer Evaluation`, `prd.md > API Behavior and Acceptance Criteria`, `prd.md > States and Boundaries`
  Spec ref: `spec.md > Viva evaluator`, `spec.md > API and Data Model`, `spec.md > Where It Runs and How Someone Tries It`
  Build: Implement deterministic concept/depth scoring and optional LLM answer evaluation with policy-controlled fallback; validate all API response shapes, structured errors, CORS behavior, and local setup instructions.
  Verify (mechanical): Exercise `GET /`, `/api/health`, `/api/samples`, `POST /api/audit`, and `POST /api/evaluate-viva`; test weak and strong answers, invalid URL, empty repository, and offline samples; confirm JSON shapes and no unhandled 500 responses.
  Learner check: Use one sample question with an empty answer and then a thoughtful answer in `/docs`; compare scores, matched/missed concepts, and feedback.
  Commit: `Complete viva evaluation and verify backend`

- [x] **4. The served dashboard completes the audit and viva flow**
  Becomes usable: A user opens `/`, checks service status, loads a sample or enters a repository and claim, reads the audit evidence, and submits answers for grading without leaving the page.
  Why now: The API contract is stable and the learner has approved bringing the previously separate frontend into the same app; serving it from FastAPI keeps setup simple and makes the project immediately demoable.
  PRD ref: `prd.md > The Core Journey`, `prd.md > What We're Building`, `prd.md > Dashboard, Health and Samples`, `prd.md > Audit Request`, `prd.md > Viva Answer Evaluation`
  Spec ref: `spec.md > Where It Runs and How Someone Tries It`, `spec.md > Components > Static dashboard`, `spec.md > File Structure`
  Build: Add the responsive Tailwind/Lucide dashboard at `static/index.html`, render backend status/samples/audit/evaluation data safely, add in-memory key settings and progress/error states, mount `/static`, and serve the page at `/`.
  Verify (mechanical): Compile/import `main.py`; start Uvicorn; verify `/` returns the HTML shell, `/static/` loads the dashboard, health and samples work, sample audit and viva evaluation return usable JSON, and frontend code references the expected routes with safe text rendering.
  Learner check: Open the dashboard, load a sample, run an audit, inspect an evidence citation, and submit an answer for grading; learner reported that the page looked amazing and sample loading, audits, and grading worked smoothly.
  Commit: `Add served ProofHire audit dashboard`

## Hands-on Checkpoints

- [x] Early usable behavior explored — after slice 1, before live GitHub/provider work
- [x] Final kick-the-tires exploration and feedback completed

## Final Review

- [x] Final review complete — feedback resolved and learner confirms ready to ship

## Code Tour and App Map

- [x] Learning activity complete — evidence-based recap connected to the learner's goal and verified endpoint behavior
- [x] Optional edit and transfer reflection addressed — no edit or transfer reflection requested
- [x] `devpost/app-map.html` generated from finished code, checked, and shown, including a project-grounded practice to reuse

Activity and evidence: Learner reviewed the served dashboard at port 8001, loaded a sample, ran audits, and submitted a viva answer; reported that all worked smoothly and the dashboard looked amazing. Independent smoke checks verified `/`, `/static/index.html`, `/api/health`, `/api/samples`, `/api/audit`, and `/api/evaluate-viva`. Connected the observed claim-to-evidence flow to the learner's goal of understanding how AI compares claims with code.
Route and stops: Reference route shown in `devpost/app-map.html` (not toured live): `main.py` `dashboard` → `static/index.html` audit form submit handler → `/api/audit` → `renderReport`; per-question form submit handler → `/api/evaluate-viva`.
Edit outcome: Not applicable; no dashboard changes were requested during review.
Reflection: Optional transfer reflection not requested.
Activity mode: Evidence-based recap after learner's live dashboard review; static reference route available in the app map.

## Revisions

- Added the served Tailwind/Lucide frontend and revised the default journey from a backend-only service to a same-origin dashboard after the learner requested frontend creation and integration.
