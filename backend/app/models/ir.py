from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ValidationError

class AllowedOperation(str, Enum):
    KEEP = "KEEP"
    FLAG = "FLAG"
    IMPUTE_MEAN = "IMPUTE_MEAN"
    IMPUTE_MEDIAN = "IMPUTE_MEDIAN"
    IMPUTE_MODE = "IMPUTE_MODE"
    IMPUTE_CONSTANT = "IMPUTE_CONSTANT"
    IMPUTE_KNN = "IMPUTE_KNN"
    IMPUTE_GROUPWISE_MEAN = "IMPUTE_GROUPWISE_MEAN"
    IMPUTE_GROUPWISE_MEDIAN = "IMPUTE_GROUPWISE_MEDIAN"
    DROP_ROWS_EXACT_DUPLICATE = "DROP_ROWS_EXACT_DUPLICATE"
    DROP_ROWS_PREDICATE = "DROP_ROWS_PREDICATE"
    NORMALIZE_CATEGORICAL = "NORMALIZE_CATEGORICAL"
    TRIM_WHITESPACE = "TRIM_WHITESPACE"
    CAST_TYPE = "CAST_TYPE"
    CLIP_OUTLIERS = "CLIP_OUTLIERS"
    WINSORIZE = "WINSORIZE"
    STANDARDIZE_DATE_FORMAT = "STANDARDIZE_DATE_FORMAT"
    REGEX_REPLACE = "REGEX_REPLACE"
    ONE_HOT_ENCODE = "ONE_HOT_ENCODE"
    LABEL_ENCODE = "LABEL_ENCODE"
    ORDINAL_ENCODE = "ORDINAL_ENCODE"
    TARGET_ENCODE = "TARGET_ENCODE"

class Scope(BaseModel):
    predicate: Optional[str] = None
    estimated_affected_rows: Optional[int] = None

class Constraints(BaseModel):
    preserve_row_count: bool = True
    preserve_columns: List[str] = Field(default_factory=list)
    max_modification_pct: Optional[float] = None

class TransformationIR(BaseModel):
    ir_version: str = "1.0"
    issue_id: str
    operation: AllowedOperation
    target_column: str
    group_by: Optional[List[str]] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    scope: Scope = Field(default_factory=Scope)
    constraints: Constraints = Field(default_factory=Constraints)
    risk_level: str = Field(pattern="^(LOW|MEDIUM|HIGH)$")
    agent_confidence: str = Field(pattern="^(LOW|MEDIUM|HIGH)$")
    rationale: str

class RejectedResponse(BaseModel):
    reason: str
    detail: Any

class IRCandidate(BaseModel):
    ir: TransformationIR
    # policy_result: Optional[Any] = None # Will be populated by policy engine later

def validate_agent_response(raw_json_dict: dict) -> IRCandidate | RejectedResponse:
    """
    Validates a parsed JSON dictionary against the TransformationIR schema.
    Returns an IRCandidate if valid, or RejectedResponse if invalid.
    """
    try:
        ir = TransformationIR.model_validate(raw_json_dict)
        # Policy Engine check would go here later (Section 4.3)
        return IRCandidate(ir=ir)
    except ValidationError as e:
        return RejectedResponse(reason="IR_INVALID", detail=str(e))
    except ValueError as e:
        # Pydantic Enum validation errors might raise ValueErrors
        return RejectedResponse(reason="OPERATION_NOT_ALLOWED", detail=str(e))
