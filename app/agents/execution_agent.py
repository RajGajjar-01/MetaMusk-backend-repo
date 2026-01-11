"""
Execution & Orchestration Agent implementation using langchain create_agent.
Handles rendering of Manim scripts on VM infrastructure.
"""
from pathlib import Path
from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage, HumanMessage
from app.tools import (
    vm_executor_tool,
    job_status_tool,
    aggregator_tool,
    assembler_tool,
    full_video_executor_tool
)
import json
import logging

logger = logging.getLogger(__name__)


def load_prompt(filename: str) -> str:
    """Load prompt from prompts directory"""
    prompt_path = Path(__file__).parent.parent / "prompts" / filename
    return prompt_path.read_text()


def create_execution_agent():
    """
    Create Execution & Orchestration Agent using langgraph's create_react_agent.
    """
    logger.info("⚙️ Creating Execution Agent...")
    
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.1
    )
    logger.debug("LLM initialized")
    
    tools = [
        vm_executor_tool,
        job_status_tool,
        aggregator_tool,
        assembler_tool,
        full_video_executor_tool,
    ]
    logger.debug(f"Tools loaded: {[t.name for t in tools]}")
    
    system_prompt = load_prompt("execution_agent.txt")
    system_prompt += "\n\nCRITICAL: Return final result as VALID JSON corresponding to ExecutionResult."
    
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt
    )
    logger.info("✅ Execution Agent created successfully")
    
    def execution_node(state):
        """
        Execution node that injects script artifacts into LLM context.
        """
        logger.info("🎬 Execution Agent invoked")
        logger.debug(f"Input state keys: {list(state.keys())}")
        
        # Extract script artifacts from state
        script_artifacts = state.get("script_artifacts", {})
        
        # Build context message with scripts to execute
        context_parts = []
        context_parts.append("[EXECUTION CONTEXT - SCRIPT PACKAGE]")
        
        scenes = []
        if script_artifacts:
            # Handle multiple possible structures
            if isinstance(script_artifacts, dict):
                # Try different paths to find scenes
                if "scenes" in script_artifacts:
                    scenes = script_artifacts["scenes"]
                    logger.debug(f"Found scenes at top level: {len(scenes)}")
                elif "video_script" in script_artifacts:
                    scenes = script_artifacts.get("video_script", {}).get("scenes", [])
                    logger.debug(f"Found scenes in video_script: {len(scenes)}")
                elif "raw_parsed" in script_artifacts:
                    raw = script_artifacts.get("raw_parsed", {})
                    if "scenes" in raw:
                        scenes = raw["scenes"]
                    elif "video_script" in raw:
                        scenes = raw.get("video_script", {}).get("scenes", [])
                    logger.debug(f"Found scenes in raw_parsed: {len(scenes)}")
            
            context_parts.append(f"Found {len(scenes)} scenes to render.")
            context_parts.append("")
            
            # Build the scenes array for full_video_executor_tool
            scenes_for_tool = []
            for i, scene in enumerate(scenes):
                scene_id = scene.get("scene_id", scene.get("title", f"Scene{i+1}"))
                code = scene.get("manim_code", "")
                
                if code:
                    scenes_for_tool.append({
                        "scene_id": scene_id,
                        "manim_code": code
                    })
                    context_parts.append(f"Scene {i+1}: {scene_id} ({len(code)} chars)")
                else:
                    context_parts.append(f"Scene {i+1}: {scene_id} - ⚠️ NO CODE")
            
            context_parts.append("")
            context_parts.append("=" * 50)
            context_parts.append("INSTRUCTION: Call full_video_executor_tool with these scenes:")
            context_parts.append("=" * 50)
            context_parts.append("")
            context_parts.append("```python")
            context_parts.append("full_video_executor_tool(scenes=[")
            for s in scenes_for_tool:
                # Escape the code for display
                code_preview = s["manim_code"][:100].replace("\n", "\\n") + "..."
                context_parts.append(f'    {{"scene_id": "{s["scene_id"]}", "manim_code": "{code_preview}"}},')
            context_parts.append("])")
            context_parts.append("```")
            context_parts.append("")
            context_parts.append("FULL SCENE CODE FOR REFERENCE:")
            context_parts.append("")
            
            for i, scene in enumerate(scenes):
                scene_id = scene.get("scene_id", scene.get("title", f"Scene{i+1}"))
                code = scene.get("manim_code", "")
                context_parts.append(f"### SCENE {i+1}: {scene_id}")
                context_parts.append("```python")
                context_parts.append(code if code else "# NO CODE AVAILABLE")
                context_parts.append("```")
                context_parts.append("")
        else:
            context_parts.append("❌ NO SCRIPT ARTIFACTS FOUND IN STATE")
            context_parts.append("Error: Cannot proceed without scripts.")
        
        context_message = "\n".join(context_parts)
        
        # Inject context into messages
        messages = list(state.get("messages", []))
        messages.append(HumanMessage(content=context_message))
        
        logger.info(f"Injecting script context ({len(context_message)} chars) into Execution Agent")
        
        try:
            # Invoke agent with modified state (but don't modify original state in graph yet)
            modified_state = {**state, "messages": messages}
            
            result = agent.invoke(modified_state)
            logger.debug(f"Agent returned with keys: {list(result.keys())}")
            
            result_messages = result.get("messages", [])
            output_str = ""
            for msg in reversed(result_messages):
                if hasattr(msg, "content") and msg.content:
                    if isinstance(msg.content, list):
                        # Handle list content
                        text_parts = []
                        for part in msg.content:
                            if isinstance(part, dict) and "text" in part:
                                text_parts.append(part["text"])
                            elif isinstance(part, str):
                                text_parts.append(part)
                        output_str = "\n".join(text_parts)
                    else:
                        output_str = str(msg.content)
                    break
            
            execution_results = {}
            try:
                clean_output = output_str.strip()
                if "```json" in clean_output:
                    clean_output = clean_output.split("```json")[1].split("```")[0]
                elif "```" in clean_output:
                    clean_output = clean_output.split("```")[1].split("```")[0]
                
                # Fix common JSON errors
                clean_output = clean_output.replace("\\'", "'")  # Fix invalid single quote escape
                
                execution_results = json.loads(clean_output)
                logger.info("✅ Parsed execution results JSON")
            except Exception as e:
                logger.warning(f"⚠️ JSON parse failed: {e}")
                execution_results = {"raw_output": output_str}

            logger.info("🎬 Execution Agent completed")
            return {
                "messages": [AIMessage(content=output_str)],
                "execution_results": execution_results
            }
        except Exception as e:
            logger.error(f"❌ Execution Agent error: {e}", exc_info=True)
            raise
    
    return execution_node


if __name__ == "__main__":
    agent = create_execution_agent()
    print("Execution Agent created successfully!")
