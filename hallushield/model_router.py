"""
Multi-Provider Model Router for HalluShield
Supports: Groq (SLM), Gemini (LLM), HuggingFace (SLM), Claude (LLM fallback)
"""
from __future__ import annotations

import os
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel


class ModelResponse(BaseModel):
    """Response from any model provider"""
    text: str
    model: str
    provider: str
    tier: Literal["slm", "llm"]
    tokens: int = 0
    cost: float = 0.0
    metadata: Dict[str, Any] = {}


class ModelRouter:
    """
    Intelligent router that starts with SLM and escalates to LLM when needed
    
    Tier 1 (SLM - Fast & Cheap):
    - Groq: llama-3.3-70b-versatile, llama-3.1-8b-instant
    - HuggingFace: Mistral-7B, Phi-3
    
    Tier 2 (LLM - Premium):
    - Gemini: gemini-2.5-flash, gemini-2.5-pro
    - Claude: claude-sonnet-4-20250514 (fallback)
    """
    
    def __init__(self):
        # Track usage stats
        self.stats = {
            "slm_calls": 0,
            "llm_calls": 0,
            "escalations": 0,
            "total_cost": 0.0,
            "cost_saved": 0.0,
        }
        
        # Cost per 1M tokens (approximate)
        self.cost_table = {
            "slm": 0.10,  # $0.10 per 1M tokens
            "llm_flash": 0.50,  # Gemini Flash
            "llm_pro": 2.00,  # Gemini Pro / Claude
        }
    
    async def get_response(
        self,
        query: str,
        model_tier: Literal["slm", "llm", "auto"] = "auto",
        slm_model: str = "llama-3.3-70b-versatile",
        llm_model: str = "gemini-2.5-flash",
    ) -> ModelResponse:
        """
        Get response with intelligent tier selection
        
        Args:
            query: User query
            model_tier: "slm" | "llm" | "auto" (auto starts with SLM)
            slm_model: Groq model name for SLM tier
            llm_model: Gemini model name for LLM tier
            
        Returns:
            ModelResponse with text, metadata, and cost information
        """
        
        if model_tier == "llm":
            return await self._call_llm(query, llm_model)
        elif model_tier == "slm":
            return await self._call_slm(query, slm_model)
        else:
            # Auto mode: Try SLM first (will implement escalation logic later)
            return await self._call_slm(query, slm_model)
    
    async def _call_slm(self, query: str, model: str) -> ModelResponse:
        """Call Small Language Model via Groq"""
        self.stats["slm_calls"] += 1
        
        try:
            # Try Groq first
            return await self._call_groq(query, model)
        except Exception as groq_error:
            print(f"Groq error: {groq_error}")
            # Fallback to HuggingFace
            try:
                return await self._call_huggingface(query)
            except Exception as hf_error:
                print(f"HuggingFace error: {hf_error}")
                raise Exception(f"All SLM providers failed: Groq={groq_error}, HF={hf_error}")
    
    async def _call_groq(self, query: str, model: str) -> ModelResponse:
        """Call Groq API for SLM"""
        from groq import Groq
        
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not found in environment")
        
        client = Groq(api_key=api_key)
        
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant. Provide accurate, concise answers. If you're unsure about something, clearly state your uncertainty.",
                },
                {
                    "role": "user",
                    "content": query,
                },
            ],
            model=model,
            temperature=0.0,  # Deterministic for fact-based queries
            max_tokens=2000,
        )
        
        response_text = chat_completion.choices[0].message.content
        total_tokens = chat_completion.usage.total_tokens if chat_completion.usage else 0
        cost = self._calculate_cost(total_tokens, "slm")
        
        self.stats["total_cost"] += cost
        
        return ModelResponse(
            text=response_text,
            model=model,
            provider="groq",
            tier="slm",
            tokens=total_tokens,
            cost=cost,
            metadata={
                "finish_reason": chat_completion.choices[0].finish_reason,
                "prompt_tokens": chat_completion.usage.prompt_tokens if chat_completion.usage else 0,
                "completion_tokens": chat_completion.usage.completion_tokens if chat_completion.usage else 0,
            },
        )
    
    async def _call_huggingface(self, query: str) -> ModelResponse:
        """Fallback: Call HuggingFace Inference API"""
        from huggingface_hub import InferenceClient
        
        hf_token = os.getenv("HF_TOKEN")
        if not hf_token:
            raise ValueError("HF_TOKEN not found in environment")
        
        client = InferenceClient(api_key=hf_token)
        
        response = client.chat.completions.create(
            model="mistralai/Mistral-7B-Instruct-v0.3",
            messages=[{"role": "user", "content": query}],
            max_tokens=2000,
            temperature=0.0,
        )
        
        response_text = response.choices[0].message.content
        # Estimate tokens since HF doesn't always return usage
        estimated_tokens = int(len(response_text.split()) * 1.3)
        cost = self._calculate_cost(estimated_tokens, "slm")
        
        self.stats["total_cost"] += cost
        
        return ModelResponse(
            text=response_text,
            model="Mistral-7B-Instruct-v0.3",
            provider="huggingface",
            tier="slm",
            tokens=estimated_tokens,
            cost=cost,
            metadata={"finish_reason": response.choices[0].finish_reason if hasattr(response.choices[0], "finish_reason") else "stop"},
        )
    
    async def _call_llm(self, query: str, model: str) -> ModelResponse:
        """Call Premium Large Language Model via Gemini"""
        self.stats["llm_calls"] += 1
        
        try:
            # Try Gemini first
            return await self._call_gemini(query, model)
        except Exception as gemini_error:
            print(f"Gemini error: {gemini_error}")
            # Fallback to Claude
            try:
                return await self._call_claude(query)
            except Exception as claude_error:
                print(f"Claude error: {claude_error}")
                raise Exception(f"All LLM providers failed: Gemini={gemini_error}, Claude={claude_error}")
    
    async def _call_gemini(self, query: str, model: str) -> ModelResponse:
        """Call Google Gemini API"""
        from google import genai
        
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment")
        
        client = genai.Client(api_key=api_key)
        
        response = client.models.generate_content(
            model=model,
            contents=query,
            config={
                "temperature": 0.0,
                "max_output_tokens": 2000,
            },
        )
        
        response_text = response.text
        
        # Estimate tokens (Gemini doesn't always return usage metadata)
        estimated_tokens = int(len(query.split()) * 1.3 + len(response_text.split()) * 1.3)
        
        # Determine cost tier
        cost_tier = "llm_flash" if "flash" in model.lower() else "llm_pro"
        cost = self._calculate_cost(estimated_tokens, cost_tier)
        
        self.stats["total_cost"] += cost
        
        return ModelResponse(
            text=response_text,
            model=model,
            provider="gemini",
            tier="llm",
            tokens=estimated_tokens,
            cost=cost,
            metadata={
                "model_version": model,
            },
        )
    
    async def _call_claude(self, query: str) -> ModelResponse:
        """Fallback: Call Anthropic Claude API"""
        from anthropic import Anthropic
        
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")
        
        client = Anthropic(api_key=api_key)
        
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            temperature=0.0,
            messages=[{"role": "user", "content": query}],
        )
        
        response_text = message.content[0].text
        total_tokens = message.usage.input_tokens + message.usage.output_tokens
        cost = self._calculate_cost(total_tokens, "llm_pro")
        
        self.stats["total_cost"] += cost
        
        return ModelResponse(
            text=response_text,
            model="claude-sonnet-4-20250514",
            provider="anthropic",
            tier="llm",
            tokens=total_tokens,
            cost=cost,
            metadata={
                "stop_reason": message.stop_reason,
                "input_tokens": message.usage.input_tokens,
                "output_tokens": message.usage.output_tokens,
            },
        )
    
    def _calculate_cost(self, tokens: int, tier: str) -> float:
        """Calculate approximate cost based on tokens and tier"""
        cost_per_million = self.cost_table.get(tier, 1.0)
        return (tokens / 1_000_000) * cost_per_million
    
    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics"""
        total_calls = self.stats["slm_calls"] + self.stats["llm_calls"]
        
        return {
            "slm_calls": self.stats["slm_calls"],
            "llm_calls": self.stats["llm_calls"],
            "total_calls": total_calls,
            "escalations": self.stats["escalations"],
            "escalation_rate": self.stats["escalations"] / max(self.stats["slm_calls"], 1),
            "total_cost": round(self.stats["total_cost"], 4),
            "cost_saved": round(self.stats.get("cost_saved", 0.0), 4),
            "avg_cost_per_query": round(self.stats["total_cost"] / max(total_calls, 1), 4),
        }
    
    def should_escalate(
        self,
        slm_response: ModelResponse,
        hallucination_score: float = 0.0,
        confidence: float = 1.0,
    ) -> tuple[bool, str]:
        """
        Determine if SLM response needs escalation to LLM
        
        Args:
            slm_response: Response from SLM
            hallucination_score: Score from verification (0.0 - 1.0, higher = more hallucinations)
            confidence: Confidence score (0.0 - 1.0, higher = more confident)
            
        Returns:
            (should_escalate, reason)
        """
        text = slm_response.text.lower()
        
        # Check 1: SLM expressed uncertainty
        uncertainty_phrases = [
            "i don't know",
            "i'm not sure",
            "i cannot",
            "i don't have",
            "unclear",
            "uncertain",
            "i cannot confirm",
        ]
        
        if any(phrase in text for phrase in uncertainty_phrases):
            return True, "SLM expressed uncertainty"
        
        # Check 2: High hallucination score (>30%)
        if hallucination_score > 0.3:
            return True, f"High hallucination rate: {hallucination_score:.1%}"
        
        # Check 3: Low confidence (<50%)
        if confidence < 0.5:
            return True, f"Low verification confidence: {confidence:.2f}"
        
        # Check 4: Very short response (might indicate lack of knowledge)
        if len(text.split()) < 10:
            return True, "Response too brief, may lack detail"
        
        return False, "No escalation needed"
