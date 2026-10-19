"""ProofHire's self-contained FastAPI backend."""

from __future__ import annotations

import os
import re
from typing import Dict, List, Literal, Optional, Tuple
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()

APP_VERSION = "1.0.0"
MAX_CLAIM_LENGTH = 2000


def number_lines(source: str) -> str:
    """Prefix each line with its one-based source line number."""
    return "\n".join(f"{line_number}: {line}" for line_number, line in enumerate(source.splitlines(), 1))


SAMPLE_DATA = [
    {
        "sample_id": "fastapi-redis-jwt",
        "title": "FastAPI Backend with Exaggerated Redis/JWT Claim",
        "payload": {
            "repo_url": "https://github.com/proofhire-samples/fastapi-redis-jwt",
            "claim": "Built a FastAPI backend with Redis caching and JWT authentication for secure, scalable requests.",
        },
        "snapshot": {
            "metadata": {"owner": "proofhire-samples", "repo": "fastapi-redis-jwt", "stars": 12, "language": "Python"},
            "files": {
                "README.md": "# Demo FastAPI service\nA small API with no cache or authentication layer.\n",
                "requirements.txt": "fastapi==0.115.0\nuvicorn==0.30.6\n",
                "main.py": (
                    "from fastapi import FastAPI\n"
                    "\n"
                    "app = FastAPI()\n"
                    "\n"
                    "@app.get('/health')\n"
                    "def health():\n"
                    "    return {'status': 'ok'}\n"
                    "\n"
                    "if __name__ == '__main__':\n"
                    "    import uvicorn\n"
                    "    uvicorn.run(app, host='127.0.0.1', port=8000)\n"
                ),
            },
        },
    },
    {
        "sample_id": "express-scalability",
        "title": "Node.js Express API Claiming Production Scalability",
        "payload": {
            "repo_url": "https://github.com/proofhire-samples/express-scalability",
            "claim": "Designed a production-scale Express API with rate limiting, caching, and horizontal scalability.",
        },
        "snapshot": {
            "metadata": {"owner": "proofhire-samples", "repo": "express-scalability", "stars": 8, "language": "JavaScript"},
            "files": {
                "README.md": "# Express demo\nA single-process example service.\n",
                "package.json": '{"dependencies":{"express":"^4.21.0"}}\n',
                "server.js": (
                    "const express = require('express');\n"
                    "const app = express();\n"
                    "\n"
                    "app.get('/health', (_req, res) => {\n"
                    "  res.json({ status: 'ok' });\n"
                    "});\n"
                    "\n"
                    "app.listen(3000, () => console.log('server ready'));\n"
                ),
            },
        },
    },
    {
        "sample_id": "python-ml-quality",
        "title": "Python ML Pipeline Claiming Automated Testing & Docker",
        "payload": {
            "repo_url": "https://github.com/proofhire-samples/python-ml-quality",
            "claim": "Built a scikit-learn ML pipeline with comprehensive pytest coverage and a Docker deployment.",
        },
        "snapshot": {
            "metadata": {"owner": "proofhire-samples", "repo": "python-ml-quality", "stars": 21, "language": "Python"},
            "files": {
                "README.md": "# ML demo\nA small model-training script.\n",
                "requirements.txt": "scikit-learn==1.5.2\npandas==2.2.3\n",
                "train.py": (
                    "from sklearn.linear_model import LogisticRegression\n"
                    "from sklearn.pipeline import make_pipeline\n"
                    "\n"
                    "def build_model():\n"
                    "    return make_pipeline(LogisticRegression())\n"
                    "\n"
                    "def train(features, labels):\n"
                    "    model = build_model()\n"
                    "    model.fit(features, labels)\n"
                    "    return model\n"
                ),
            },
        },
    },
]

SAMPLES_BY_REPOSITORY: Dict[str, dict] = {
    f"{sample['snapshot']['metadata']['owner']}/{sample['snapshot']['metadata']['repo']}": sample
    for sample in SAMPLE_DATA
}

FEATURES = {
    "FastAPI": {
        "claim": r"\bfast\s*api\b|\bfastapi\b",
        "source": r"\bFastAPI\b|from\s+fastapi",
        "manifest": r"\bfastapi\b",
    },
    "Express": {
        "claim": r"\bexpress(?:\.js)?\b",
        "source": r"require\(['\"]express['\"]\)|from\s+['\"]express['\"]",
        "manifest": r"['\"]express['\"]\s*:",
    },
    "React": {
        "claim": r"\breact\b",
        "source": r"from\s+['\"]react['\"]|require\(['\"]react['\"]\)|useState\s*\(",
        "manifest": r"['\"]react['\"]\s*:",
    },
    "JWT": {
        "claim": r"\bjwt\b|json web token",
        "source": r"jwt\.encode|jwt\.decode|create_access_token|OAuth2PasswordBearer",
        "manifest": r"python-jose|pyjwt|jsonwebtoken",
    },
    "OAuth": {
        "claim": r"\boauth\b",
        "source": r"OAuth2|oauthlib|authorization_code",
        "manifest": r"authlib|oauthlib",
    },
    "Redis": {
        "claim": r"\bredis\b",
        "source": r"Redis\s*\(|redis\.(?:get|set|from_url)|from\s+redis",
        "manifest": r"\bredis\b",
    },
    "caching": {
        "claim": r"\bcach(?:e|ing)\b",
        "source": r"@lru_cache|@cache|cachetools|cache\.set|cache\.get",
        "manifest": r"cachetools|fastapi-cache",
    },
    "Docker": {
        "claim": r"\bdocker\b|containeri[sz]",
        "source": r"^\s*FROM\s+\S+|docker\.compose",
        "manifest": r"docker",
    },
    "Kubernetes": {
        "claim": r"\bkubernetes\b|\bk8s\b",
        "source": r"apiVersion:\s*v1|kind:\s*(?:Deployment|Service)",
        "manifest": r"kubernetes",
    },
    "PostgreSQL": {
        "claim": r"\bpostgres(?:ql)?\b",
        "source": r"postgres(?:ql)?://|psycopg|create_engine",
        "manifest": r"psycopg|asyncpg|postgres",
    },
    "MongoDB": {
        "claim": r"\bmongodb\b|\bmongo\b",
        "source": r"MongoClient|mongodb(?:\+srv)?://",
        "manifest": r"pymongo|motor",
    },
    "SQLite": {
        "claim": r"\bsqlite\b",
        "source": r"sqlite3\.connect|sqlite://",
        "manifest": r"sqlite",
    },
    "async/await": {
        "claim": r"\basync(?:hronous)?\b|\bawait\b",
        "source": r"\basync\s+def\b|\bawait\s+",
        "manifest": r"asyncio",
    },
    "pytest": {
        "claim": r"\bpytest\b|\bunit tests?\b|\bautomated tests?\b",
        "source": r"\bdef\s+test_\w+|pytest|assert\s+",
        "manifest": r"\bpytest\b",
    },
    "rate limiting": {
        "claim": r"rate.limit|throttl",
        "source": r"RateLimiter|rate_limit|slowapi|limits\.",
        "manifest": r"slowapi|flask-limiter|express-rate-limit",
    },
    "WebSockets": {
        "claim": r"\bwebsocket",
        "source": r"WebSocket|websocket\.route|io\(\)",
        "manifest": r"websocket|socket\.io",
    },
    "microservices": {
        "claim": r"\bmicroservices?\b",
        "source": r"service discovery|grpc\.|@app\.rpc",
        "manifest": r"grpcio|consul",
    },
    "scikit-learn": {
        "claim": r"scikit.learn|\bsklearn\b|\bmachine learning\b|\bml pipeline\b",
        "source": r"from\s+sklearn|import\s+sklearn",
        "manifest": r"scikit-learn",
    },
    "PyTorch": {
        "claim": r"\bpytorch\b|\btorch\b",
        "source": r"import\s+torch|from\s+torch",
        "manifest": r"\btorch\b",
    },
}

MANIFEST_NAMES = {
    "requirements.txt",
    "package.json",
    "pyproject.toml",
    "pom.xml",
    "cargo.toml",
    "go.mod",
}
SOURCE_EXTENSIONS = (".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs", ".cs", ".rb", ".php")


class AuditRequest(BaseModel):
    repo_url: str = Field(..., max_length=2048)
    claim: str = Field(..., min_length=1, max_length=MAX_CLAIM_LENGTH)
    github_token: Optional[str] = None
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_provider: Optional[str] = "auto"


class ClaimBreakdownItem(BaseModel):
    claimed_feature: str
    status: Literal["verified", "partial", "missing"]
    evidence_file: Optional[str] = None
    evidence_lines: Optional[str] = None
    explanation: str


class Finding(BaseModel):
    severity: Literal["high", "medium", "low"]
    file: str
    lines: str
    title: str
    description: str
    code_snippet: str
    recommendation: str


class VivaQuestion(BaseModel):
    id: int
    file: str
    line_range: str
    difficulty: str
    question: str
    why_asked: str
    expected_concepts: List[str]
    code_context: str
    refactored_fix_snippet: str


class RepoMetadata(BaseModel):
    owner: str
    repo: str
    stars: int
    language: str
    files_scanned: List[str]
    analysis_engine: str
    cached: bool


class AuditResponse(BaseModel):
    repo_metadata: RepoMetadata
    credibility_score: int
    verdict: str
    summary: str
    claim_breakdown: List[ClaimBreakdownItem]
    findings: List[Finding]
    viva_questions: List[VivaQuestion]
    warnings: List[str] = []
    scan_limits: List[str] = []


def repository_key(repo_url: str) -> Tuple[str, str]:
    raw_url = repo_url.strip()
    if not raw_url:
        raise HTTPException(status_code=400, detail="repo_url is required.")
    normalized_url = raw_url if "://" in raw_url else f"https://{raw_url}"
    parsed = urlparse(normalized_url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"github.com", "www.github.com"}:
        raise HTTPException(status_code=400, detail="Enter a valid GitHub repository URL, such as https://github.com/owner/repo.")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        raise HTTPException(status_code=400, detail="The GitHub URL must include both an owner and repository name.")
    owner, repo = parts[0], parts[1]
    if repo.lower().endswith(".git"):
        repo = repo[:-4]
    if not re.fullmatch(r"[A-Za-z0-9-]{1,39}", owner) or not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", repo):
        raise HTTPException(status_code=400, detail="The GitHub owner or repository name contains invalid characters.")
    if repo in {".", ".."}:
        raise HTTPException(status_code=400, detail="The GitHub repository name is invalid.")
    return owner, repo


def extract_claimed_features(claim: str) -> List[str]:
    features = [
        name
        for name, patterns in FEATURES.items()
        if re.search(patterns["claim"], claim, flags=re.IGNORECASE)
    ]
    if features:
        return features
    terms = re.findall(r"\b[A-Za-z][A-Za-z0-9+#.-]{2,}\b", claim)
    stop_words = {"built", "using", "used", "with", "that", "from", "this", "into", "for", "and", "the"}
    return list(dict.fromkeys(term for term in terms if term.lower() not in stop_words))[:3] or ["technical implementation"]


def find_feature_evidence(feature: str, files: Dict[str, str]) -> Tuple[str, Optional[str], Optional[str], bool]:
    patterns = FEATURES.get(feature)
    if not patterns:
        return "missing", None, None, False
    dependency_location: Optional[Tuple[str, int, str]] = None
    for path, content in files.items():
        is_manifest = path.rsplit("/", 1)[-1].lower() in MANIFEST_NAMES
        pattern = patterns["manifest"] if is_manifest else patterns["source"]
        for line_number, line in enumerate(content.splitlines(), 1):
            candidate = line.split(": ", 1)[1] if re.match(r"^\d+: ", line) else line
            if re.search(pattern, candidate, flags=re.IGNORECASE):
                if not is_manifest:
                    return "verified", path, str(line_number), True
                if dependency_location is None:
                    dependency_location = (path, line_number, line)
    if dependency_location:
        return "partial", dependency_location[0], str(dependency_location[1]), False
    return "missing", None, None, False


def build_sample_audit(request: AuditRequest, sample: dict) -> AuditResponse:
    metadata = sample["snapshot"]["metadata"]
    raw_files = sample["snapshot"]["files"]
    numbered_files = {path: number_lines(content) for path, content in raw_files.items()}
    claimed_features = extract_claimed_features(request.claim)
    breakdown: List[ClaimBreakdownItem] = []
    findings: List[Finding] = []
    for feature in claimed_features:
        status, evidence_file, evidence_line, implementation_found = find_feature_evidence(feature, numbered_files)
        if status == "verified":
            explanation = f"Implementation evidence for {feature} appears in the inspected source."
        elif status == "partial":
            explanation = f"The inspected dependencies mention {feature}, but implementation evidence was not found."
        else:
            explanation = f"No evidence for {feature} was found in the inspected sample files; this is not proof it is absent elsewhere."
        breakdown.append(
            ClaimBreakdownItem(
                claimed_feature=feature,
                status=status,
                evidence_file=evidence_file,
                evidence_lines=evidence_line,
                explanation=explanation,
            )
        )
        if status != "verified":
            snippet = ""
            if evidence_file and evidence_line:
                snippet = numbered_files[evidence_file].splitlines()[int(evidence_line) - 1]
            findings.append(
                Finding(
                    severity="high" if status == "missing" else "medium",
                    file=evidence_file or "Repository scan",
                    lines=evidence_line or "N/A",
                    title=f"{feature} is {'not evidenced' if status == 'missing' else 'only listed as a dependency'}",
                    description=explanation,
                    code_snippet=snippet,
                    recommendation=f"Provide a verifiable implementation of {feature} or narrow the resume claim.",
                )
            )
    score_map = {"verified": 100, "partial": 55, "missing": 0}
    score = round(sum(score_map[item.status] for item in breakdown) / max(1, len(breakdown)))
    if score >= 80:
        verdict = "Verified High Credibility"
    elif score >= 40:
        verdict = "Partially Verified - Gaps Found"
    else:
        verdict = "High Discrepancy / Exaggerated Claim"
    files_scanned = list(raw_files)
    source_candidates = [
        (path, numbered_files[path].splitlines()[0] if numbered_files[path].splitlines() else "")
        for path in files_scanned
        if path.lower().endswith(SOURCE_EXTENSIONS)
    ]
    if not source_candidates:
        source_candidates = [("Repository scan", "No source code was returned by the bounded scan.")]
    questions: List[VivaQuestion] = []
    for index in range(3):
        feature = claimed_features[index % len(claimed_features)]
        path, context = source_candidates[index % len(source_candidates)]
        line_range = "1" if path != "Repository scan" else "N/A"
        questions.append(
            VivaQuestion(
                id=index + 1,
                file=path,
                line_range=line_range,
                difficulty=("Foundational", "Intermediate", "Advanced")[index],
                question=f"How does the implementation shown at {path}:{line_range} support the claim about {feature}, and what trade-off does this approach introduce?",
                why_asked="Tests whether the candidate can explain the evidence and distinguish an implemented feature from a resume assertion.",
                expected_concepts=[feature, "implementation evidence", "trade-off"],
                code_context=context,
                refactored_fix_snippet="# Explain the observed implementation and its limits.",
            )
        )
    return AuditResponse(
        repo_metadata=RepoMetadata(
            owner=metadata["owner"],
            repo=metadata["repo"],
            stars=metadata["stars"],
            language=metadata["language"],
            files_scanned=files_scanned,
            analysis_engine="heuristic",
            cached=False,
        ),
        credibility_score=score,
        verdict=verdict,
        summary=f"The bounded sample scan found support for {sum(item.status == 'verified' for item in breakdown)} of {len(breakdown)} detected claim features. This is an evidence aid, not a hiring decision.",
        claim_breakdown=breakdown,
        findings=findings,
        viva_questions=questions,
        warnings=[],
        scan_limits=["This is a bundled demo snapshot, not a complete repository scan."],
    )


app = FastAPI(
    title="ProofHire API",
    version=APP_VERSION,
    description="Audit resume claims against bounded GitHub repository evidence.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def auth_configuration() -> dict:
    return {
        "github_token": bool(os.getenv("GITHUB_TOKEN")),
        "llm_key": bool(os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")),
    }


@app.get("/")
@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "ProofHire API",
        "version": APP_VERSION,
        "docs_url": "/docs",
        "auth_configured": auth_configuration(),
    }


@app.get("/api/samples")
def get_samples() -> dict:
    samples = []
    for sample in SAMPLE_DATA:
        snapshot = sample["snapshot"]
        samples.append(
            {
                "sample_id": sample["sample_id"],
                "title": sample["title"],
                "payload": sample["payload"],
                "fallback_snapshot": {
                    "metadata": snapshot["metadata"],
                    "files": {path: number_lines(content) for path, content in snapshot["files"].items()},
                },
            }
        )
    return {"samples": samples}


@app.post("/api/audit", response_model=AuditResponse)
def audit(request: AuditRequest) -> AuditResponse:
    owner, repo = repository_key(request.repo_url)
    normalized_key = f"{owner.lower()}/{repo.lower()}"
    sample = SAMPLES_BY_REPOSITORY.get(normalized_key)
    if sample is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "live_repository_fetch_not_ready",
                "message": "Live GitHub retrieval is added in the next build slice. Use a repository URL from /api/samples for now.",
            },
        )
    if not request.claim.strip():
        raise HTTPException(status_code=400, detail="claim must not be empty.")
    return build_sample_audit(request, sample)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
