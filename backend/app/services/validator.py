import polars as pl
import os
from typing import List, Dict, Any
from app.models.ir import TransformationIR

class ValidationResult:
    def __init__(self, passed: bool, violations: List[str] = None):
        self.passed = passed
        self.violations = violations or []

class ValidationEngine:
    """
    Independently verifies that the Sandbox execution did not violate 
    preservation constraints (e.g., dropping too many rows, corrupting schemas).
    This acts as the final safety checkpoint before the dataset is marked COMPLETED.
    """
    
    @staticmethod
    def validate(input_path: str, output_path: str, ir_list: List[TransformationIR]) -> ValidationResult:
        violations = []
        
        try:
            print(f"[ValidationEngine] Starting validation on {output_path} against original {input_path}...")
            # Load basic shapes
            input_lf = pl.scan_csv(input_path)
            output_lf = pl.scan_csv(output_path)
            
            # Using eager evaluation for row counts (small overhead for MVP)
            input_df = input_lf.collect()
            output_df = output_lf.collect()
            
            original_row_count = len(input_df)
            new_row_count = len(output_df)
            print(f"[ValidationEngine] Original rows: {original_row_count}, New rows: {new_row_count}")
            
            # 1. Row Retention Check
            # Aggregate the most restrictive row retention constraint from all IRs
            min_retention_pct = 100.0 # Default: keep all rows
            for ir in ir_list:
                if not ir.constraints.preserve_row_count:
                    # If dropping rows is allowed, the max modification pct dictates the bound
                    allowable_retention = 100.0 - ir.constraints.max_modification_pct
                    if allowable_retention < min_retention_pct:
                        min_retention_pct = allowable_retention
                        
            actual_retention_pct = (new_row_count / original_row_count) * 100 if original_row_count > 0 else 100.0
            
            if actual_retention_pct < min_retention_pct:
                print(f"[ValidationEngine] Row retention FAILED. Expected >= {min_retention_pct}%, got {actual_retention_pct}%")
                violations.append(f"Row retention failed. Expected >= {min_retention_pct}%, got {actual_retention_pct}%")
            else:
                print(f"[ValidationEngine] Row retention PASSED. Retained {actual_retention_pct}% (Min {min_retention_pct}% required)")
                
            # 2. Schema Preservation Check
            original_cols = set(input_df.columns)
            new_cols = set(output_df.columns)
            
            # Ensure no original columns were dropped (we only allow adding e.g. flags)
            dropped_cols = original_cols - new_cols
            if dropped_cols:
                violations.append(f"Schema corrupted. Dropped original columns: {dropped_cols}")
                
            # If there are violations, return False
            if violations:
                return ValidationResult(passed=False, violations=violations)
                
            return ValidationResult(passed=True)
            
        except Exception as e:
            return ValidationResult(passed=False, violations=[f"Validation execution failed: {str(e)}"])
