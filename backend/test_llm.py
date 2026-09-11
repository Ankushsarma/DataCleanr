import asyncio
import os
import json
from dotenv import load_dotenv

load_dotenv()
gemini_key = os.environ.get("GEMINI_API_KEY")

if not gemini_key:
    print("No GEMINI API KEY")
    exit(1)

from app.services.llm import GeminiLLMProvider
from app.services.agent import AgentOrchestrator

async def run_test():
    provider = GeminiLLMProvider(api_key=gemini_key)
    agent = AgentOrchestrator(primary_provider=provider)
    
    # Test Missing values (Peak - string)
    evidence_missing = {
        "null_pct": 55.0, 
        "null_count": 11, 
        "dtype": "String", 
        "n_unique": 8
    }
    print("Testing MISSING_HIGH...")
    candidates = await agent.propose(
        issue_id="test1", 
        issue_column="Peak", 
        issue_type="MISSING_HIGH", 
        issue_evidence=evidence_missing, 
        profiler_output={}
    )
    for c in candidates:
        print(f"Strategy: {c.ir.operation.value}")
        print(f"Rationale: {c.ir.rationale}")
        print(f"Parameters: {c.ir.parameters}")

    # Test Regex Replace (Actual gross - currency string)
    evidence_gross = {
        "unique_pct": 100.0,
        "dtype": "String"
    }
    print("\nTesting POTENTIAL_ID_OR_TEXT (Gross currency)...")
    candidates = await agent.propose(
        issue_id="test2", 
        issue_column="Actual gross", 
        issue_type="POTENTIAL_ID_OR_TEXT", 
        issue_evidence=evidence_gross, 
        profiler_output={}
    )
    for c in candidates:
        print(f"Strategy: {c.ir.operation.value}")
        print(f"Rationale: {c.ir.rationale}")
        print(f"Parameters: {c.ir.parameters}")

asyncio.run(run_test())
