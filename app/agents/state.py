"""
State schemas for LangGraph multi-agent system.
"""
from typing import TypedDict, Annotated, Sequence, Optional, List
from langchain_core.messages import BaseMessage
import operator


class SupervisorState(TypedDict):
    """State maintained by supervisor across all agents"""
    messages: Annotated[Sequence[BaseMessage], operator.add]
    user_query: str
    current_agent: Optional[str]  # "knowledge" | "execution" | "finish"
    script_artifacts: Optional[dict]  # Output from Agent 1
    execution_results: Optional[dict]  # Output from Agent 2
    next_action: str  # Routing decision


class KnowledgeAgentState(TypedDict):
    """State for Knowledge & Script Agent"""
    messages: Annotated[Sequence[BaseMessage], operator.add]
    query: str
    retrieved_context: List[str]
    web_search_results: List[dict]
    script_package: Optional[dict]
    is_complete: bool


class ExecutionAgentState(TypedDict):
    """State for Execution & Orchestration Agent"""
    messages: Annotated[Sequence[BaseMessage], operator.add]
    script_package: dict  # Input from Agent 1
    job_ids: List[str]
    rendered_scenes: List[str]
    final_video_path: Optional[str]
    is_complete: bool
