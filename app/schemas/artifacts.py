"""
Artifact schemas for multi-agent system.
Uses Pydantic for structured outputs.
"""
from pydantic import BaseModel, Field
from typing import List, Optional


class Scene(BaseModel):
    """Individual animation scene with structured output"""
    scene_id: str = Field(description="Unique identifier for the scene")
    explanation_goal: str = Field(description="What this scene teaches")
    visual_elements: List[str] = Field(description="List of animations/objects to display")
    narration_script: str = Field(description="Voice-over text for the scene")
    manim_code: str = Field(description="Complete Manim Python code for this scene")
    duration_estimate: float = Field(description="Estimated duration in seconds")


class ScriptPackage(BaseModel):
    """Output artifact from Knowledge Agent - enforces structured output"""
    concept_name: str = Field(description="Clear name of the educational concept")
    learning_objectives: List[str] = Field(description="What the viewer will learn")
    retrieved_context: List[str] = Field(
        description="Sources and references used",
        default_factory=list
    )
    scenes: List[Scene] = Field(description="Array of scene objects")
    metadata: dict = Field(
        description="Additional metadata (difficulty, total duration, etc.)",
        default_factory=dict
    )


class ExecutionResult(BaseModel):
    """Output artifact from Execution Agent - enforces structured output"""
    rendered_scenes: List[str] = Field(description="List of rendered scene file paths")
    final_video_path: str = Field(description="Path to the assembled final video")
    execution_metadata: dict = Field(
        description="Execution details (VM info, timings, etc.)",
        default_factory=dict
    )
    timings: dict = Field(
        description="Timing information for each stage",
        default_factory=dict
    )
    errors: List[str] = Field(
        description="List of any errors encountered",
        default_factory=list
    )


class SupervisorDecision(BaseModel):
    """Structured output for supervisor routing decisions"""
    next_action: str = Field(
        description="Next action to take: 'knowledge_agent', 'execution_agent', or 'FINISH'"
    )
    reasoning: str = Field(description="Explanation for the routing decision")
    context_to_pass: dict = Field(
        description="Relevant context to pass to the next agent",
        default_factory=dict
    )
