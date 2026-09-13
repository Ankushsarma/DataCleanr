import polars as pl
from typing import Callable, Dict, Any
from app.models.ir import TransformationIR

def compile_keep(ir: TransformationIR, lf: pl.LazyFrame) -> pl.LazyFrame:
    # No-op
    return lf

def compile_flag(ir: TransformationIR, lf: pl.LazyFrame) -> pl.LazyFrame:
    # MVP: FLAG marks the issue for review in the DB/Audit logs. 
    # Per user request, we will no longer append an extra `_flagged` column to the actual output dataset.
    return lf

def compile_impute_median(ir: TransformationIR, lf: pl.LazyFrame) -> pl.LazyFrame:
    return lf.with_columns(
        pl.col(ir.target_column).fill_null(pl.col(ir.target_column).median())
    )

def compile_impute_mean(ir: TransformationIR, lf: pl.LazyFrame) -> pl.LazyFrame:
    return lf.with_columns(
        pl.col(ir.target_column).fill_null(pl.col(ir.target_column).mean())
    )

def compile_impute_mode(ir: TransformationIR, lf: pl.LazyFrame) -> pl.LazyFrame:
    # mode() on a column with majority nulls will return null itself,
    # making fill_null a no-op. So we must compute mode on non-null values only.
    df = lf.collect()
    col = ir.target_column
    non_null = df[col].drop_nulls()
    if len(non_null) == 0:
        print(f"[Compiler] Warning: Column '{col}' is entirely null. Cannot compute mode, skipping.")
        return df.lazy()
    mode_val = non_null.mode()[0]
    print(f"[Compiler] Compiling IMPUTE_MODE on column '{col}' with mode value '{mode_val}'.")
    return df.with_columns(pl.col(col).fill_null(pl.lit(mode_val))).lazy()

def compile_impute_constant(ir: TransformationIR, lf: pl.LazyFrame) -> pl.LazyFrame:
    value = ir.parameters.get("value", "UNKNOWN")
    print(f"[Compiler] Compiling IMPUTE_CONSTANT for column '{ir.target_column}' with value '{value}'.")
    return lf.with_columns(
        pl.col(ir.target_column).fill_null(pl.lit(value))
    )

def compile_impute_knn(ir: TransformationIR, lf: pl.LazyFrame) -> pl.LazyFrame:
    # Evaluate LazyFrame to get data
    df = lf.collect()
    
    # Identify target and numeric columns
    target_col = ir.target_column
    if df[target_col].dtype not in [pl.Int64, pl.Float64, pl.Int32, pl.Float32]:
        print(f"Warning: KNN Imputation requires numeric target, got {df[target_col].dtype}. Falling back to Constant.")
        return compile_impute_constant(ir, lf).collect().lazy()
    
    numeric_cols = [c for c in df.columns if df[c].dtype in [pl.Int64, pl.Float64, pl.Int32, pl.Float32]]
    
    if len(numeric_cols) < 2:
        print("Warning: KNN Imputation needs at least 1 other numeric feature. Falling back to Median.")
        return compile_impute_median(ir, lf).collect().lazy()
        
    try:
        from sklearn.impute import KNNImputer
        n_neighbors = ir.parameters.get("n_neighbors", 5)
        # Handle cases where we have fewer rows than neighbors
        n_neighbors = min(n_neighbors, max(1, len(df) - 1))
        
        print(f"[Compiler] Running KNNImputer on column '{target_col}' with {n_neighbors} neighbors...")
        imputer = KNNImputer(n_neighbors=n_neighbors, weights="uniform")
        num_data = df.select(numeric_cols).to_numpy()
        imputed_data = imputer.fit_transform(num_data)
        
        # Reassign the target column
        target_idx = numeric_cols.index(target_col)
        imputed_col_data = imputed_data[:, target_idx]
        
        df = df.with_columns(pl.Series(name=target_col, values=imputed_col_data))
        print(f"[Compiler] Successfully imputed {target_col} using KNN.")
    except Exception as e:
        print(f"KNN Imputer failed: {e}. Falling back to Median.")
        return compile_impute_median(ir, lf).collect().lazy()
        
    return df.lazy()

def compile_winsorize(ir: TransformationIR, lf: pl.LazyFrame) -> pl.LazyFrame:
    # Simplistic winsorize: cap at 5th and 95th percentiles
    col = ir.target_column
    return lf.with_columns(
        pl.col(col).clip(
            lower_bound=pl.col(col).quantile(0.05),
            upper_bound=pl.col(col).quantile(0.95)
        )
    )

def compile_clip_outliers(ir: TransformationIR, lf: pl.LazyFrame) -> pl.LazyFrame:
    # For MVP, acts identical to winsorize unless parameters specify strict bounds
    return compile_winsorize(ir, lf)

def compile_drop_rows_predicate(ir: TransformationIR, lf: pl.LazyFrame) -> pl.LazyFrame:
    # The agent passes a SQL-like predicate in scope.predicate (e.g. "target IS NULL")
    # For MVP and safety, we only support specific simple dropping logic rather than `sql` parsing
    # If the predicate is "target IS NULL", we use drop_nulls
    if ir.scope.predicate:
        if "IS NULL" in ir.scope.predicate:
            print(f"[Compiler] Compiling DROP_ROWS_PREDICATE (IS NULL) on column '{ir.target_column}'.")
            return lf.drop_nulls(subset=[ir.target_column])
        elif "OUTLIER" in ir.scope.predicate:
            col = ir.target_column
            print(f"[Compiler] Compiling DROP_ROWS_PREDICATE (OUTLIER) on column '{col}'.")
            return lf.filter(
                pl.col(col).is_between(pl.col(col).quantile(0.05), pl.col(col).quantile(0.95))
            )
    return lf

def compile_regex_replace(ir: TransformationIR, lf: pl.LazyFrame) -> pl.LazyFrame:
    pattern = ir.parameters.get("pattern", "")
    replacement = ir.parameters.get("replacement", "")
    print(f"[Compiler] Compiling REGEX_REPLACE on column '{ir.target_column}' with pattern '{pattern}'.")
    
    # We must cast to String to perform string replace, then replace
    # Polars string operations return null if the value doesn't match if we use str.extract, 
    # but str.replace_all works directly on string columns.
    return lf.with_columns(
        pl.col(ir.target_column).cast(pl.Utf8).str.replace_all(pattern, replacement)
    )

def compile_cast_type(ir: TransformationIR, lf: pl.LazyFrame) -> pl.LazyFrame:
    target_type = ir.parameters.get("target_type", "String")
    print(f"[Compiler] Compiling CAST_TYPE on column '{ir.target_column}' to {target_type}.")
    
    type_map = {
        "String": pl.Utf8,
        "Int64": pl.Int64,
        "Float64": pl.Float64,
        "Boolean": pl.Boolean
    }
    
    pl_type = type_map.get(target_type, pl.Utf8)
    
    if target_type in ["Int64", "Float64"]:
        # If casting to numeric, strip currency symbols and commas first
        return lf.with_columns(
            pl.col(ir.target_column).cast(pl.Utf8).str.replace_all(r"[\$,£€]", "").str.replace_all(",", "").cast(pl_type, strict=False)
        )
    else:
        return lf.with_columns(
            pl.col(ir.target_column).cast(pl_type, strict=False)
        )

def compile_trim_whitespace(ir: TransformationIR, lf: pl.LazyFrame) -> pl.LazyFrame:
    print(f"[Compiler] Compiling TRIM_WHITESPACE on column '{ir.target_column}'.")
    return lf.with_columns(
        pl.col(ir.target_column).cast(pl.Utf8).str.strip_chars()
    )

def compile_normalize_categorical(ir: TransformationIR, lf: pl.LazyFrame) -> pl.LazyFrame:
    print(f"[Compiler] Compiling NORMALIZE_CATEGORICAL on column '{ir.target_column}'.")
    # Basic normalization: lowercased, stripped, no extra internal spaces
    return lf.with_columns(
        pl.col(ir.target_column).cast(pl.Utf8).str.to_lowercase().str.strip_chars()
    )

def compile_text_standardize(ir: TransformationIR, lf: pl.LazyFrame) -> pl.LazyFrame:
    print(f"[Compiler] Compiling TEXT_STANDARDIZE on column '{ir.target_column}'.")
    # Titlecase and trim to resolve M, m, male, Male -> Male
    return lf.with_columns(
        pl.col(ir.target_column).cast(pl.Utf8).str.to_titlecase().str.strip_chars()
    )

def compile_nullify_negative(ir: TransformationIR, lf: pl.LazyFrame) -> pl.LazyFrame:
    print(f"[Compiler] Compiling NULLIFY_NEGATIVE on column '{ir.target_column}'.")
    return lf.with_columns(
        pl.when(pl.col(ir.target_column) < 0)
        .then(None)
        .otherwise(pl.col(ir.target_column))
        .alias(ir.target_column)
    )

def compile_standardize_date_format(ir: TransformationIR, lf: pl.LazyFrame) -> pl.LazyFrame:
    format = ir.parameters.get("format", "%Y-%m-%d")
    print(f"[Compiler] Compiling STANDARDIZE_DATE_FORMAT on column '{ir.target_column}' to {format}.")
    return lf.with_columns(
        pl.col(ir.target_column).str.strptime(pl.Date, format, strict=False).cast(pl.Utf8)
    )

def compile_drop_rows_exact_duplicate(ir: TransformationIR, lf: pl.LazyFrame) -> pl.LazyFrame:
    print(f"[Compiler] Compiling DROP_ROWS_EXACT_DUPLICATE.")
    # Target column is ignored, runs on entire dataframe
    return lf.unique(maintain_order=True)

def compile_one_hot_encode(ir: TransformationIR, lf: pl.LazyFrame) -> pl.LazyFrame:
    print(f"[Compiler] Compiling ONE_HOT_ENCODE on column '{ir.target_column}'.")
    # to_dummies is an eager operation, so we collect and return a new LazyFrame
    return lf.collect().to_dummies(ir.target_column).lazy()

def compile_label_encode(ir: TransformationIR, lf: pl.LazyFrame) -> pl.LazyFrame:
    print(f"[Compiler] Compiling LABEL_ENCODE on column '{ir.target_column}'.")
    return lf.with_columns(
        pl.col(ir.target_column).cast(pl.Categorical).to_physical().cast(pl.Int64)
    )

def compile_ordinal_encode(ir: TransformationIR, lf: pl.LazyFrame) -> pl.LazyFrame:
    print(f"[Compiler] Compiling ORDINAL_ENCODE on column '{ir.target_column}'.")
    order = ir.parameters.get("order", [])
    if not order:
        # Fallback to label encoding if no order is provided
        return compile_label_encode(ir, lf)
    
    mapping = {val: i for i, val in enumerate(order)}
    return lf.with_columns(
        pl.col(ir.target_column).replace(mapping, default=None).cast(pl.Int64)
    )

def compile_target_encode(ir: TransformationIR, lf: pl.LazyFrame) -> pl.LazyFrame:
    print(f"[Compiler] Compiling TARGET_ENCODE on column '{ir.target_column}'.")
    target_var = ir.parameters.get("target_variable")
    if not target_var:
        print("[Compiler] Warning: target_variable missing, falling back to KEEP.")
        return lf
    
    # Calculate means
    mean_lf = lf.group_by(ir.target_column).agg(
        pl.col(target_var).mean().alias(f"{ir.target_column}_target_mean")
    )
    
    # Join and replace
    return lf.join(mean_lf, on=ir.target_column, how="left").with_columns(
        pl.col(f"{ir.target_column}_target_mean").alias(ir.target_column)
    ).drop(f"{ir.target_column}_target_mean")

# Registry mapping allowed operations to pure LazyFrame builders
COMPILER_REGISTRY: Dict[str, Callable[[TransformationIR, pl.LazyFrame], pl.LazyFrame]] = {
    "KEEP": compile_keep,
    "FLAG": compile_flag,
    "IMPUTE_MEDIAN": compile_impute_median,
    "IMPUTE_MEAN": compile_impute_mean,
    "IMPUTE_MODE": compile_impute_mode,
    "IMPUTE_CONSTANT": compile_impute_constant,
    "IMPUTE_KNN": compile_impute_knn,
    "WINSORIZE": compile_winsorize,
    "CLIP_OUTLIERS": compile_clip_outliers,
    "DROP_ROWS_PREDICATE": compile_drop_rows_predicate,
    "REGEX_REPLACE": compile_regex_replace,
    "CAST_TYPE": compile_cast_type,
    "TRIM_WHITESPACE": compile_trim_whitespace,
    "NORMALIZE_CATEGORICAL": compile_normalize_categorical,
    "STANDARDIZE_DATE_FORMAT": compile_standardize_date_format,
    "DROP_ROWS_EXACT_DUPLICATE": compile_drop_rows_exact_duplicate,
    "ONE_HOT_ENCODE": compile_one_hot_encode,
    "LABEL_ENCODE": compile_label_encode,
    "ORDINAL_ENCODE": compile_ordinal_encode,
    "TARGET_ENCODE": compile_target_encode,
    "TEXT_STANDARDIZE": compile_text_standardize,
    "NULLIFY_NEGATIVE": compile_nullify_negative,
    # Additional operations would be mapped here
}

class IRCompiler:
    """
    Translates validated IR models into deterministic Polars query plans.
    """
    @staticmethod
    def compile(ir: TransformationIR, lf: pl.LazyFrame) -> pl.LazyFrame:
        builder = COMPILER_REGISTRY.get(ir.operation.value)
        if not builder:
            print(f"Warning: Operation {ir.operation.value} is not implemented in Compiler. Keeping original.")
            return lf
        
        return builder(ir, lf)
