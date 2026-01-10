"""
Test examples for HalluShield AI
Run these after starting the server with: uvicorn main:app --reload
"""

import httpx
import asyncio
import json


async def test_simple_query():
    """Test a simple factual query - should use SLM only"""
    print("\n" + "="*60)
    print("TEST 1: Simple Factual Query (SLM)")
    print("="*60)
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/verify",
            json={"query": "What is the capital of France?"},
            timeout=30.0
        )
        
        result = response.json()
        print(f"\nQuery: What is the capital of France?")
        print(f"Original Answer: {result['original_answer']}")
        print(f"Verified Answer: {result['verified_answer']}")
        print(f"Hallucination Score: {result['hallucination_score']}")
        print(f"Confidence: {result['confidence']}")
        print(f"Claims: {result['claim_breakdown']}")


async def test_complex_query():
    """Test a complex query - may escalate to LLM"""
    print("\n" + "="*60)
    print("TEST 2: Complex Query (May Escalate)")
    print("="*60)
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/verify",
            json={"query": "Explain quantum entanglement and its implications for quantum computing in detail."},
            timeout=60.0
        )
        
        result = response.json()
        print(f"\nQuery: Explain quantum entanglement...")
        print(f"Hallucination Score: {result['hallucination_score']}")
        print(f"Confidence: {result['confidence']}")
        print(f"Claims: {result['claim_breakdown']}")
        print(f"Modifications: {len(result['modifications'])} corrections made")


async def test_hallucination_prone():
    """Test a query prone to hallucination"""
    print("\n" + "="*60)
    print("TEST 3: Hallucination-Prone Query")
    print("="*60)
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/verify",
            json={"query": "What was the population of Tokyo in 2024?"},
            timeout=30.0
        )
        
        result = response.json()
        print(f"\nQuery: What was the population of Tokyo in 2024?")
        print(f"Original Answer: {result['original_answer'][:200]}...")
        print(f"Verified Answer: {result['verified_answer'][:200]}...")
        print(f"Hallucination Score: {result['hallucination_score']}")
        print(f"Modifications: {result['modifications']}")


async def test_stats():
    """Test the stats endpoint"""
    print("\n" + "="*60)
    print("TEST 4: Statistics Endpoint")
    print("="*60)
    
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8000/stats")
        stats = response.json()
        
        print(f"\nUsage Statistics:")
        print(f"  SLM Calls: {stats.get('slm_calls', 0)}")
        print(f"  LLM Calls: {stats.get('llm_calls', 0)}")
        print(f"  Total Calls: {stats.get('total_calls', 0)}")
        print(f"  Escalations: {stats.get('escalations', 0)}")
        print(f"  Escalation Rate: {stats.get('escalation_rate', 0):.1%}")
        print(f"  Total Cost: ${stats.get('total_cost', 0):.4f}")
        print(f"  Cost Saved: ${stats.get('cost_saved', 0):.4f}")
        print(f"  Avg Cost/Query: ${stats.get('avg_cost_per_query', 0):.4f}")


async def main():
    """Run all tests"""
    print("\n🛡️  HalluShield AI - Test Suite")
    print("Make sure the server is running: uvicorn main:app --reload\n")
    
    try:
        # Test 1: Simple query
        await test_simple_query()
        
        # Test 2: Complex query
        await test_complex_query()
        
        # Test 3: Hallucination-prone
        await test_hallucination_prone()
        
        # Test 4: Stats
        await test_stats()
        
        print("\n" + "="*60)
        print("✅ All tests completed!")
        print("="*60 + "\n")
        
    except httpx.ConnectError:
        print("\n❌ Error: Could not connect to server.")
        print("Please start the server first:")
        print("  uvicorn main:app --reload\n")
    except Exception as e:
        print(f"\n❌ Error: {e}\n")


if __name__ == "__main__":
    asyncio.run(main())
