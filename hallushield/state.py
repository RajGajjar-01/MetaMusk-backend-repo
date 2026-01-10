from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

from .types import Claim, Decision, Evidence, VerificationResult


class HalluShieldState(TypedDict, total=False):
    query: str
    user_id: Optional[str]

    raw_llm_response: str
    llm_metadata: Dict[str, Any]

    claims: List[Claim]

    evidence_map: Dict[str, List[Evidence]]

    verification_results: Dict[str, VerificationResult]

    decisions: List[Decision]

    cached_claims: Dict[str, Any]

    final_answer: Dict[str, Any]
    
    # Escalation fields
    should_escalate: bool
    escalation_reason: str
    hallucination_score_detected: float
    confidence_detected: float
    force_llm_tier: bool

    processing_time: float
    errors: List[str]
