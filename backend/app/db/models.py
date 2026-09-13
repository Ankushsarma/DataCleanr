from sqlalchemy import Column, String, Integer, Float, Boolean, ForeignKey, DateTime, JSON, Text, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.db.session import Base

def generate_uuid():
    return str(uuid.uuid4())

class Dataset(Base):
    __tablename__ = "datasets"
    
    dataset_id = Column(String(36), primary_key=True, default=generate_uuid)
    namespace_id = Column(String(36), nullable=False)
    raw_s3_uri = Column(String, nullable=False)
    raw_hash = Column(String, nullable=False)
    schema_json = Column(JSON, nullable=False)
    row_count = Column(Integer)
    column_count = Column(Integer)
    created_by = Column(String(36), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Job(Base):
    __tablename__ = "jobs"
    
    job_id = Column(String(36), primary_key=True, default=generate_uuid)
    dataset_id = Column(String(36), ForeignKey("datasets.dataset_id"), nullable=False)
    mode = Column(String, nullable=False)
    state = Column(String, nullable=False)
    policy_version = Column(String, nullable=False)
    profiler_version = Column(String, nullable=False)
    agent_version = Column(String, nullable=False)
    ir_schema_version = Column(String, nullable=False)
    compiler_version = Column(String, nullable=False)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)
    cost_usd = Column(Numeric(10, 4))
    llm_calls = Column(Integer, default=0)
    tokens_used = Column(Integer, default=0)
    output_schema_json = Column(JSON, nullable=True)
    applied_operations = Column(JSON, default=list)

class JobLog(Base):
    __tablename__ = "job_logs"
    
    log_id = Column(String(36), primary_key=True, default=generate_uuid)
    job_id = Column(String(36), ForeignKey("jobs.job_id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    message = Column(Text, nullable=False)

class Issue(Base):
    __tablename__ = "issues"
    
    issue_id = Column(String(36), primary_key=True, default=generate_uuid)
    job_id = Column(String(36), ForeignKey("jobs.job_id"), nullable=False)
    column_name = Column(String)
    issue_type = Column(String, nullable=False)
    evidence_ref = Column(String, nullable=False)
    decision = Column(String)
    final_state = Column(String)

class CandidateModel(Base):
    __tablename__ = "candidates"
    
    candidate_id = Column(String(36), primary_key=True, default=generate_uuid)
    issue_id = Column(String(36), ForeignKey("issues.issue_id"), nullable=False)
    strategy = Column(String, nullable=False)
    ir_json = Column(JSON, nullable=False)
    agent_confidence = Column(String)
    agent_rationale = Column(Text)
    risk_level = Column(String)
    policy_eligible = Column(Boolean)
    validation_result = Column(JSON)
    selection_score = Column(Numeric)
    selected = Column(Boolean, default=False)
