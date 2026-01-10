from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from hallushield import HalluShieldPipeline
from hallushield.types import VerifyRequest, VerifyResponse

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

@app.get("/")
def read_root():
    return {"message": "Hello World"}

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

_default_pipeline = HalluShieldPipeline()

@app.post("/verify", response_model=VerifyResponse)
async def verify(req: VerifyRequest):
    pipeline = _default_pipeline
    if req.llm_provider or req.llm_model:
        pipeline = HalluShieldPipeline(llm_provider=req.llm_provider, llm_model=req.llm_model)
    result = await pipeline.verify(query=req.query, user_id=req.user_id)
    final_answer = result.get("final_answer", {})

    return VerifyResponse(
        verified_answer=final_answer.get("verified_answer", ""),
        original_answer=final_answer.get("original_answer", ""),
        modifications=final_answer.get("modifications", []),
        hallucination_score=float(final_answer.get("hallucination_score", 0.0)),
        confidence=float(final_answer.get("confidence", 0.0)),
        claim_breakdown=final_answer.get("claim_breakdown", {}),
        decisions=result.get("decisions", []),
        claims=result.get("claims", []),
        errors=result.get("errors", []),
    )

@app.get("/stats")
async def get_stats():
    """
    Get HalluShield usage statistics including:
    - SLM/LLM call counts
    - Escalation rate
    - Total cost and cost savings
    """
    pipeline = _default_pipeline
    
    # Get stats from model router if available
    if hasattr(pipeline, "model_router"):
        return pipeline.model_router.get_stats()
    else:
        return {
            "message": "No statistics available yet. Make some /verify requests first.",
            "slm_calls": 0,
            "llm_calls": 0,
            "total_calls": 0,
            "escalations": 0,
            "escalation_rate": 0.0,
            "total_cost": 0.0,
            "cost_saved": 0.0,
            "avg_cost_per_query": 0.0,
        }

