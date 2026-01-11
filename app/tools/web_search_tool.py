"""
Web search tool for supplementary information using Tavily Search API.
Provides real-time web search capabilities for the Knowledge Agent.
"""
from langchain_core.tools import tool
from typing import List, Dict, Optional
import os
import logging
import httpx

logger = logging.getLogger(__name__)


def get_tavily_api_key() -> Optional[str]:
    """Get Tavily API key from environment."""
    return os.getenv("TAVILY_API_KEY")


async def search_with_tavily(query: str, num_results: int = 5) -> List[Dict]:
    """
    Perform web search using Tavily Search API.
    
    Args:
        query: Search query
        num_results: Number of results to return
        
    Returns:
        List of search results
    """
    api_key = get_tavily_api_key()
    
    if not api_key:
        logger.warning("TAVILY_API_KEY not found, using mock data")
        return get_mock_results(query, num_results)
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": query,
                    "search_depth": "advanced",
                    "include_answer": True,
                    "include_raw_content": False,
                    "max_results": num_results,
                    "include_domains": [],
                    "exclude_domains": []
                }
            )
            response.raise_for_status()
            data = response.json()
            
            results = []
            
            # Include the AI-generated answer if available
            if data.get("answer"):
                results.append({
                    "title": "AI Summary",
                    "snippet": data["answer"],
                    "url": "tavily-answer",
                    "score": 1.0
                })
            
            # Include search results
            for result in data.get("results", [])[:num_results]:
                results.append({
                    "title": result.get("title", ""),
                    "snippet": result.get("content", ""),
                    "url": result.get("url", ""),
                    "score": result.get("score", 0.0)
                })
            
            logger.info(f"Tavily search returned {len(results)} results for: {query}")
            return results
            
    except httpx.HTTPStatusError as e:
        logger.error(f"Tavily API error: {e.response.status_code} - {e.response.text}")
        return get_mock_results(query, num_results)
    except Exception as e:
        logger.error(f"Web search error: {e}")
        return get_mock_results(query, num_results)


def get_mock_results(query: str, num_results: int = 3) -> List[Dict]:
    """Return mock search results when API is unavailable."""
    return [
        {
            "title": f"Understanding {query}",
            "snippet": f"Comprehensive guide to {query} with examples and visualizations. "
                      f"This resource covers the fundamental concepts and practical applications.",
            "url": f"https://example.com/{query.replace(' ', '-')}",
            "score": 0.95
        },
        {
            "title": f"{query} - Khan Academy",
            "snippet": f"Learn {query} through interactive exercises and video lessons. "
                      f"Free educational content with step-by-step explanations.",
            "url": f"https://khanacademy.org/math/{query.replace(' ', '-')}",
            "score": 0.90
        },
        {
            "title": f"{query} Explained Simply",
            "snippet": f"Step-by-step explanation of {query} with real-world applications. "
                      f"Perfect for beginners and intermediate learners.",
            "url": f"https://mathworld.wolfram.com/{query.replace(' ', '')}",
            "score": 0.85
        },
        {
            "title": f"Visual Guide to {query}",
            "snippet": f"Interactive visualizations and animations explaining {query}. "
                      f"See the concepts come to life with dynamic graphics.",
            "url": f"https://brilliant.org/wiki/{query.replace(' ', '-')}",
            "score": 0.80
        },
        {
            "title": f"{query} - 3Blue1Brown Style",
            "snippet": f"Deep intuitive explanation of {query} using visual mathematics. "
                      f"Focus on building genuine understanding rather than memorization.",
            "url": f"https://3blue1brown.com/topics/{query.replace(' ', '-')}",
            "score": 0.75
        }
    ][:num_results]


def search_sync(query: str, num_results: int = 5) -> List[Dict]:
    """
    Synchronous version of web search.
    
    Args:
        query: Search query
        num_results: Number of results
        
    Returns:
        List of search results
    """
    api_key = get_tavily_api_key()
    
    if not api_key:
        logger.warning("TAVILY_API_KEY not found, using mock data")
        return get_mock_results(query, num_results)
    
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": query,
                    "search_depth": "advanced",
                    "include_answer": True,
                    "include_raw_content": False,
                    "max_results": num_results
                }
            )
            response.raise_for_status()
            data = response.json()
            
            results = []
            
            if data.get("answer"):
                results.append({
                    "title": "AI Summary",
                    "snippet": data["answer"],
                    "url": "tavily-answer",
                    "score": 1.0
                })
            
            for result in data.get("results", [])[:num_results]:
                results.append({
                    "title": result.get("title", ""),
                    "snippet": result.get("content", ""),
                    "url": result.get("url", ""),
                    "score": result.get("score", 0.0)
                })
            
            return results
            
    except Exception as e:
        logger.error(f"Sync web search error: {e}")
        return get_mock_results(query, num_results)


@tool
def web_search_tool(query: str, num_results: int = 5) -> List[Dict]:
    """
    Search the web for supplementary information about educational concepts.
    
    Use this tool when you need:
    - Real-time information about mathematical concepts
    - Examples and visualizations from educational sources
    - Supplementary context for generating better content
    - High-level intuition and explanations
    
    Args:
        query: Search query (e.g., "Fourier transform intuition", "derivative visualization")
        num_results: Number of results to return (default: 5)
        
    Returns:
        List of search results with title, snippet, url, and relevance score
    """
    return search_sync(query, num_results)


# For async usage in agents
async def web_search_async(query: str, num_results: int = 5) -> List[Dict]:
    """Async version of web search for use in async agents."""
    return await search_with_tavily(query, num_results)
