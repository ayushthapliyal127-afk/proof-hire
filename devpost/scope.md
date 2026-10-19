---
doc: scope
status: approved
---

# ProofHire

ProofHire is a Python FastAPI app with a dark-mode dashboard that compares one resume claim with evidence from a GitHub repository and returns line-grounded findings and technical viva questions. Its static frontend and REST API are served by the same local service.

## The Unique Kernel

The backend gathers a bounded, inspectable set of repository files, compares a technical claim with that evidence using an optional live LLM and a deterministic no-key analyzer, and returns findings and viva questions tied to real file paths and line numbers. Model output is never treated as proof: citations must resolve to fetched source, and a bounded scan cannot establish that a feature is absent everywhere in a repository.

## Who It's For

The primary use is a developer, reviewer, or interviewer who wants to examine whether a technical resume claim is supported by a public repository. The output supports human review; it does not infer authorship or recommend hiring outcomes.

## The Core Loop

1. The user opens the dashboard and enters a GitHub repository URL and one resume claim, or loads a built-in sample payload.
2. The backend validates the URL, retrieves repository metadata and a bounded selection of text files, or uses an embedded sample snapshot for a known demo repository.
3. The backend compares the claim with numbered code and dependency evidence. It uses Gemini or OpenAI when a key is available and falls back to deterministic inspection when no key is configured or a provider fails.
4. The dashboard displays a structured audit containing evidence, limitations, a credibility score, and technical viva questions.
5. The user may submit an answer to a viva question and receive an LLM evaluation or a deterministic concept/depth evaluation.

## Why This Matters to the Learner

The learner wants to understand how AI checks a repository against a claim.

## What "Working" Looks Like

The FastAPI app serves a responsive dashboard at `/`, its JSON API, and three repeatable sample snapshots. The user can audit a claim, inspect exact source line citations, and submit answers to viva questions. The three built-in samples work without GitHub or LLM credentials so the demo remains repeatable offline.

## The POC Boundary

Build the complete app with the FastAPI backend in `main.py` and a static dashboard in `static/index.html`, with dependency and environment examples and repeatable local verification. Support public GitHub repositories, bounded scans, in-memory caching, optional GitHub/Gemini/OpenAI credentials, deterministic fallback analysis, optional LLM analysis, sample snapshots, audit and viva-evaluation endpoints, and permissive CORS. The static frontend calls the same-origin API; no separate frontend build system or database is required.

## Later

- Persistent audit history, user accounts, organization roles, and saved reports.
- Private repository support, candidate workflows, and hiring-system integrations.
- Durable distributed caching, background jobs, repository-wide indexing, and operational monitoring.
- Production deployment, managed secrets, usage quotas, and formal security/compliance review.

## Explicitly Cut

- Automated hiring decisions, candidate ranking, or claims that code proves authorship or personal competence.
- Treating a feature not found in the bounded scan as proof that the repository lacks it.
- Reading arbitrary URLs or private repositories; only validated GitHub repository URLs are accepted.
- A database, account system, or persistent storage.
