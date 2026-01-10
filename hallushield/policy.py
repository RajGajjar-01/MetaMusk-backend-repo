from __future__ import annotations

from typing import List

from .types import Claim, Decision, Evidence, VerificationResult


class AdaptiveDecisionPolicy:
    def decide(self, claim: Claim, verification: VerificationResult, evidence: List[Evidence]) -> Decision:
        action = self._rule_based_action(verification)
        return Decision(
            claim_id=claim.id,
            action=action,
            original_claim=claim.text,
            corrected_claim=None,
            evidence_urls=[e.source_url for e in evidence],
            confidence=float(verification.evidence_agreement),
            reasoning=self._reasoning(action),
        )

    def _rule_based_action(self, verification: VerificationResult) -> str:
        if verification.support_score > 0.85 and verification.contradiction_score < 0.1:
            return "ACCEPT"
        if verification.contradiction_score > 0.7:
            return "CORRECT"
        if verification.source_count < 2 or verification.evidence_agreement < 0.5:
            return "ABSTAIN"
        return "FLAG_FOR_HUMAN"

    def _reasoning(self, action: str) -> str:
        if action == "ACCEPT":
            return "Evidence supports the claim."
        if action == "CORRECT":
            return "Evidence contradicts the claim."
        if action == "ABSTAIN":
            return "Insufficient evidence confidence."
        return "Mixed evidence signals; requires review."
