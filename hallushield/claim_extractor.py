from __future__ import annotations

import hashlib
import re
from typing import List

from .types import Claim


class ClaimExtractor:
    def extract(self, text: str) -> List[Claim]:
        sentences = self._split_sentences(text)
        claims: List[Claim] = []
        for idx, sent in enumerate(sentences):
            s = sent.strip()
            if not s:
                continue
            if s.endswith("?"):
                continue
            if not self._looks_factual(s):
                continue

            claim_text = self._normalize_claim(s)
            claims.append(
                Claim(
                    id=self._generate_claim_id(claim_text),
                    text=claim_text,
                    claim_type=self._infer_claim_type(s),
                    source_sentence=s,
                    position=idx,
                )
            )
        return claims

    def _split_sentences(self, text: str) -> List[str]:
        parts = re.split(r"(?<=[.!?])\s+", text.strip())
        return [p for p in parts if p.strip()]

    def _looks_factual(self, sentence: str) -> bool:
        has_digit = any(ch.isdigit() for ch in sentence)
        has_capitalized = bool(re.search(r"\b[A-Z][a-z]+\b", sentence))
        has_copula_or_verb = bool(
            re.search(
                r"\b(is|are|was|were|has|have|had|will|won|founded|born|died|released|created|located)\b",
                sentence,
                re.IGNORECASE,
            )
        )
        return has_digit or (has_capitalized and has_copula_or_verb)

    def _infer_claim_type(self, sentence: str) -> str:
        if re.search(r"\b(\d+|percent|%|usd|\$|million|billion)\b", sentence, re.IGNORECASE):
            return "numerical"
        if re.search(
            r"\b(\d{4}|jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec|yesterday|today|tomorrow)\b",
            sentence,
            re.IGNORECASE,
        ):
            return "temporal"
        if re.search(r"\b(in|at|near|located|based)\b", sentence, re.IGNORECASE):
            return "entity"
        return "event"

    def _normalize_claim(self, sentence: str) -> str:
        return re.sub(r"\s+", " ", sentence).strip()

    def _generate_claim_id(self, claim_text: str) -> str:
        return hashlib.md5(claim_text.encode("utf-8")).hexdigest()[:16]
