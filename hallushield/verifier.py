from __future__ import annotations

import json
import os
import re
from typing import List, Optional

from .types import Evidence, VerificationResult


class NLIVerifier:
    def __init__(self) -> None:
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.default_model = os.getenv("HALLUSHIELD_VERIFIER_MODEL")

    async def verify(self, claim_id: str, claim: str, evidence_list: List[Evidence]) -> VerificationResult:
        if not evidence_list:
            return VerificationResult(
                claim_id=claim_id,
                support_score=0.0,
                contradiction_score=0.0,
                neutral_score=1.0,
                evidence_agreement=0.0,
                source_count=0,
                evidence_ids=[],
            )

        llm_result = await self._verify_with_llm(claim, evidence_list)
        if llm_result is not None:
            return VerificationResult(
                claim_id=claim_id,
                support_score=float(llm_result.get("support_score", 0.0)),
                contradiction_score=float(llm_result.get("contradiction_score", 0.0)),
                neutral_score=float(llm_result.get("neutral_score", 1.0)),
                evidence_agreement=float(llm_result.get("confidence", 0.0)),
                source_count=len(evidence_list),
                evidence_ids=[e.source_url for e in evidence_list],
            )

        support = self._heuristic_support(claim, evidence_list)
        contradiction = 0.0
        neutral = max(0.0, 1.0 - support - contradiction)
        return VerificationResult(
            claim_id=claim_id,
            support_score=support,
            contradiction_score=contradiction,
            neutral_score=neutral,
            evidence_agreement=support,
            source_count=len(evidence_list),
            evidence_ids=[e.source_url for e in evidence_list],
        )

    async def _verify_with_llm(self, claim: str, evidence_list: List[Evidence]) -> Optional[dict]:
        provider = os.getenv("HALLUSHIELD_PROVIDER")
        model = os.getenv("HALLUSHIELD_VERIFIER_MODEL") or self.default_model

        if provider == "groq":
            # Groq doesn't support structured JSON well for verification yet, default to Gemini
            provider = "google"

        if provider == "google" and os.getenv("GEMINI_API_KEY"):
            from langchain_google_genai import ChatGoogleGenerativeAI
            
            # Use Flash for verification (fast & cheap)
            model = model or "gemini-2.5-flash"
            
            llm = ChatGoogleGenerativeAI(
                model=model,
                temperature=0.0,
                max_output_tokens=1000,
            )
            content = self._build_prompt(claim, evidence_list)
            resp = await llm.ainvoke(content)
            return self._parse_json(resp.content)

        if provider == "anthropic" and self.anthropic_api_key:
            from langchain_anthropic import ChatAnthropic
            
            model = model or "claude-3-haiku-20240307"

            llm = ChatAnthropic(model=model, temperature=0.0, max_tokens=1000)
            content = self._build_prompt(claim, evidence_list)
            resp = await llm.ainvoke(content)
            return self._parse_json(resp.content)

        if provider == "openai" and self.openai_api_key:
            from langchain_openai import ChatOpenAI
            
            model = model or "gpt-4o-mini"

            llm = ChatOpenAI(model=model, temperature=0.0, max_tokens=1000)
            content = self._build_prompt(claim, evidence_list)
            resp = await llm.ainvoke(content)
            return self._parse_json(resp.content)

        return None

    def _build_prompt(self, claim: str, evidence_list: List[Evidence]) -> str:
        evidence_text = "\n\n".join(
            [
                f"Source {i + 1} ({e.source_url}):\n{e.snippet}"
                for i, e in enumerate(evidence_list)
            ]
        )

        return (
            "You are a fact-verification expert. Analyze if the evidence supports, contradicts, or is neutral to the claim.\n\n"
            f"CLAIM: {claim}\n\n"
            f"EVIDENCE:\n{evidence_text}\n\n"
            "Return ONLY a JSON object with this exact structure (no markdown, no code blocks):\n"
            "{\n"
            "  \"verdict\": \"SUPPORTED\" | \"CONTRADICTED\" | \"NEUTRAL\",\n"
            "  \"support_score\": 0.0-1.0,\n"
            "  \"contradiction_score\": 0.0-1.0,\n"
            "  \"neutral_score\": 0.0-1.0,\n"
            "  \"confidence\": 0.0-1.0,\n"
            "  \"reasoning\": \"brief explanation\",\n"
            "  \"supporting_evidence_indices\": []\n"
            "}\n\n"
            "Scores must sum to 1.0."
        )

    def _parse_json(self, text: str) -> Optional[dict]:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if not m:
                return None
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None

    def _heuristic_support(self, claim: str, evidence_list: List[Evidence]) -> float:
        tokens = [t.lower() for t in re.findall(r"[A-Za-z0-9]+", claim) if len(t) >= 4]
        if not tokens:
            return 0.3

        scores = []
        for e in evidence_list:
            hay = (e.snippet or "").lower()
            hit = sum(1 for t in tokens if t in hay)
            scores.append(hit / max(1, len(tokens)))

        base = max(scores) if scores else 0.0
        return max(0.0, min(1.0, 0.2 + 0.8 * base))
