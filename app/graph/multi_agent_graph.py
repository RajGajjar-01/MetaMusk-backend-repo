"""
Multi-Agent Graph Orchestration using LangGraph.
Coordinates Knowledge Agent, Execution Agent, and Supervisor Agent.
"""
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage
from app.agents.supervisor_agent import create_supervisor_agent
from app.agents.knowledge_agent import create_knowledge_agent
from app.agents.execution_agent import create_execution_agent
from app.agents.state import SupervisorState


def create_multi_agent_graph():
    """
    Create the multi-agent orchestration graph.
    
    Flow:
    START → Supervisor → Knowledge Agent → Supervisor → Execution Agent → Supervisor → END
    """
    # Initialize agents
    supervisor = create_supervisor_agent()
    knowledge_agent = create_knowledge_agent()
    execution_agent = create_execution_agent()
    
    # Create graph with SupervisorState
    graph = StateGraph(SupervisorState)
    
    # Add nodes
    graph.add_node("supervisor", supervisor)
    graph.add_node("knowledge_agent", knowledge_agent)
    graph.add_node("execution_agent", execution_agent)
    
    # Define routing logic
    def route_supervisor(state: SupervisorState) -> str:
        """
        Route based on supervisor's decision.
        
        The supervisor uses structured outputs to determine next_action.
        """
        next_action = state.get("next_action", "")
        
        # CRITICAL FIX: Force finish if we have valid execution results with video
        execution_results = state.get("execution_results")
        if execution_results and isinstance(execution_results, dict):
            video_path = execution_results.get("final_video_path")
            local_path = execution_results.get("local_path")
            status = execution_results.get("status")
            actual_path = video_path or local_path
            
            # Check for completed status or valid path
            if status == "completed" and actual_path:
                return END
            if actual_path and actual_path != "None" and actual_path != "" and "mock" not in str(actual_path).lower():
                return END
        
        if next_action == "knowledge_agent":
            return "knowledge_agent"
        elif next_action == "execution_agent":
            return "execution_agent"
        elif next_action == "FINISH":
            return END
        else:
            # Continue supervisor loop if no clear decision
            return "supervisor"
    
    # Add edges
    graph.add_edge(START, "supervisor")
    
    # Conditional routing from supervisor
    graph.add_conditional_edges(
        "supervisor",
        route_supervisor,
        {
            "knowledge_agent": "knowledge_agent",
            "execution_agent": "execution_agent",
            END: END,
            "supervisor": "supervisor"
        }
    )
    
    # After agents complete, return to supervisor
    graph.add_edge("knowledge_agent", "supervisor")
    graph.add_edge("execution_agent", "supervisor")
    
    # Compile graph
    compiled_graph = graph.compile()
    
    return compiled_graph


def invoke_multi_agent_system(user_query: str, user_id: str = "default"):
    """
    Invoke the multi-agent system with a user query.
    
    Args:
        user_query: The educational concept to explain
        user_id: User identifier for tracking
        
    Returns:
        Final state with execution results
    """
    graph = create_multi_agent_graph()
    
    # Initial state
    initial_state = {
        "messages": [HumanMessage(content=user_query)],
        "user_query": user_query,
        "current_agent": None,
        "script_artifacts": None,
        "execution_results": None,
        "next_action": ""
    }
    
    # Invoke graph
    result = graph.invoke(initial_state)
    
    return result


if __name__ == "__main__":
    # Test the graph
    print("Creating multi-agent graph...")
    graph = create_multi_agent_graph()
    print("Multi-agent graph created successfully!")
    
    # Visualize graph (optional)
    try:
        from IPython.display import Image, display
        display(Image(graph.get_graph().draw_mermaid_png()))
    except:
        print("Graph visualization requires IPython and graphviz")
