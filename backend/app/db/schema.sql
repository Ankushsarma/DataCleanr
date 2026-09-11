-- Original PostgreSQL Schema Reference (from Tech Spec)

CREATE TABLE datasets (
    dataset_id UUID PRIMARY KEY,
    namespace_id UUID NOT NULL,
    raw_s3_uri TEXT NOT NULL,
    raw_hash TEXT NOT NULL,
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
    state TEXT NOT NULL CHECK (state IN ('RUNNING','PENDING_APPROVAL','ACCEPTED','REJECTED','UNRESOLVED','FAILED')),
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

CREATE TABLE issues (
    issue_id UUID PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES jobs(job_id),
    column_name TEXT,
    issue_type TEXT NOT NULL,
    evidence_ref TEXT NOT NULL,
    decision TEXT CHECK (decision IN ('KEEP','FLAG','MODIFY')),
    final_state TEXT
);

CREATE TABLE candidates (
    candidate_id UUID PRIMARY KEY,
    issue_id UUID NOT NULL REFERENCES issues(issue_id),
    strategy TEXT NOT NULL,
    ir_json JSONB NOT NULL,
    agent_confidence TEXT CHECK (agent_confidence IN ('LOW','MEDIUM','HIGH')),
    agent_rationale TEXT,
    risk_level TEXT CHECK (risk_level IN ('LOW','MEDIUM','HIGH')),
    policy_eligible BOOLEAN,
    validation_result JSONB,
    selection_score NUMERIC,
    selected BOOLEAN DEFAULT FALSE
);
