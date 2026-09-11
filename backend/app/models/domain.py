from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from uuid import UUID

class TransformationScope(BaseModel):
    predicate: str
    estimated_affected_rows: Optional[int] = None

class TransformationConstraints(BaseModel):
    preserve_row_count: bool = True
    preserve_columns: List[str] = Field(default_factory=list)
    max_modification_pct: Optional[float] = None

class TransformationIR(BaseModel):
    ir_version: str = "1.0"
    issue_id: UUID
    operation: str
    target_column: str
    group_by: Optional[List[str]] = Field(default_factory=list)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    scope: TransformationScope
    constraints: TransformationConstraints
    risk_level: str
    agent_confidence: str
    rationale: str

class ValidationSubResult(BaseModel):
    passed: bool
    score: float = 1.0
    details: str = ""

class ValidationResult(BaseModel):
    execution: ValidationSubResult
    constraints: ValidationSubResult
    preservation: ValidationSubResult
    policy: ValidationSubResult
    
    @property
    def accepted(self) -> bool:
        return all([self.execution.passed, self.constraints.passed, self.preservation.passed, self.policy.passed])

class Candidate(BaseModel):
    candidate_id: UUID
    issue_id: UUID
    strategy: str
    ir: TransformationIR
    agent_confidence: str
    risk_level: str
    policy_eligible: bool = False
    validation_result: Optional[ValidationResult] = None
    selection_score: float = 0.0
    selected: bool = False
