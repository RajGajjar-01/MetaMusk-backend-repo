from __future__ import annotations

import os
from typing import List

try:
    import httpx  # type: ignore
except Exception:  # pragma: no cover
    httpx = None

from .types import Evidence


class EvidenceRetriever:
    def __init__(self) -> None:
        self.brave_api_key = os.getenv("BRAVE_SEARCH_API_KEY")
        self.brave_api_url = "https://api.search.brave.com/res/v1/web/search"
        self.wikipedia_api_url = "https://en.wikipedia.org/w/api.php"

    async def retrieve(self, claim: str, top_k: int = 5) -> List[Evidence]:
        evidence: List[Evidence] = []

        web_results = await self._search_web(claim, top_k=min(3, top_k))
        evidence.extend(web_results)

        wiki_results = await self._search_wikipedia(
            claim,
            top_k=min(2, max(0, top_k - len(evidence))),
        )
        evidence.extend(wiki_results)

        ranked = self._rank_evidence(evidence)
        return ranked[:top_k]

    async def _search_web(self, claim: str, top_k: int = 3) -> List[Evidence]:
        if not self.brave_api_key:
            return [
                Evidence(
                    source_url=f"https://example.com/evidence/{i}",
                    snippet=f"Placeholder evidence for: {claim}",
                    relevance_score=0.8 - (i * 0.1),
                    publish_date=None,
                    credibility_score=0.6,
                )
                for i in range(top_k)
            ]

        if httpx is None:
            return [
                Evidence(
                    source_url=f"https://example.com/evidence/{i}",
                    snippet=f"Placeholder evidence for: {claim}",
                    relevance_score=0.7 - (i * 0.1),
                    publish_date=None,
                    credibility_score=0.5,
                )
                for i in range(top_k)
            ]

        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.brave_api_key,
        }
        params = {"q": claim, "count": max(1, top_k)}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(self.brave_api_url, headers=headers, params=params)
                r.raise_for_status()
                data = r.json()
        except httpx.HTTPError:
            return [
                Evidence(
                    source_url=f"https://example.com/evidence/{i}",
                    snippet=f"Placeholder evidence for: {claim}",
                    relevance_score=0.7 - (i * 0.1),
                    publish_date=None,
                    credibility_score=0.5,
                )
                for i in range(top_k)
            ]

        results: List[Evidence] = []
        for item in (data.get("web", {}).get("results", []) or [])[:top_k]:
            url = item.get("url") or ""
            snippet = (item.get("description") or "").strip()
            if not url or not snippet:
                continue
            results.append(
                Evidence(
                    source_url=url,
                    snippet=snippet,
                    relevance_score=0.75,
                    publish_date=item.get("age"),
                    credibility_score=0.7,
                )
            )
        return results

    async def _search_wikipedia(self, claim: str, top_k: int = 2) -> List[Evidence]:
        if top_k <= 0:
            return []

        if httpx is None:
            return []

        params = {
            "action": "query",
            "list": "search",
            "srsearch": claim,
            "format": "json",
            "utf8": 1,
            "srlimit": top_k,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(self.wikipedia_api_url, params=params)
                r.raise_for_status()
                data = r.json()
        except httpx.HTTPError:
            return []

        results: List[Evidence] = []
        for item in (data.get("query", {}).get("search", []) or [])[:top_k]:
            title = item.get("title")
            snippet = (item.get("snippet") or "").replace("<span class=\"searchmatch\">", "").replace("</span>", "")
            if not title or not snippet:
                continue
            url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
            results.append(
                Evidence(
                    source_url=url,
                    snippet=snippet,
                    relevance_score=0.65,
                    publish_date=None,
                    credibility_score=0.8,
                )
            )
        return results

    def _rank_evidence(self, evidence: List[Evidence]) -> List[Evidence]:
        for e in evidence:
            e.relevance_score = float(e.relevance_score) * float(e.credibility_score)
        return sorted(evidence, key=lambda e: e.relevance_score, reverse=True)
