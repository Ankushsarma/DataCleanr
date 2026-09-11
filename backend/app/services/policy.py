import os
import yaml
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from app.models.ir import TransformationIR, IRCandidate

class PolicyResult(BaseModel):
    eligible: bool
    violations: List[str]

class PolicyEngine:
    """
    Deterministic engine that enforces data cleaning rules and safety limits.
    Loads configuration from policy_v1.yaml.
    """
    
    def __init__(self, config_path: str = "app/core/policy_v1.yaml"):
        self.config_path = config_path
        self._load_config()

    def _load_config(self):
        try:
            with open(self.config_path, "r") as f:
                self.config = yaml.safe_load(f)
        except Exception as e:
            print(f"Failed to load Policy config at {self.config_path}: {e}")
            self.config = {"operations": {}, "global_constraints": {}}

    def evaluate(self, ir: TransformationIR, dataset_metadata: Dict[str, Any]) -> PolicyResult:
        """
        Evaluates an IR candidate against the loaded policy rules.
        """
        violations = []
        op_rules = self.config.get("operations", {}).get(ir.operation.value, {})
        
        # 1. Operation Support Check
        if not op_rules:
            violations.append(f"Operation {ir.operation.value} is not permitted by policy.")
            return PolicyResult(eligible=False, violations=violations)

        # 2. Max Modification Percentage Check
        max_mod_pct = op_rules.get("max_modification_pct")
        if max_mod_pct is not None and ir.scope.estimated_affected_rows is not None:
            total_rows = dataset_metadata.get("row_count", 0)
            if total_rows > 0:
                proposed_mod_pct = (ir.scope.estimated_affected_rows / total_rows) * 100
                if proposed_mod_pct > max_mod_pct:
                    violations.append(f"Proposed modification ({proposed_mod_pct:.1f}%) exceeds maximum allowed ({max_mod_pct}%) for {ir.operation.value}.")
                    
        # 3. Minimum Group Size Check (e.g. for GROUPWISE imputation)
        req_min_group_size = op_rules.get("requires_min_group_size")
        if req_min_group_size is not None:
            proposed_min_group = ir.parameters.get("min_group_size", 0)
            if proposed_min_group < req_min_group_size:
                violations.append(f"Operation requires min_group_size >= {req_min_group_size}, but IR specified {proposed_min_group}.")
                
        # 4. Risk Level Sanity Check (Agent cannot bypass policy risk levels)
        policy_risk = op_rules.get("max_risk")
        risk_hierarchy = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
        if policy_risk and risk_hierarchy.get(ir.risk_level, 0) > risk_hierarchy.get(policy_risk, 3):
             # If agent proposed MEDIUM risk, but policy says max_risk is LOW
             violations.append(f"Proposed risk level {ir.risk_level} exceeds policy maximum {policy_risk} for {ir.operation.value}.")

        # 5. Row Retention Check
        min_retention = self.config.get("global_constraints", {}).get("row_retention", {}).get("min_retention_pct")
        if min_retention is not None and not ir.constraints.preserve_row_count:
            # If the operation drops rows, check if it violates global retention
            if max_mod_pct is not None and (100.0 - max_mod_pct) < min_retention:
                violations.append(f"Operation could result in {(100.0 - max_mod_pct):.1f}% row retention, violating global minimum of {min_retention}%.")
                
        is_eligible = len(violations) == 0
        return PolicyResult(eligible=is_eligible, violations=violations)

# Singleton instance
policy_engine = PolicyEngine()
