from typing import Protocol, Dict, Any
import json
import asyncio
import time
import threading

class LLMProvider(Protocol):
    async def complete(self, prompt: str, schema: dict, max_tokens: int = 2000, system_prompt: str = None) -> str:
        ...

class OpenAILLMProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        import openai
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model
        
    async def complete(self, prompt: str, schema: dict, max_tokens: int = 2000, system_prompt: str = None) -> str:
        print(f"[Agent Orchestrator] Querying real LLM ({self.model}) for issue...")
        
        default_sys = "You are an expert data engineer AI. Return ONLY a valid JSON object matching the provided JSON schema. No markdown wrapping. You must output an array of 'candidates' where each is a valid TransformationIR object. Allowed operations: KEEP, FLAG, DROP_ROWS_PREDICATE, DROP_ROWS_EXACT_DUPLICATE, IMPUTE_CONSTANT, IMPUTE_KNN, IMPUTE_MEAN, IMPUTE_MEDIAN, IMPUTE_MODE, TRIM_WHITESPACE, NORMALIZE_CATEGORICAL, CAST_TYPE, REGEX_REPLACE. IMPUTATION RULES: DO NOT use FLAG for missing values; you MUST use an IMPUTE_* operation instead. Use IMPUTE_MEAN when data is normally distributed (numeric without major outliers). Use IMPUTE_MEDIAN when numeric data has outliers or is skewed. Use IMPUTE_MODE when data is categorical or strings. REGEX RULES: If using REGEX_REPLACE, you MUST provide the 'pattern' and 'replacement' keys inside the 'parameters' dictionary."
        sys_prompt = system_prompt or default_sys
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": f"Schema:\n{json.dumps(schema)}\n\nPrompt:\n{prompt}"}
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"[Agent Orchestrator] LLM Provider error: {e}")
            return json.dumps({"candidates": []})

class GeminiLLMProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "gemini-3.6-flash"):
        from google import genai
        self.client = genai.Client(api_key=api_key)
        self.model = model
        
    def _make_sync_call(self, prompt: str, schema: dict, max_tokens: int, system_prompt: str = None) -> str:
        """Synchronous Gemini API call - safe to run from any thread."""
        from google.genai import types
        from google.genai.errors import APIError
        
        default_sys = (
            "You are an expert data engineer AI. Return ONLY a valid JSON object matching the provided JSON schema. "
            "No markdown wrapping. You must output an array of 'candidates' where each is a valid TransformationIR object. "
            "CRITICAL: Every candidate MUST include 'operation' (string), 'rationale' (string), 'risk_level' (string: LOW, MEDIUM, or HIGH), "
            "and 'agent_confidence' (string: LOW, MEDIUM, or HIGH). "
            "Allowed operations: KEEP, FLAG, DROP_ROWS_PREDICATE, DROP_ROWS_EXACT_DUPLICATE, IMPUTE_CONSTANT, IMPUTE_KNN, IMPUTE_MEAN, IMPUTE_MEDIAN, IMPUTE_MODE, TRIM_WHITESPACE, NORMALIZE_CATEGORICAL, CAST_TYPE, REGEX_REPLACE. "
            "IMPUTATION RULES: DO NOT use FLAG for missing values; you MUST use an IMPUTE_* operation instead. Use IMPUTE_MEAN when data is normally distributed (numeric without major outliers). Use IMPUTE_MEDIAN when numeric data has outliers or is skewed. Use IMPUTE_MODE when data is categorical or strings. "
            "REGEX RULES: If using REGEX_REPLACE, you MUST provide the 'pattern' and 'replacement' keys inside the 'parameters' dictionary."
        )
        
        sys_prompt = system_prompt or default_sys
        
        retries = 3
        for attempt in range(retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=f"System: {sys_prompt}\n\nSchema:\n{json.dumps(schema)}\n\nPrompt:\n{prompt}",
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.1,
                        max_output_tokens=max_tokens
                    )
                )
                return response.text
            except APIError as e:
                if e.code in (429, 503):
                    wait_time = 20
                    print(f"[Agent Orchestrator] Rate limit/unavailable (code {e.code}). Sleeping {wait_time}s before retry (Attempt {attempt+1}/{retries})...")
                    time.sleep(wait_time)
                else:
                    print(f"[Agent Orchestrator] Gemini Provider error: {e}")
                    return json.dumps({"candidates": []})
            except Exception as e:
                print(f"[Agent Orchestrator] Gemini Provider error: {e}")
                return json.dumps({"candidates": []})
                
        print(f"[Agent Orchestrator] Exhausted retries due to rate limiting.")
        return json.dumps({"candidates": []})
        
    async def complete(self, prompt: str, schema: dict, max_tokens: int = 2000, system_prompt: str = None) -> str:
        print(f"[Agent Orchestrator] Querying real LLM ({self.model}) for issue...")
        # Run the synchronous Gemini call in a thread to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._make_sync_call, prompt, schema, max_tokens, system_prompt
        )
