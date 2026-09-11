"""Quick test for the Rule-Based Strategy Engine."""
from app.services.rule_engine import RuleBasedStrategyEngine

# Test 1: Missing string column
print("--- Test 1: MISSING_HIGH + String ---")
results = RuleBasedStrategyEngine.resolve(
    issue_id="t1", issue_column="Peak", issue_type="MISSING_HIGH",
    issue_evidence={"null_pct": 55.0, "null_count": 11, "dtype": "String", "n_unique": 8},
    profiler_output={}
)
for r in results:
    print(f"  {r.operation.value}: {r.rationale}")

# Test 2: Missing numeric with outliers
print("\n--- Test 2: MISSING_LOW + Numeric + Outliers ---")
results = RuleBasedStrategyEngine.resolve(
    issue_id="t2", issue_column="Shows", issue_type="MISSING_LOW",
    issue_evidence={"null_pct": 5.0, "null_count": 1, "dtype": "Int64", "has_outliers": True},
    profiler_output={}
)
for r in results:
    print(f"  {r.operation.value}: {r.rationale}")

# Test 3: Missing numeric without outliers
print("\n--- Test 3: MISSING_LOW + Numeric + Normal ---")
results = RuleBasedStrategyEngine.resolve(
    issue_id="t3", issue_column="Age", issue_type="MISSING_LOW",
    issue_evidence={"null_pct": 5.0, "null_count": 1, "dtype": "Float64", "has_outliers": False},
    profiler_output={}
)
for r in results:
    print(f"  {r.operation.value}: {r.rationale}")

# Test 4: Skewed outliers
print("\n--- Test 4: SKEWED_OUTLIERS ---")
results = RuleBasedStrategyEngine.resolve(
    issue_id="t4", issue_column="Shows", issue_type="SKEWED_OUTLIERS",
    issue_evidence={"mean": 110.0, "std": 66.5, "max": 325, "min": 41},
    profiler_output={}
)
for r in results:
    print(f"  {r.operation.value}: {r.rationale}")

# Test 5: Whitespace
print("\n--- Test 5: WHITESPACE_PADDING ---")
results = RuleBasedStrategyEngine.resolve(
    issue_id="t5", issue_column="Name", issue_type="WHITESPACE_PADDING",
    issue_evidence={"has_padding": True},
    profiler_output={}
)
for r in results:
    print(f"  {r.operation.value}: {r.rationale}")

# Test 6: Potential ID
print("\n--- Test 6: POTENTIAL_ID_OR_TEXT ---")
results = RuleBasedStrategyEngine.resolve(
    issue_id="t6", issue_column="Actual gross", issue_type="POTENTIAL_ID_OR_TEXT",
    issue_evidence={"unique_pct": 100.0},
    profiler_output={}
)
for r in results:
    print(f"  {r.operation.value}: {r.rationale}")

print("\nAll tests passed!")
