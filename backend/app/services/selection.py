from typing import List, Optional
from app.db.models import CandidateModel

class SelectionResult:
    def __init__(self, decision: str, selected_candidate: Optional[CandidateModel] = None, reason: str = ""):
        self.decision = decision
        self.selected_candidate = selected_candidate
        self.reason = reason

class SelectionEngine:
    """
    Deterministically scores and selects the best candidate for an issue
    based on confidence, risk, and other penalties.
    """
    
    CONFIDENCE_MAP = {
        "HIGH": 10.0,
        "MEDIUM": 5.0,
        "LOW": 1.0
    }
    
    RISK_PENALTY = {
        "LOW": 0.0,
        "MEDIUM": 5.0,
        "HIGH": 15.0
    }
    
    @staticmethod
    def score_candidate(c: CandidateModel) -> float:
        # If it wasn't policy eligible, it gets a devastating score
        if not c.policy_eligible:
            return -999.0
            
        base_score = 10.0 # Base validation pass
        confidence_bonus = SelectionEngine.CONFIDENCE_MAP.get(c.agent_confidence, 0.0)
        risk_deduction = SelectionEngine.RISK_PENALTY.get(c.risk_level, 0.0)
        
        # Penalize modification percentage? The mock doesn't currently parse the constraints 
        # out of the JSON perfectly here, so we will stick to risk & confidence for MVP.
        
        return base_score + confidence_bonus - risk_deduction

    @staticmethod
    def select(candidates: List[CandidateModel]) -> SelectionResult:
        eligible = [c for c in candidates if c.policy_eligible]
        
        if not eligible:
            return SelectionResult(decision="KEEP_ORIGINAL", reason="no_eligible_candidate")
            
        # Score candidates
        # Storing the score temporarily on the object for sorting
        for c in eligible:
            c._selection_score = SelectionEngine.score_candidate(c)
            
        # Sort descending by score
        scored = sorted(eligible, key=lambda x: getattr(x, '_selection_score'), reverse=True)
        
        # Select the best one
        best_candidate = scored[0]
        
        # Clear out default selected flags on all candidates, and set the winner
        for c in candidates:
            c.selected = (c.candidate_id == best_candidate.candidate_id)
            c.selection_score = getattr(c, '_selection_score', -999.0)
            
        return SelectionResult(decision="MODIFY", selected_candidate=best_candidate)
