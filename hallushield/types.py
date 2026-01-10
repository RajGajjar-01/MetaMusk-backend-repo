from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Claim(BaseModel):
    id: str
    text: str
    claim_type: str
    source_sentence: str
    position: int


class Evidence(BaseModel):
    source_url: str
    snippet: str
    relevance_score: float
    publish_date: Optional[str] = None
    credibility_score: float = 0.5


class VerificationResult(BaseModel):
    claim_id: str
    support_score: float
    contradiction_score: float
    neutral_score: float
    evidence_agreement: float
    source_count: int
    evidence_ids: List[str]


class Decision(BaseModel):
    claim_id: str
    action: str
    original_claim: str
    corrected_claim: Optional[str] = None
    evidence_urls: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    reasoning: str = ""


class VerifyRequest(BaseModel):
    query: str
    user_id: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None


class VerifyResponse(BaseModel):
    verified_answer: str
    original_answer: str
    modifications: List[Dict[str, Any]]
    hallucination_score: float
    confidence: float
    claim_breakdown: Dict[str, int]
    decisions: List[Decision]
    claims: List[Claim]
    errors: List[str] = Field(default_factory=list)
