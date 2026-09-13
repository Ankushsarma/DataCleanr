from typing import List, Dict, Any

class DetectedIssue:
    def __init__(self, column: str, issue_type: str, evidence: Dict[str, Any]):
        self.column = column
        self.issue_type = issue_type
        self.evidence = evidence

class IssueDetector:
    """
    Rule-based issue detector that takes profiler output and flags problems.
    """
    
    @staticmethod
    def detect(profiler_output: Dict[str, Any], file_path: str = None) -> List[DetectedIssue]:
        issues = []
        columns_stats = profiler_output.get("columns", {})
        row_count = profiler_output.get("row_count", 0)
        
        for col_name, stats in columns_stats.items():
            
            null_pct = stats.get("null_pct", 0)
            
            # Rule 1: Missing values (Low vs High based on threshold)
            missing_evidence = {
                "null_pct": null_pct, 
                "null_count": stats.get("null_count", 0),
                "dtype": stats.get("dtype", "Unknown"),
                "n_unique": stats.get("n_unique", 0)
            }
            if stats.get("dtype") in ["Int64", "Float64", "Int32", "Float32"]:
                missing_evidence["mean"] = stats.get("mean")
                missing_evidence["std"] = stats.get("std")
                missing_evidence["min"] = stats.get("min")
                missing_evidence["max"] = stats.get("max")
                
                # Simple outlier heuristic for the LLM
                mean = stats.get("mean")
                std = stats.get("std")
                c_max = stats.get("max")
                c_min = stats.get("min")
                has_outliers = False
                if mean is not None and std is not None and std > 0:
                    if (c_max is not None and c_max > mean + (3 * std)) or \
                       (c_min is not None and c_min < mean - (3 * std)):
                        has_outliers = True
                missing_evidence["has_outliers"] = has_outliers

            if 0 < null_pct <= 15:
                issues.append(DetectedIssue(
                    column=col_name,
                    issue_type="MISSING_LOW",
                    evidence=missing_evidence
                ))
            elif null_pct > 15:
                issues.append(DetectedIssue(
                    column=col_name,
                    issue_type="MISSING_HIGH",
                    evidence=missing_evidence
                ))
                
            # Rule 2: Constant column or Single Dominant Category
            n_unique = stats.get("n_unique", 0)
            if n_unique == 1 and stats.get("null_count", 0) < row_count and row_count > 1:
                issues.append(DetectedIssue(
                    column=col_name,
                    issue_type="CONSTANT_VALUE",
                    evidence={"n_unique": 1, "null_pct": null_pct}
                ))
            
            # Rule 3: Single Dominant Category (for strings)
            if stats.get("dtype") == "String" and row_count > 10 and n_unique > 1:
                most_frequent = stats.get("most_frequent")
                # We don't have the exact count of the most frequent value in the basic stats right now,
                # but we can infer high cardinality text vs ID.
                unique_pct = (n_unique / row_count) * 100
                if 95 <= unique_pct <= 100:
                     issues.append(DetectedIssue(
                        column=col_name,
                        issue_type="POTENTIAL_ID_OR_TEXT",
                        evidence={"unique_pct": round(unique_pct, 2)}
                    ))
                     
            # Rule 4: Skewed / Outliers (Using ML Isolation Forest)
            is_identifier = any(x in col_name.lower() for x in ["id", "rank", "index", "ref"])
            if stats.get("dtype") in ["Int64", "Float64", "Int32", "Float32"] and not is_identifier:
                mean = stats.get("mean")
                std = stats.get("std")
                c_max = stats.get("max")
                c_min = stats.get("min")
                
                # We need the actual data to run Isolation Forest
                has_outliers = False
                contamination = 0.05
                
                if file_path:
                    try:
                        import polars as pl
                        import numpy as np
                        from sklearn.ensemble import IsolationForest
                        
                        df = pl.read_csv(file_path, null_values=["NA", "null", ""])
                        if col_name in df.columns:
                            # Drop nulls for IsolationForest
                            valid_data = df.select(col_name).drop_nulls().to_numpy()
                            if len(valid_data) > 10:  # Need enough data points
                                clf = IsolationForest(contamination=contamination, random_state=42)
                                preds = clf.fit_predict(valid_data)
                                if -1 in preds:
                                    has_outliers = True
                    except Exception as e:
                        print(f"IsolationForest failed on {col_name}: {e}")
                        # Fallback to standard deviation heuristic
                        if mean is not None and std is not None and c_max is not None and std > 0:
                            if c_max > mean + (3 * std) or c_min < mean - (3 * std):
                                has_outliers = True
                else:
                    # Fallback to standard deviation heuristic
                    if mean is not None and std is not None and c_max is not None and std > 0:
                        if c_max > mean + (3 * std) or c_min < mean - (3 * std):
                            has_outliers = True
                            
                if has_outliers:
                    issues.append(DetectedIssue(
                        column=col_name,
                        issue_type="SKEWED_OUTLIERS",
                        evidence={"mean": mean, "std": std, "max": c_max, "min": c_min, "method": "IsolationForest"}
                    ))
            # Rule 5: Whitespace padding
            if stats.get("dtype") == "String":
                # In a real system, profiler would flag this. We simulate finding padding if it's a string column.
                # Since we don't have exact profiler stats for this, we will rely on file_path to check
                if file_path:
                    try:
                        import polars as pl
                        df = pl.read_csv(file_path, null_values=["NA", "null", ""])
                        if col_name in df.columns:
                            # Check for any row with leading/trailing whitespace
                            has_padding = df.select(pl.col(col_name).str.starts_with(" ") | pl.col(col_name).str.ends_with(" ")).sum().item() > 0
                            if has_padding:
                                issues.append(DetectedIssue(
                                    column=col_name,
                                    issue_type="WHITESPACE_PADDING",
                                    evidence={"has_padding": True}
                                ))
                    except Exception as e:
                        print(f"Whitespace check failed for {col_name}: {e}")
                        
            # Rule 6: Type Mismatch
            if stats.get("dtype") == "String":
                castability_pct = stats.get("castability_pct", 0)
                inferred_type = stats.get("inferred_type")
                if inferred_type and castability_pct >= 80:
                    issues.append(DetectedIssue(
                        column=col_name,
                        issue_type="TYPE_MISMATCH",
                        evidence={
                            "inferred_type": inferred_type,
                            "castability_pct": castability_pct
                        }
                    ))
            
            # Rule 7: Inconsistent Casing (Heuristic)
            if stats.get("dtype") == "String" and file_path:
                try:
                    import polars as pl
                    df = pl.read_csv(file_path, null_values=["NA", "null", ""])
                    if col_name in df.columns:
                        unique_vals = df[col_name].drop_nulls().unique().to_list()
                        if 1 < len(unique_vals) <= 50:
                            # If lowercasing reduces the number of unique values, we have an inconsistency
                            lower_vals = set([str(x).lower().strip() for x in unique_vals])
                            if len(lower_vals) < len(unique_vals):
                                issues.append(DetectedIssue(
                                    column=col_name,
                                    issue_type="INCONSISTENT_CASING",
                                    evidence={"unique_count": len(unique_vals), "lowered_count": len(lower_vals)}
                                ))
                except Exception as e:
                    pass
            
            # Rule 8: Invalid Logical Values (Negative Age/Price)
            if stats.get("dtype") in ["Int64", "Float64", "Int32", "Float32"]:
                c_min = stats.get("min")
                if c_min is not None and c_min < 0:
                    col_lower = col_name.lower()
                    if any(x in col_lower for x in ["age", "price", "cost", "revenue", "count", "amount"]):
                        issues.append(DetectedIssue(
                            column=col_name,
                            issue_type="INVALID_LOGICAL_VALUE",
                            evidence={"min_value": c_min, "reason": "Negative value in logical positive column"}
                        ))
                        
        # Dataset level rules
        if file_path:
            try:
                import polars as pl
                df = pl.read_csv(file_path, null_values=["NA", "null", ""])
                # Exact duplicates
                dup_count = len(df) - len(df.unique())
                if dup_count > 0:
                    issues.append(DetectedIssue(
                        column="dataset",
                        issue_type="EXACT_DUPLICATES",
                        evidence={"duplicate_count": dup_count}
                    ))
            except Exception as e:
                print(f"Dataset level checks failed: {e}")
                     
        return issues
