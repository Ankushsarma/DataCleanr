import polars as pl
from app.models.ir import TransformationIR, Scope, AllowedOperation, Constraints
from app.services.compiler import IRCompiler
import json

# Create a sample DataFrame
df = pl.DataFrame({
    "id": [1, 2, 3, 4, 5],
    "age": [25, None, 30, 25, 40],
    "name": ["Alice ", " Bob", "CHARLIE", "  Dave  ", "Eve"],
    "category": ["A", "B", None, "A", "A"]
}).lazy()

print("Original DataFrame:")
print(df.collect().to_dicts())

# Test 1: IMPUTE_MEAN on 'age'
ir_mean = TransformationIR(
    issue_id="1",
    target_column="age",
    operation=AllowedOperation.IMPUTE_MEAN,
    scope=Scope(predicate=None),
    rationale="Test impute mean",
    risk_level="LOW",
    agent_confidence="HIGH",
    constraints=Constraints(preserve_row_count=True, preserve_columns=[])
)
df_mean = IRCompiler.compile(ir_mean, df)
print("\nAfter IMPUTE_MEAN on 'age':")
print(df_mean.collect().to_dicts())

# Test 2: TRIM_WHITESPACE on 'name'
ir_trim = TransformationIR(
    issue_id="2",
    target_column="name",
    operation=AllowedOperation.TRIM_WHITESPACE,
    scope=Scope(predicate=None),
    rationale="Test trim whitespace",
    risk_level="LOW",
    agent_confidence="HIGH",
    constraints=Constraints(preserve_row_count=True, preserve_columns=[])
)
df_trim = IRCompiler.compile(ir_trim, df)
print("\nAfter TRIM_WHITESPACE on 'name':")
print(df_trim.collect().to_dicts())

# Test 3: NORMALIZE_CATEGORICAL on 'name'
ir_norm = TransformationIR(
    issue_id="3",
    target_column="name",
    operation=AllowedOperation.NORMALIZE_CATEGORICAL,
    scope=Scope(predicate=None),
    rationale="Test normalize categorical",
    risk_level="LOW",
    agent_confidence="HIGH",
    constraints=Constraints(preserve_row_count=True, preserve_columns=[])
)
df_norm = IRCompiler.compile(ir_norm, df)
print("\nAfter NORMALIZE_CATEGORICAL on 'name':")
print(df_norm.collect().to_dicts())

# Test 4: DROP_ROWS_PREDICATE on 'age' IS NULL
ir_drop = TransformationIR(
    issue_id="4",
    target_column="age",
    operation=AllowedOperation.DROP_ROWS_PREDICATE,
    scope=Scope(predicate="age IS NULL"),
    rationale="Test drop nulls",
    risk_level="LOW",
    agent_confidence="HIGH",
    constraints=Constraints(preserve_row_count=False, preserve_columns=[])
)
df_drop = IRCompiler.compile(ir_drop, df)
print("\nAfter DROP_ROWS_PREDICATE (age IS NULL):")
print(df_drop.collect().to_dicts())

# Test 5: IMPUTE_MODE on 'category'
ir_mode = TransformationIR(
    issue_id="5",
    target_column="category",
    operation=AllowedOperation.IMPUTE_MODE,
    scope=Scope(predicate=None),
    rationale="Test impute mode",
    risk_level="LOW",
    agent_confidence="HIGH",
    constraints=Constraints(preserve_row_count=True, preserve_columns=[])
)
df_mode = IRCompiler.compile(ir_mode, df)
print("\nAfter IMPUTE_MODE on 'category':")
print(df_mode.collect().to_dicts())
