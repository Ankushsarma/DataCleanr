import json
import uuid
from typing import List, Dict, Any, Optional

from app.models.ir import validate_agent_response, IRCandidate, RejectedResponse
from app.services.llm import LLMProvider
from app.services.evidence import EvidenceCompiler

class AgentOrchestrator:
    """
    Manages the prompt construction, LLM interaction, and validation loop
    for the single reasoning agent.
    """
    def __init__(self, primary_provider: LLMProvider, fallback_provider: Optional[LLMProvider] = None):
        self.primary = primary_provider
        self.fallback = fallback_provider
        
    async def propose(
        self, 
        issue_id: str,
        issue_column: str,
        issue_type: str,
        issue_evidence: Dict[str, Any],
        profiler_output: Dict[str, Any],
        failure_memory: Optional[list] = None
    ) -> List[IRCandidate]:
        """
        Generates transformation candidates for a given issue.
        """
        evidence_pkg = EvidenceCompiler.compile(
            issue_column=issue_column,
            issue_type=issue_type,
            issue_evidence=issue_evidence,
            profiler_output=profiler_output,
            failure_memory=failure_memory
        )
        
        prompt = self._build_prompt(evidence_pkg)
        
        try:
            response_text = await self.primary.complete(prompt=prompt, schema={}, max_tokens=2000)
            
            try:
                raw_json_list = json.loads(response_text)
            except json.JSONDecodeError as e:
                # Attempt to repair truncated JSON by closing open strings/brackets
                print(f"Agent returned malformed JSON, attempting repair: {e}")
                repaired = self._repair_json(response_text)
                try:
                    raw_json_list = json.loads(repaired)
                except json.JSONDecodeError:
                    print(f"Agent failed to return valid JSON even after repair.")
                    return []
            
            try:
                if isinstance(raw_json_list, dict) and "candidates" in raw_json_list:
                    raw_json_list = raw_json_list["candidates"]
                elif not isinstance(raw_json_list, list):
                    raw_json_list = [raw_json_list]
                    
                valid_candidates = []
                for raw_json in raw_json_list:
                    # Overwrite injected IDs to match the current pipeline state
                    raw_json["issue_id"] = issue_id
                    raw_json["target_column"] = issue_column
                    
                    validation_result = validate_agent_response(raw_json)
                    
                    if isinstance(validation_result, IRCandidate):
                        valid_candidates.append(validation_result)
                    else:
                        print(f"Agent response rejected: {validation_result.reason} - {validation_result.detail}")
                        
                return valid_candidates
                    
            except Exception as e:
                print(f"Agent failed to parse response: {e}")
                return []
                
        except Exception as e:
            print(f"LLM Provider error: {e}")
            return []
            
    def _build_prompt(self, evidence: Dict[str, Any]) -> str:
        # In a real implementation, this would be a sophisticated Jinja template.
        evidence_str = json.dumps(evidence, indent=2)
        return f"""
        You are an expert data engineer and reasoning agent.
        Analyze the following data quality issue and propose a safe, deterministic transformation.
        
        EVIDENCE PACKAGE:
        {evidence_str}
        
        Output valid JSON matching an ARRAY of TransformationIR schemas.
        """
    
    @staticmethod
    def _repair_json(text: str) -> str:
        """Attempt to repair truncated JSON by closing open strings, arrays, and objects."""
        # Strip any trailing whitespace
        text = text.rstrip()
        
        # Track open delimiters
        in_string = False
        escape_next = False
        stack = []
        
        for ch in text:
            if escape_next:
                escape_next = False
                continue
            if ch == '\\' and in_string:
                escape_next = True
                continue
            if ch == '"' and not escape_next:
                in_string = not in_string
                continue
            if not in_string:
                if ch in ('{', '['):
                    stack.append(ch)
                elif ch == '}' and stack and stack[-1] == '{':
                    stack.pop()
                elif ch == ']' and stack and stack[-1] == '[':
                    stack.pop()
        
        # Close any open string
        if in_string:
            text += '"'
        
        # Close open brackets/braces in reverse order
        for opener in reversed(stack):
            if opener == '{':
                text += '}'
            elif opener == '[':
                text += ']'
        
        return text

