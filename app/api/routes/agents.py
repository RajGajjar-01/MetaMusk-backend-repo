"""
FastAPI routes for multi-agent video generation system.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.graph.multi_agent_graph import invoke_multi_agent_system
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["Multi-Agent System"])


class VideoGenerationRequest(BaseModel):
    """Request model for video generation"""
    concept: str = Field(description="Educational concept to explain")
    user_id: str = Field(default="default", description="User identifier")
    options: Optional[Dict] = Field(default_factory=dict, description="Additional options")


class VideoGenerationResponse(BaseModel):
    """Response model for video generation"""
    status: str = Field(description="Status of the request")
    video_path: Optional[str] = Field(description="Path to generated video")
    script_package: Optional[Dict] = Field(description="Generated script package")
    execution_metadata: Optional[Dict] = Field(description="Execution metadata")
    errors: List[str] = Field(default_factory=list, description="Any errors encountered")


@router.post("/generate-video", response_model=VideoGenerationResponse)
async def generate_video(request: VideoGenerationRequest):
    """
    Generate educational video using multi-agent system.
    
    This endpoint:
    1. Routes request to Supervisor Agent
    2. Supervisor coordinates Knowledge Agent (script generation)
    3. Supervisor coordinates Execution Agent (rendering)
    4. Returns final video path and metadata
    """
    try:
        logger.info(f"Generating video for concept: {request.concept}")
        
        # Invoke multi-agent system
        result = invoke_multi_agent_system(
            user_query=request.concept,
            user_id=request.user_id
        )
        
        # Extract results
        execution_results = result.get("execution_results", {})
        script_artifacts = result.get("script_artifacts", {})
        
        # Ensure errors are strings
        raw_errors = execution_results.get("errors", [])
        clean_errors = [str(err) if not isinstance(err, str) else err for err in raw_errors]

        return VideoGenerationResponse(
            status="success",
            video_path=execution_results.get("final_video_path"),
            script_package=script_artifacts,
            execution_metadata=execution_results.get("execution_metadata", {}),
            errors=clean_errors
        )
        
    except Exception as e:
        logger.error(f"Error generating video: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate video: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """Health check endpoint for multi-agent system"""
    return {
        "status": "healthy",
        "agents": ["supervisor", "knowledge", "execution"],
        "version": "1.0.0"
    }


@router.get("/stats")
async def get_stats():
    """Get usage statistics for multi-agent system"""
    # TODO: Implement actual stats tracking
    return {
        "total_videos_generated": 0,
        "avg_generation_time_seconds": 0,
        "success_rate": 0.0
    }
