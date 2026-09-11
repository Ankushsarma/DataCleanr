# AutoCleanAI — Technical Implementation Specification
**Companion to:** AutoCleanAI PRD v6.0
**Scope:** Stages 1–3, Modes 1–2 (per PRD Sections 32–33)

---

## 1. System Overview & Service Boundaries

The PRD's pipeline (Section 11) maps to discrete services rather than one monolith, because each stage has a different scaling profile, failure mode, and trust boundary.

| Service | Responsibility | Scales with | Trust boundary |
| :--- | :--- | :--- | :--- |
| **Ingestion API** | Upload, validation, dataset registration | Concurrent uploads | User-facing, authenticated |
| **Profiler Worker** | Deterministic EDA (Polars) | Rows × columns | No LLM, no external calls |
| **Issue Detector** | Rule-based issue detection | Rows × columns | No LLM |
| **Evidence Compiler** | Aggregates profiler + detector output into compressed evidence package | Issues × columns | No raw data by default |
| **Agent Orchestrator** | Single-agent reasoning calls, retry loop | Issues, LLM latency | Calls external LLM provider |
| **Policy Engine** | Candidate filtering, final IR check | Candidates | Pure function, no I/O side effects |
| **Selection Engine** | Deterministic scoring/ranking | Candidates per issue | Pure function |
| **Compiler** | IR → executable Polars operation graph | IR size | No LLM, no arbitrary code execution |
| **Sandbox Executor** | Runs compiled operations in isolation | Dataset size | Isolated compute (container/process) |
| **Validation Engine** | Execution/constraint/preservation/policy checks | Dataset size | No LLM, no I/O outside job scope |
| **Audit Service** | Append-only provenance log | Jobs × transformations | Immutable store |
| **Approval Service** | HIGH-risk workflow, SLA timers | Pending approvals | Role-gated |

This decomposition is what lets Section 12's "two authorities" (Policy Engine, Validation Engine) remain **pure, side-effect-free, independently testable** components — critical since they're the safety backbone the whole architecture leans on.

---

## 2. Technology Stack

| Layer | Choice | Rationale |
| :--- | :--- | :--- |
| Data engine | **Polars** (lazy API) | PRD-mandated; columnar, out-of-core capable for the 2GB/10M-row ceiling (Section 7) |
| Backend services | **Python 3.12 + FastAPI** | Async I/O for LLM calls; Pydantic aligns with IR schema validation needs |
| Job orchestration | **Temporal** (or AWS Step Functions for Stage 2+) | Needed for retry/replanning (Section 24), PENDING_APPROVAL state (Section 19), and terminal-state guarantees (Section 6.7) — these are workflow semantics, not just task queues |
| Task queue (Stage 1) | **Celery + Redis** | Simplest local-prototype option before Temporal/Step Functions adoption |
| LLM access | **AWS Bedrock (default)**, provider-agnostic client interface | PRD-mandated default; abstraction layer allows "Alternative model/provider" fallback (Section 13) |
| Sandbox execution | **gVisor-wrapped subprocess** or **Firecracker microVM** (cloud), **restricted subprocess w/ resource limits** (local) | No arbitrary Python execution (Non-Goal, Section 5); operations are IR-compiled, not agent-authored code |
| Database (metadata, audit, jobs) | **PostgreSQL** | Append-only audit tables (Section 26), row-level access control (Section 17) |
| Object storage | **S3** (raw dataset, transformed dataset, evidence packages) | Immutability of raw dataset (Section 26) via versioned buckets + Object Lock |
| Secrets | **AWS Secrets Manager + KMS** | Per Section 18 |
| Auth | **OAuth2/OIDC (e.g., Cognito or Auth0)** + RBAC middleware | Maps to Section 17 role table |
| Observability | **CloudWatch + OpenTelemetry traces** | Job/cost/latency reporting (Section 6.6, 6.9) |
| Frontend | **Next.js/React + Tailwind** | UI requirements (Section 31) |

---

## 3. Data Model

### 3.1 Core Postgres Schema (abbreviated DDL)

```sql
CREATE TABLE datasets (
    dataset_id UUID PRIMARY KEY,
    namespace_id UUID NOT NULL REFERENCES namespaces(namespace_id),
    raw_s3_uri TEXT NOT NULL,
    raw_hash TEXT NOT NULL,               -- SHA-256, immutable
    schema_json JSONB NOT NULL,
    row_count BIGINT,
    column_count INT,
    created_by UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE jobs (
    job_id UUID PRIMARY KEY,
    dataset_id UUID NOT NULL REFERENCES datasets(dataset_id),
    mode TEXT NOT NULL CHECK (mode IN ('ASSISTED','AUTONOMOUS','PIPELINE')),
    state TEXT NOT NULL CHECK (state IN
        ('RUNNING','PENDING_APPROVAL','ACCEPTED','REJECTED','UNRESOLVED','FAILED')),
    policy_version TEXT NOT NULL,
    profiler_version TEXT NOT NULL,
    agent_version TEXT NOT NULL,
    ir_schema_version TEXT NOT NULL,
    compiler_version TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at TIMESTAMPTZ,
    cost_usd NUMERIC(10,4),
    llm_calls INT DEFAULT 0,
    tokens_used BIGINT DEFAULT 0
);
-- Every job MUST end in one of the four terminal states (Section 6.7) or RUNNING/PENDING_APPROVAL as
-- transient states; a nightly reconciliation job flags anything stuck outside these for >max_job_duration.

CREATE TABLE issues (
    issue_id UUID PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES jobs(job_id),
    column_name TEXT,
    issue_type TEXT NOT NULL,             -- e.g. MISSING, INVALID, INCONSISTENT_CATEGORY, DUPLICATE
    evidence_ref TEXT NOT NULL,           -- S3 pointer to compressed evidence package
    decision TEXT CHECK (decision IN ('KEEP','FLAG','MODIFY')),
    final_state TEXT
);

CREATE TABLE candidates (
    candidate_id UUID PRIMARY KEY,
    issue_id UUID NOT NULL REFERENCES issues(issue_id),
    strategy TEXT NOT NULL,               -- e.g. GROUPWISE_MEDIAN_IMPUTATION
    ir_json JSONB NOT NULL,
    agent_confidence TEXT CHECK (agent_confidence IN ('LOW','MEDIUM','HIGH')),
    agent_rationale TEXT,
    risk_level TEXT CHECK (risk_level IN ('LOW','MEDIUM','HIGH')),
    policy_eligible BOOLEAN,
    validation_result JSONB,              -- execution/constraint/preservation/policy sub-scores
    selection_score NUMERIC,
    selected BOOLEAN DEFAULT FALSE
);

-- Append-only. No UPDATE or DELETE grants at the DB role level.
CREATE TABLE audit_log (
    audit_id BIGSERIAL PRIMARY KEY,
    job_id UUID NOT NULL,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    raw_dataset_hash TEXT NOT NULL,
    transformation_hash TEXT,
    final_dataset_hash TEXT,
    actor_id UUID,                        -- NULL for system-generated events
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE approvals (
    approval_id UUID PRIMARY KEY,
    candidate_id UUID NOT NULL REFERENCES candidates(candidate_id),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    decided_by UUID,
    decision TEXT CHECK (decision IN ('APPROVED','REJECTED','TIMED_OUT')),
    decided_at TIMESTAMPTZ,
    sla_deadline TIMESTAMPTZ NOT NULL      -- default now() + 24h, per Section 19
);
```

### 3.2 Access control enforcement

RBAC (Section 17) is enforced at two layers, not just the API:
1. **API middleware** — checks role against endpoint (e.g., only Approver/Admin can `POST /approvals/{id}/decide`).
2. **Row-level security (Postgres RLS)** on `datasets`, `jobs`, `audit_log` keyed on `namespace_id`, so a compromised API layer still can't cross namespaces. Pipeline mode's service-identity path uses a separate `service_principals` table with scoped namespace grants, never a human role.

---

## 4. The Intermediate Representation (IR)

This is the single most important contract in the system — it's what makes "AI proposes, deterministic system executes" (Section 12) actually true. The agent **never** returns executable code; it returns IR that is validated, then compiled.

### 4.1 IR JSON Schema (v1)

```json
{
  "ir_version": "1.0",
  "issue_id": "uuid",
  "operation": "IMPUTE_GROUPWISE_MEDIAN",
  "target_column": "income",
  "group_by": ["region", "employment_type"],
  "parameters": {
    "fallback": "GLOBAL_MEDIAN",
    "min_group_size": 5
  },
  "scope": {
    "predicate": "income IS NULL",
    "estimated_affected_rows": 4108
  },
  "constraints": {
    "preserve_row_count": true,
    "preserve_columns": ["customer_id"],
    "max_modification_pct": 10.0
  },
  "risk_level": "MEDIUM",
  "agent_confidence": "HIGH",
  "rationale": "8.3% missing income; MCAR pattern by profiler; group medians stable (n>=5) across 94% of groups."
}
```

### 4.2 Operation Allowlist

The `operation` field is a closed enum, not free text. Stage 1 allowlist (extendable via versioned migration, never via agent request):

```
KEEP, FLAG,
IMPUTE_MEAN, IMPUTE_MEDIAN, IMPUTE_MODE,
IMPUTE_GROUPWISE_MEAN, IMPUTE_GROUPWISE_MEDIAN,
DROP_ROWS_EXACT_DUPLICATE, DROP_ROWS_PREDICATE,
NORMALIZE_CATEGORICAL, TRIM_WHITESPACE, CAST_TYPE,
CLIP_OUTLIERS, WINSORIZE, STANDARDIZE_DATE_FORMAT,
REGEX_REPLACE (allowlisted patterns only, no arbitrary regex from agent)
```

Each operation has a registered Polars implementation in the Compiler (Section 4.4). The agent selects **which** allowlisted operation + parameters; it cannot introduce a new operation type at inference time.

### 4.3 Validation Pipeline (Section 14, implemented)

```python
def validate_agent_response(raw_response: str) -> IRCandidate | RejectedResponse:
    # 1. JSON Schema validation
    parsed = json_schema_validate(raw_response, schema=IR_JSON_SCHEMA_V1)
    if not parsed.valid:
        return RejectedResponse(reason="SCHEMA_INVALID", detail=parsed.errors)

    # 2. IR structural validation (Pydantic model)
    try:
        ir = TransformationIR.model_validate(parsed.data)
    except ValidationError as e:
        return RejectedResponse(reason="IR_INVALID", detail=str(e))

    # 3. Operation allowlist check
    if ir.operation not in ALLOWED_OPERATIONS:
        return RejectedResponse(reason="OPERATION_NOT_ALLOWED", detail=ir.operation)

    # 4. Policy check (Section 20 pre-filter)
    policy_result = policy_engine.evaluate(ir, dataset_metadata)
    if not policy_result.eligible:
        return RejectedResponse(reason="POLICY_INELIGIBLE", detail=policy_result.violations)

    return IRCandidate(ir=ir, policy_result=policy_result)
```

No malformed or non-allowlisted response ever reaches the Compiler — this is enforced structurally (the Compiler's input type is `IRCandidate`, not `str`), not just by convention.

### 4.4 Compiler → Sandbox

The Compiler maps each `operation` to a pure Polars lazy-expression builder function:

```python
COMPILER_REGISTRY: dict[str, Callable[[TransformationIR, pl.LazyFrame], pl.LazyFrame]] = {
    "IMPUTE_GROUPWISE_MEDIAN": compile_groupwise_median,
    "DROP_ROWS_EXACT_DUPLICATE": compile_drop_exact_duplicates,
    # ...
}

def compile_ir(ir: TransformationIR, lf: pl.LazyFrame) -> pl.LazyFrame:
    builder = COMPILER_REGISTRY[ir.operation]
    return builder(ir, lf)
```

The resulting `LazyFrame` plan is what actually executes — inside the sandbox, with:
- **Resource limits**: CPU/memory/time caps (cgroups locally, Fargate task limits in cloud)
- **No network access** from the sandbox process
- **No filesystem access** outside a scoped scratch dir + read-only input mount
- **Execution timeout** feeding into the 30-minute max job duration (Section 7)

---

## 5. Evidence Package (Privacy Architecture, Section 15)

The Evidence Compiler builds a per-issue package sent to the agent. Default composition:

```json
{
  "column": "income",
  "dtype": "float64",
  "issue_type": "MISSING",
  "stats": {"null_pct": 8.3, "mean": 54210.2, "std": 18400.5, "n_groups": 12},
  "group_stats": [{"group": "region=west,employment_type=FT", "median": 61200, "n": 812}, "..."],
  "distribution_summary": {"histogram_bins": [...], "skew": 0.42},
  "sample_values": null   // only populated if privacy policy explicitly allows
}
```

Raw-row sampling path (only when profiler/agent cannot resolve ambiguity from aggregates):

```
Need identified (agent requests sample OR profiler flags need)
   → Privacy Policy Engine check (classification-aware, Section 16)
   → Sampling/masking service applies k-anonymity-style masking or column redaction
   → Audit event written (who/what/why/when) BEFORE the LLM call, not after
   → Bounded sample sent to LLM (max N rows, configurable, default N=20)
```

This is implemented as a **separate audited code path**, not a flag on the normal evidence builder, so raw-data exposure is easy to grep for in the codebase and in the audit log.

### 5.1 Sensitive Data Detection (Section 16, implementation)

```python
def classify_column(col_name: str, sample: pl.Series) -> Classification:
    # Layer 1: fast heuristic
    if COLUMN_NAME_PATTERNS.search(col_name):
        return Classification(sensitive=True, layer="NAME_HEURISTIC")

    # Layer 2: content scan (bounded sample, e.g. 500 values)
    scores = {
        "email": regex_match_rate(sample, EMAIL_REGEX),
        "phone": regex_match_rate(sample, PHONE_REGEX),
        "national_id": regex_match_rate(sample, NATIONAL_ID_REGEXES),
        "entropy": shannon_entropy_score(sample),
    }
    if max(scores.values()) > CONTENT_SCAN_THRESHOLD:
        return Classification(sensitive=True, layer="CONTENT_SCAN", detail=scores)

    return Classification(sensitive=False)
```

For RESTRICTED-classified columns, the evidence compiler hard-blocks raw-value transmission to external providers at the request-construction layer (i.e., the field is dropped before serialization, not filtered after).

---

## 6. Agent Orchestrator

### 6.1 Provider-agnostic client interface

```python
class LLMProvider(Protocol):
    async def complete(self, prompt: str, schema: dict, max_tokens: int) -> LLMResponse: ...

class BedrockProvider(LLMProvider): ...
class FallbackProvider(LLMProvider): ...  # secondary model/provider, Section 13

class AgentOrchestrator:
    def __init__(self, primary: LLMProvider, fallback: LLMProvider): ...

    async def propose(self, evidence: EvidencePackage) -> list[IRCandidate]:
        try:
            response = await self.primary.complete(...)
        except (TimeoutError, RateLimitError, APIError):
            response = await self._retry_or_fallback(evidence)
        return validate_agent_response(response)
```

### 6.2 Failure hierarchy (Section 13, as a state machine)

```
LLM_CALL
  ├─ success + valid → proceed to Policy Engine
  ├─ timeout/rate-limit → RETRY_SAME (bounded, exponential backoff)
  ├─ retries exhausted → FALLBACK_PROVIDER
  ├─ fallback fails → DETERMINISTIC_FALLBACK (KEEP/FLAG/MEDIAN/MODE per policy)
  └─ no deterministic option available → MARK_UNRESOLVED (issue-level, not job-level)
```

Implemented as explicit states in Temporal (or Step Functions) rather than nested try/except, so the job's terminal state (Section 6.7) is always derivable from workflow history, and a single issue failing never fails the whole job — the workflow fans out per-issue and joins results.

---

## 7. Policy Engine & Selection Engine

### 7.1 Policy Engine (pure function, versioned config)

```yaml
# policy_v3.yaml
operations:
  IMPUTE_GROUPWISE_MEDIAN:
    max_risk: MEDIUM
    max_modification_pct: 15.0
    requires_min_group_size: 5
  DROP_ROWS_EXACT_DUPLICATE:
    max_risk: LOW
    requires_hash_match: true
  DROP_ROWS_PREDICATE:
    max_risk: HIGH   # HIGH-risk row-loss ops always require approval
sensitive_columns:
  restricted_transformations_require_approval: true
row_retention:
  min_retention_pct: 90.0   # per-operation override allowed
```

Policy config is versioned (`policy_version` recorded per job/candidate, per Section 26) and loaded immutably per job — a mid-job policy update never changes an in-flight job's rules.

### 7.2 Selection Engine (Section 20, implemented)

```python
def selection_score(c: Candidate) -> float:
    return (
        WEIGHTS.validation   * c.validation_score
        + WEIGHTS.preservation * c.preservation_score
        + WEIGHTS.confidence   * CONFIDENCE_MAP[c.agent_confidence]
        - WEIGHTS.risk         * RISK_PENALTY[c.risk_level]
        - WEIGHTS.modification * c.unnecessary_modification_estimate
        - WEIGHTS.complexity   * c.transformation_complexity
    )

def select(candidates: list[Candidate]) -> SelectionResult:
    eligible = [c for c in candidates if c.policy_eligible and c.validation_passed]
    if not eligible:
        return SelectionResult(decision="KEEP_ORIGINAL", reason="no_eligible_candidate")
    scored = sorted(eligible, key=selection_score, reverse=True)
    top = scored[0].score
    near_tied = [c for c in scored if c.score >= top * (1 - NEAR_TIE_MARGIN)]  # default 10%, Section 31
    return SelectionResult(decision="MODIFY", selected=scored[0], near_tied=near_tied[:3])
```

`WEIGHTS` and `NEAR_TIE_MARGIN` are config, not code constants — they need to be tunable during the Section 28 evaluation without redeploys.

---

## 8. Validation Engine

Four independent sub-checks, each producing a sub-score and pass/fail, all required for ACCEPT:

```python
@dataclass
class ValidationResult:
    execution: SubResult      # did the compiled op run without error?
    constraints: SubResult    # schema/type/nullability constraints post-transform
    preservation: SubResult   # row retention, distribution divergence (Wasserstein), correlation delta
    policy: SubResult         # final IR re-check against current policy (Section 12: re-checked post-compile too)

    @property
    def accepted(self) -> bool:
        return all(r.passed for r in (self.execution, self.constraints, self.preservation, self.policy))
```

`preservation` is where UMR (Section 21) and distribution preservation (Section 27) are actually computed — by diffing the pre/post `LazyFrame` on the affected scope, using ground truth where available (benchmark mode) or statistical preservation checks otherwise (production mode, since ground truth usually doesn't exist in production).

---

## 9. Retry / Replanning Loop (Section 24)

```python
async def run_with_retry(issue: Issue, max_attempts: int = 3) -> IssueOutcome:
    failure_memory: list[FailedAttempt] = []
    for attempt in range(max_attempts):
        candidates = await orchestrator.propose(evidence, failure_memory=failure_memory)
        eligible = policy_engine.filter(candidates)
        if not eligible:
            failure_memory.append(FailedAttempt(reason="all_policy_ineligible", attempt=attempt))
            continue
        selection = selection_engine.select(eligible)
        result = await validation_engine.validate(selection.selected)
        if result.accepted:
            return IssueOutcome.accepted(selection.selected, result)
        failure_memory.append(FailedAttempt(
            candidate=selection.selected, validation_result=result, attempt=attempt
        ))
        if improvement_below_threshold(failure_memory):
            break
    return IssueOutcome.unresolved(reason="no_safe_transformation_found", history=failure_memory)
```

Key implementation detail from Section 24: **previously failed strategies cannot be reused without new evidence** — enforced by passing `failure_memory` into the prompt/evidence package on retry, and having the Policy Engine reject a candidate whose `strategy` + `parameters` hash matches a prior failed attempt with no new evidence delta.

---

## 10. Approval Workflow (Section 19)

Implemented as a Temporal signal-based workflow:

```python
@workflow.defn
class ApprovalWorkflow:
    @workflow.run
    async def run(self, candidate_id: UUID) -> ApprovalDecision:
        await notify_approvers(candidate_id)  # Approver/Admin in namespace
        try:
            decision = await workflow.wait_condition(
                lambda: self._decision is not None,
                timeout=timedelta(hours=24),  # configurable SLA
            )
            return self._decision
        except TimeoutError:
            return ApprovalDecision(status="TIMED_OUT")  # → job UNRESOLVED, never auto-approve

    @workflow.signal
    def decide(self, decision: ApprovalDecision):
        self._decision = decision
```

Job-level behavior differs by mode: Assisted/Autonomous block only the affected transformation (parent workflow continues other issue branches); Pipeline mode blocks promotion (Section 25) via a separate gate before the "promote" activity runs.

---

## 11. Audit & Provenance

Every state transition writes an append-only `audit_log` row. Enforcement of immutability:
- DB role for the application has `INSERT`-only grant on `audit_log`; no `UPDATE`/`DELETE` grants exist at all.
- `raw_hash` is computed at ingestion (SHA-256 over the S3 object) and never recomputed — reproducibility (Section 26, DoD #16) depends on being able to re-fetch the exact raw bytes.
- Version tuple recorded per job: `(platform_version, profiler_version, agent_version, prompt_template_hash, model_id, ir_schema_version, policy_version, compiler_version, dependency_lockfile_hash)`. Reproduction re-runs the pipeline pinned to this tuple; if any component's version is incompatible (e.g., IR schema migrated with breaking changes), the system reports "non-reproducible under current runtime" rather than silently re-running with different logic.

---

## 12. Deployment Architecture by Stage

### Stage 1 — Local Research Prototype
```
Local machine
 ├─ FastAPI (uvicorn)
 ├─ Celery + Redis (job queue)
 ├─ Local Postgres (docker)
 ├─ Local filesystem (raw/, transformed/, evidence/)
 ├─ Sandbox: subprocess + resource.setrlimit
 └─ LLM: Bedrock API (or local model via same provider interface)
```

### Stage 2 — Cloud Prototype
```
AWS
 ├─ ECS Fargate: API service, Profiler workers, Agent Orchestrator
 ├─ S3: raw/, transformed/, evidence/ (versioned buckets)
 ├─ RDS Postgres: jobs, issues, candidates, audit_log
 ├─ Bedrock: LLM provider
 ├─ Simple API Gateway in front of FastAPI
 └─ Sandbox: separate Fargate task w/ no outbound network, minimal IAM role
```

### Stage 3 — Production-like MVP
```
AWS
 ├─ Cognito (auth) → API Gateway → ECS Fargate services
 ├─ Step Functions or Temporal Cloud (workflow orchestration: retry, approval SLA)
 ├─ RDS Postgres (Multi-AZ) w/ RLS for namespace isolation
 ├─ S3 + Object Lock (raw dataset immutability) + KMS encryption
 ├─ Secrets Manager (LLM API keys, DB creds)
 ├─ CloudWatch (logs, metrics, cost dashboards) + OpenTelemetry traces
 ├─ VPC private subnets for sandbox + DB; NAT only where required
 └─ IAM least-privilege roles per service (profiler role has no S3 write to raw/, only read)
```

---

## 13. Mapping to the Development Timeline (Section 34)

| Track (PRD) | Concrete build artifacts |
| :--- | :--- |
| Data track (wks 1–4) | Polars profiler module, issue-detector rule set, transformation registry (unit-testable, no LLM) |
| Execution track (wks 3–6) | `TransformationIR` Pydantic models + JSON Schema, Compiler registry, sandbox harness |
| AI track (wks 5–8) | Evidence Compiler, `LLMProvider` interface, Bedrock adapter, prompt templates, response validator |
| Control track (wks 7–10) | Policy Engine (YAML-driven), Selection Engine scoring |
| Control track (wks 10–12) | Retry/replanning workflow, failure-memory model |
| Eval track (wks 12–16) | Systems A/B/C/D harness, benchmark dataset loader, metrics computation (UMR, F1, Wasserstein) |
| Platform track (wks 14–18) | Cognito/RBAC, RLS policies, Approval workflow, Terraform for Stage 3 infra |
| Frontend track (wks 7–19) | Dataset overview, issue list, candidate comparison (near-tie UI), validation breakdown, confidence badges |

---

## 14. Key Implementation Risks Not to Under-Build

1. **IR schema versioning migration path** — build the migration/compat layer *before* you need it (i.e., in the Execution track), since Section 26 requires graceful handling of incompatible IR versions, not a crash.
2. **Sandbox isolation** — resist the temptation to run "compiled" Polars expressions in-process for Stage 1 convenience; even allowlisted operations should run in a resource-bounded subprocess from day one so the isolation boundary is tested early, not retrofitted before Stage 3 security review.
3. **Selection/Policy Engine purity** — no network calls, no DB writes inside these functions. Keeping them pure is what makes the Section 28 evaluation harness (systems A/B/C/D sharing "the same policy, selection, compiler, sandbox, validator") actually feasible — any hidden state breaks reproducible comparison.
4. **Terminal-state reconciliation job** — build the "any job outside {ACCEPTED, REJECTED, UNRESOLVED, FAILED} after max duration is a defect" watcher early; it's cheap to build and is your main signal for the Section 6.7 reliability metric.
