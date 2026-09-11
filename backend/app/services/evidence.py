from typing import Dict, Any, Optional

class EvidenceCompiler:
    """
    Compiles deterministic profiling statistics and issue details into a 
    structured JSON package for the LLM to reason over.
    """
    
    @staticmethod
    def compile(
        issue_column: str,
        issue_type: str,
        issue_evidence: Dict[str, Any],
        profiler_output: Dict[str, Any],
        failure_memory: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Builds the evidence package per issue.
        """
        # Get column-specific stats from the profiler output
        col_stats = profiler_output.get("columns", {}).get(issue_column, {})
        
        evidence_package = {
            "column": issue_column,
            "dtype": col_stats.get("dtype", "Unknown"),
            "issue_type": issue_type,
            "stats": col_stats,
            "issue_evidence": issue_evidence,
            "dataset_rows": profiler_output.get("row_count"),
            "dataset_columns": profiler_output.get("column_count")
        }
        
        # If there are previous failed attempts, include them in the evidence
        if failure_memory and len(failure_memory) > 0:
            evidence_package["failure_memory"] = [
                {
                    "attempt": fm.get("attempt"),
                    "reason": fm.get("reason"),
                    "candidate_strategy": fm.get("candidate", {}).get("strategy") if fm.get("candidate") else None
                } for fm in failure_memory
            ]
            
        return evidence_package
