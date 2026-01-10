from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

try:
    from langgraph.graph import END, StateGraph
except Exception:  # pragma: no cover
    END = None
    StateGraph = None

from .claim_extractor import ClaimExtractor
from .evidence_retriever import EvidenceRetriever
from .memory_store import MemoryStore
from .policy import AdaptiveDecisionPolicy
from .state import HalluShieldState
from .types import Decision, Evidence, VerificationResult
from .verifier import NLIVerifier


class HalluShieldPipeline:
    def __init__(
        self,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
        db_connection_string: Optional[str] = None,
    ) -> None:
        self.llm_provider = llm_provider or os.getenv("HALLUSHIELD_PROVIDER")
        self.llm_model = llm_model or os.getenv("HALLUSHIELD_LLM_MODEL")
        self.db_connection_string = db_connection_string

        self.claim_extractor = ClaimExtractor()
        self.evidence_retriever = EvidenceRetriever()
        self.verifier = NLIVerifier()
        self.policy = AdaptiveDecisionPolicy()
        self.memory_store = MemoryStore(db_connection_string)

        self.app = None
        if StateGraph is not None:
            workflow = self._build_workflow()
            self.app = workflow.compile()

    def _build_workflow(self):
        if StateGraph is None:
            raise RuntimeError("langgraph is not available")

        workflow: StateGraph = StateGraph(HalluShieldState)

        workflow.add_node("call_llm", self._call_llm)
        workflow.add_node("extract_claims", self._extract_claims)
        workflow.add_node("check_memory", self._check_memory)
        workflow.add_node("retrieve_evidence", self._retrieve_evidence)
        workflow.add_node("verify_claims", self._verify_claims)
        workflow.add_node("check_escalation", self._check_escalation)
        workflow.add_node("apply_policy", self._apply_policy)
        workflow.add_node("assemble_answer", self._assemble_answer)
        workflow.add_node("update_memory", self._update_memory)

        workflow.set_entry_point("call_llm")
        workflow.add_edge("call_llm", "extract_claims")
        workflow.add_edge("extract_claims", "check_memory")
        workflow.add_conditional_edges(
            "check_memory",
            self._route_by_cache,
            {"has_new_claims": "retrieve_evidence", "all_cached": "check_escalation"},
        )
        workflow.add_edge("retrieve_evidence", "verify_claims")
        workflow.add_edge("verify_claims", "check_escalation")
        workflow.add_conditional_edges(
            "check_escalation",
            self._route_by_escalation,
            {"escalate_to_llm": "call_llm", "proceed": "apply_policy"},
        )
        workflow.add_edge("apply_policy", "assemble_answer")
        workflow.add_edge("assemble_answer", "update_memory")
        workflow.add_edge("update_memory", END)

        return workflow

    def _route_by_cache(self, state: HalluShieldState) -> str:
        if len(state.get("cached_claims", {})) == len(state.get("claims", [])):
            return "all_cached"
        return "has_new_claims"

    async def _call_llm(self, state: HalluShieldState) -> Dict[str, Any]:
        """
        Call LLM with SLM-first approach and escalation logic
        Now uses ModelRouter for multi-provider support
        """
        from .model_router import ModelRouter
        
        query = state["query"]
        
        # Initialize router if not already done
        if not hasattr(self, "model_router"):
            self.model_router = ModelRouter()
        
        # Check if we should force LLM tier
        force_llm = state.get("force_llm_tier", False)
        
        if force_llm:
            # Direct LLM call (escalated from SLM)
            llm_model = self.llm_model or "gemini-2.5-flash"
            response = await self.model_router.get_response(
                query=query,
                model_tier="llm",
                llm_model=llm_model,
            )
        else:
            # Try SLM first (default behavior)
            slm_model = os.getenv("HALLUSHIELD_SLM_MODEL", "llama-3.3-70b-versatile")
            response = await self.model_router.get_response(
                query=query,
                model_tier="slm",
                slm_model=slm_model,
            )
        
        return {
            "raw_llm_response": response.text,
            "llm_metadata": {
                "provider": response.provider,
                "model": response.model,
                "tier": response.tier,
                "tokens": response.tokens,
                "cost": response.cost,
                **response.metadata,
            },
        }

    async def _extract_claims(self, state: HalluShieldState) -> Dict[str, Any]:
        claims = self.claim_extractor.extract(state.get("raw_llm_response", ""))
        return {"claims": claims}

    async def _check_memory(self, state: HalluShieldState) -> Dict[str, Any]:
        cached: Dict[str, Any] = {}
        for claim in state.get("claims", []):
            cached_result = self.memory_store.check_claim(claim.text)
            if cached_result:
                cached[claim.id] = cached_result
        return {"cached_claims": cached}

    async def _retrieve_evidence(self, state: HalluShieldState) -> Dict[str, Any]:
        evidence_map: Dict[str, List[Evidence]] = {}
        cached = state.get("cached_claims", {})
        for claim in state.get("claims", []):
            if claim.id in cached:
                continue
            evidence_map[claim.id] = await self.evidence_retriever.retrieve(claim.text)
        return {"evidence_map": evidence_map}

    async def _verify_claims(self, state: HalluShieldState) -> Dict[str, Any]:
        verification_results: Dict[str, VerificationResult] = {}
        for claim in state.get("claims", []):
            evidence_list = (state.get("evidence_map") or {}).get(claim.id)
            if not evidence_list:
                continue
            verification_results[claim.id] = await self.verifier.verify(claim.id, claim.text, evidence_list)
        return {"verification_results": verification_results}

    def _route_by_escalation(self, state: HalluShieldState) -> str:
        """Route based on escalation decision"""
        should_escalate = state.get("should_escalate", False)
        return "escalate_to_llm" if should_escalate else "proceed"

    async def _check_escalation(self, state: HalluShieldState) -> Dict[str, Any]:
        """
        Check if we should escalate from SLM to LLM based on:
        1. Model tier used (if already LLM, don't re-escalate)
        2. Hallucination score from verifications
        3. Overall confidence
        """
        from .model_router import ModelRouter
        
        # Initialize router if not already done
        if not hasattr(self, "model_router"):
            self.model_router = ModelRouter()
        
        # Check if we already used LLM tier
        llm_metadata = state.get("llm_metadata", {})
        current_tier = llm_metadata.get("tier", "slm")
        
        # Don't re-escalate if already using LLM
        if current_tier == "llm":
            return {"should_escalate": False, "escalation_reason": "Already using LLM tier"}
        
        # Calculate hallucination score from verifications
        verifications = state.get("verification_results", {})
        total_verifications = len(verifications)
        
        if total_verifications == 0:
            # No verifications yet (all cached), use low hallucination score
            hallucination_score = 0.0
            confidence = 1.0
        else:
            # Calculate based on verification results
            problematic_count = sum(
                1 for v in verifications.values()
                if v.contradiction_score > 0.5 or v.neutral_score > 0.7
            )
            hallucination_score = problematic_count / total_verifications
            
            # Calculate average confidence (using support score as proxy)
            avg_support = sum(v.support_score for v in verifications.values()) / total_verifications
            confidence = avg_support
        
        # Build a mock ModelResponse to check escalation
        from .model_router import ModelResponse
        
        slm_response = ModelResponse(
            text=state.get("raw_llm_response", ""),
            model=llm_metadata.get("model", "unknown"),
            provider=llm_metadata.get("provider", "unknown"),
            tier="slm",
            tokens=llm_metadata.get("tokens", 0),
            cost=llm_metadata.get("cost", 0.0),
        )
        
        # Check if escalation needed
        should_escalate, reason = self.model_router.should_escalate(
            slm_response=slm_response,
            hallucination_score=hallucination_score,
            confidence=confidence,
        )
        
        if should_escalate:
            # Update stats
            self.model_router.stats["escalations"] += 1
            
            # Calculate cost saved by using SLM first
            slm_cost = slm_response.cost
            estimated_llm_cost = self.model_router._calculate_cost(slm_response.tokens, "llm_pro")
            cost_saved = estimated_llm_cost - slm_cost
            self.model_router.stats["cost_saved"] = self.model_router.stats.get("cost_saved", 0.0) + cost_saved
        
        return {
            "should_escalate": should_escalate,
            "escalation_reason": reason,
            "hallucination_score_detected": hallucination_score,
            "confidence_detected": confidence,
            "force_llm_tier": should_escalate,  # This flag tells _call_llm to use LLM
        }

    async def _apply_policy(self, state: HalluShieldState) -> Dict[str, Any]:
        decisions: List[Decision] = []
        for claim in state.get("claims", []):
            cached = (state.get("cached_claims") or {}).get(claim.id)
            if cached:
                decisions.append(
                    Decision(
                        claim_id=claim.id,
                        action=cached["action"],
                        original_claim=claim.text,
                        corrected_claim=cached.get("corrected_claim"),
                        evidence_urls=cached.get("evidence_urls", []),
                        confidence=float(cached.get("confidence", 1.0)),
                        reasoning="From cache",
                    )
                )
                continue

            verification = (state.get("verification_results") or {}).get(claim.id)
            evidence = (state.get("evidence_map") or {}).get(claim.id, [])
            if verification is None:
                verification = VerificationResult(
                    claim_id=claim.id,
                    support_score=0.0,
                    contradiction_score=0.0,
                    neutral_score=1.0,
                    evidence_agreement=0.0,
                    source_count=len(evidence),
                    evidence_ids=[e.source_url for e in evidence],
                )

            decisions.append(self.policy.decide(claim, verification, evidence))

        return {"decisions": decisions}

    async def _assemble_answer(self, state: HalluShieldState) -> Dict[str, Any]:
        verified_answer = state.get("raw_llm_response", "")
        modifications: List[Dict[str, Any]] = []

        for decision in state.get("decisions", []):
            if decision.action == "CORRECT" and decision.corrected_claim:
                verified_answer = verified_answer.replace(
                    decision.original_claim,
                    f"{decision.corrected_claim} [CORRECTED]",
                )
                modifications.append(
                    {
                        "type": "correction",
                        "original": decision.original_claim,
                        "corrected": decision.corrected_claim,
                        "evidence": decision.evidence_urls[:3],
                    }
                )
            elif decision.action == "ABSTAIN":
                modifications.append(
                    {
                        "type": "uncertainty",
                        "claim": decision.original_claim,
                        "reason": "Insufficient evidence",
                    }
                )
            elif decision.action == "FLAG_FOR_HUMAN":
                modifications.append(
                    {
                        "type": "flagged",
                        "claim": decision.original_claim,
                        "reason": decision.reasoning,
                    }
                )

        total_claims = len(state.get("decisions", []))
        problematic = sum(
            1
            for d in state.get("decisions", [])
            if d.action in ["CORRECT", "FLAG_FOR_HUMAN"]
        )
        hallucination_score = (problematic / total_claims) if total_claims else 0.0

        final_answer = {
            "verified_answer": verified_answer,
            "original_answer": state.get("raw_llm_response", ""),
            "modifications": modifications,
            "hallucination_score": float(hallucination_score),
            "confidence": float(1.0 - hallucination_score),
            "claim_breakdown": {
                "total_claims": total_claims,
                "verified": sum(1 for d in state.get("decisions", []) if d.action == "ACCEPT"),
                "corrected": sum(1 for d in state.get("decisions", []) if d.action == "CORRECT"),
                "abstained": sum(1 for d in state.get("decisions", []) if d.action == "ABSTAIN"),
                "flagged": sum(1 for d in state.get("decisions", []) if d.action == "FLAG_FOR_HUMAN"),
            },
        }

        return {"final_answer": final_answer}

    async def _update_memory(self, state: HalluShieldState) -> Dict[str, Any]:
        cached = state.get("cached_claims", {})
        for decision in state.get("decisions", []):
            if decision.claim_id in cached:
                continue
            self.memory_store.store_verification(
                claim_text=decision.original_claim,
                action=decision.action,
                corrected_claim=decision.corrected_claim,
                evidence_urls=decision.evidence_urls,
                confidence=decision.confidence,
            )
        return {}

    async def verify(self, query: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        start = time.time()
        state: HalluShieldState = {"query": query, "user_id": user_id, "errors": []}

        if self.app is not None:
            result = await self.app.ainvoke(state)
        else:
            # Sequential fallback when langgraph isn't installed.
            result: Dict[str, Any] = dict(state)
            result.update(await self._call_llm(result))
            result.update(await self._extract_claims(result))
            result.update(await self._check_memory(result))

            if self._route_by_cache(result) == "has_new_claims":
                result.update(await self._retrieve_evidence(result))
                result.update(await self._verify_claims(result))
            else:
                result.setdefault("evidence_map", {})
                result.setdefault("verification_results", {})

            result.update(await self._apply_policy(result))
            result.update(await self._assemble_answer(result))
            result.update(await self._update_memory(result))

        result["processing_time"] = time.time() - start
        return result
