"""
API endpoint for prompt enhancement with video script generation.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.tools.prompt_enhancement_tool import enhance_prompt_sync
from typing import List, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/prompt", tags=["Prompt Enhancement"])


class PromptEnhancementRequest(BaseModel):
    """Request model for prompt enhancement"""
    prompt: str = Field(
        description="User's original prompt to enhance",
        min_length=1,
        max_length=500
    )
    system_prompt: Optional[str] = Field(
        default=None,
        description="Custom system prompt (uses default if None)"
    )
    providers: Optional[List[str]] = Field(
        default=["gemini", "groq"],
        description="List of providers to try in order"
    )
    models: Optional[List[str]] = Field(
        default=None,
        description="List of models corresponding to providers"
    )
    max_retries: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Maximum retries per provider"
    )
    temperature: float = Field(
        default=0,
        ge=0,
        le=1,
        description="LLM temperature (0-1)"
    )


class Scene(BaseModel):
    """Video scene model"""
    title: str
    narration: str
    visuals: List[str]
    duration: int


class VideoScript(BaseModel):
    """Video script model"""
    scenes: List[Scene]


class Example(BaseModel):
    """Example model"""
    title: str
    input: Optional[str] = None
    steps: Optional[List[str]] = None
    explanation: Optional[str] = None


class PromptEnhancementResponse(BaseModel):
    """Response model for enhanced prompt"""
    enhanced_prompt: str = Field(description="Enhanced, detailed prompt")
    concept_name: str = Field(description="Clear name of the concept")
    target_audience: str = Field(description="Beginner/Intermediate/Advanced")
    learning_objectives: List[str] = Field(description="Specific learning goals")
    video_script: VideoScript = Field(description="Complete video script with scenes")
    example: Dict[str, Any] = Field(description="Concrete numerical example")
    suggested_visuals: List[str] = Field(description="Visual elements to animate")
    estimated_duration: int = Field(description="Estimated video duration in seconds (≤ 60)")
    original_prompt: str = Field(description="The original user prompt")
    provider_used: Optional[str] = Field(default=None, description="Provider that succeeded")
    model_used: Optional[str] = Field(default=None, description="Model that succeeded")


@router.post("/enhance", response_model=PromptEnhancementResponse)
async def enhance_prompt(request: PromptEnhancementRequest):
    """
    Enhance a user's educational prompt using AI with multiple model fallback.
    
    This endpoint takes a simple user prompt and returns an enhanced version
    with a concise video script (under 60 seconds), learning objectives,
    visual suggestions, and a concrete example.
    
    **Example Request:**
    ```json
    {
      "prompt": "explain the Fourier transform",
      "providers": ["gemini", "groq"],
      "max_retries": 2,
      "temperature": 0
    }
    ```
    
    **Example Response:**
    ```json
    {
      "enhanced_prompt": "Create a 60-second educational video...",
      "concept_name": "Fourier Transform",
      "target_audience": "Intermediate",
      "learning_objectives": ["Understand Fourier Transform as wave decomposition"],
      "video_script": {
        "scenes": [
          {
            "title": "Hook",
            "narration": "Ever wonder how music players...",
            "visuals": ["Music player equalizer"],
            "duration": 10
          }
        ]
      },
      "example": {
        "title": "Simple Wave Decomposition",
        "input": "f(t) = sin(t) + 0.5sin(3t)",
        "steps": ["Identify first component..."]
      },
      "suggested_visuals": ["Music equalizer bars", "Sine waves combining"],
      "estimated_duration": 60,
      "original_prompt": "explain the Fourier transform",
      "provider_used": "gemini",
      "model_used": "gemini-2.5-flash"
    }
    ```
    """
    try:
        logger.info(f"Enhancing prompt: {request.prompt}")
        
        result = enhance_prompt_sync(
            user_prompt=request.prompt,
            system_prompt=request.system_prompt,
            providers=request.providers,
            models=request.models,
            max_retries=request.max_retries,
            temperature=request.temperature
        )
        
        result["original_prompt"] = request.prompt
        
        logger.info(f"Successfully enhanced prompt for concept: {result.get('concept_name')}")
        
        return PromptEnhancementResponse(**result)
        
    except Exception as e:
        logger.error(f"Error enhancing prompt: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to enhance prompt: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """Health check for prompt enhancement service"""
    return {
        "status": "healthy",
        "service": "prompt_enhancement",
        "version": "2.0.0",
        "features": [
            "Multiple model fallback",
            "Customizable system prompts",
            "Concise video scripts (≤ 60s)",
            "Concrete numerical examples",
            "Retry logic with exponential backoff"
        ]
    }


@router.post("/test")
async def test_enhancement():
    """
    Test endpoint with a predefined prompt.
    
    Useful for quickly testing if the service is working.
    """
    test_request = PromptEnhancementRequest(
        prompt="explain quadratic equations"
    )
    return await enhance_prompt(test_request)
