import polars as pl
import json
from typing import Dict, Any

class PolarsProfiler:
    """
    Deterministic EDA Profiler using Polars.
    """
    
    @staticmethod
    def profile(file_path: str) -> Dict[str, Any]:
        """
        Reads a CSV and computes column-level statistics.
        Uses Polars lazy execution where possible for performance.
        """
        # Read the file eagerly to get schema and row count (MVP simplification)
        # For very large files, we'd use scan_csv and compute aggregates lazily.
        df = pl.read_csv(file_path, ignore_errors=True)
        
        row_count = df.height
        column_count = df.width
        
        column_stats = {}
        
        for col_name in df.columns:
            series = df[col_name]
            dtype = str(series.dtype)
            
            null_count = series.null_count()
            null_pct = (null_count / row_count) * 100 if row_count > 0 else 0
            
            n_unique = series.n_unique()
            
            stats = {
                "dtype": dtype,
                "null_count": null_count,
                "null_pct": round(null_pct, 2),
                "n_unique": n_unique
            }
            
            # Numeric stats
            if series.dtype in [pl.Int64, pl.Int32, pl.Float64, pl.Float32]:
                try:
                    stats["mean"] = series.mean()
                    stats["std"] = series.std()
                    stats["min"] = series.min()
                    stats["max"] = series.max()
                except Exception:
                    pass # Ignore if calculation fails for some edge cases
            
            # String / Categorical stats
            if series.dtype == pl.String:
                try:
                    # Get top most frequent value
                    value_counts = series.value_counts(sort=True)
                    if not value_counts.is_empty():
                        # the first row has the most frequent value
                        most_frequent = value_counts[col_name][0]
                        stats["most_frequent"] = most_frequent
                        
                    # Check for type castability (e.g. to Float64)
                    valid_original_count = row_count - null_count
                    if valid_original_count > 0:
                        # Try casting to Float64 to see how many succeed
                        # Strip currency symbols and commas first to handle monetary values
                        cleaned_series = series.str.replace_all(r"[\$,£€]", "").str.replace_all(",", "")
                        cast_series = cleaned_series.cast(pl.Float64, strict=False)
                        valid_cast_count = row_count - cast_series.null_count()
                        castability_pct = (valid_cast_count / valid_original_count) * 100
                        
                        if castability_pct > 0:
                            stats["castability_pct"] = round(castability_pct, 2)
                            stats["inferred_type"] = "Float64"
                except Exception as e:
                    pass

            column_stats[col_name] = stats
            
        return {
            "row_count": row_count,
            "column_count": column_count,
            "columns": column_stats
        }
