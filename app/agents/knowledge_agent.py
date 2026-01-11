"""
Knowledge & Script Agent implementation using langgraph prebuilt create_react_agent.
Uses prompt_enhancement_tool, web_search_tool, and script_generator_tool.
"""
from pathlib import Path
from langgraph.prebuilt import create_react_agent
from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage
from app.tools import (
    prompt_enhancement_tool,
    web_search_tool,
    script_generator_tool,
)
import json
import logging

logger = logging.getLogger(__name__)


def load_prompt(filename: str) -> str:
    """Load prompt from prompts directory"""
    prompt_path = Path(__file__).parent.parent / "prompts" / filename
    return prompt_path.read_text()


def create_knowledge_agent():
    """
    Create Knowledge & Script Agent using langgraph's create_react_agent.
    Returns the agent graph that can be invoked with state.
    """
    logger.info("🧠 Creating Knowledge Agent...")
    
    # Initialize LLM
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.3
    )
    logger.debug("LLM initialized: gemini-2.5-flash")
    
    # Define tools
    tools = [
        prompt_enhancement_tool,
        web_search_tool,
        script_generator_tool,
    ]
    logger.debug(f"Tools loaded: {[t.name for t in tools]}")
    
    # Load system prompt
    system_prompt = load_prompt("knowledge_agent.txt")
    system_prompt += "\n\nCRITICAL: You MUST return the final result as a VALID JSON OBJECT matching the ScriptPackage schema."
    logger.debug("System prompt loaded")
    
    # Create agent using langchain's create_agent
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt
    )
    logger.info("✅ Knowledge Agent created successfully")
    
    # Wrap to handle state mapping for the multi-agent graph
    def knowledge_node(state):
        logger.info("📚 Knowledge Agent invoked")
        logger.debug(f"Input state keys: {list(state.keys())}")
        
        try:
            # Invoke the agent
            logger.debug("Invoking agent...")
            result = agent.invoke(state)
            logger.debug(f"Agent returned result with keys: {list(result.keys())}")
            
            # Extract the last AI message content
            messages = result.get("messages", [])
            logger.debug(f"Message count: {len(messages)}")
            
            output_str = ""
            for msg in reversed(messages):
                if hasattr(msg, "content") and msg.content:
                    if isinstance(msg.content, list):
                        # Handle list content (e.g. from multimodal models)
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
            
            logger.debug(f"Output string length: {len(output_str)}")
            
            # Try to parse JSON output
            script_artifacts = {}
            try:
                clean_output = output_str.strip()
                if "```json" in clean_output:
                    clean_output = clean_output.split("```json")[1].split("```")[0]
                elif "```" in clean_output:
                    clean_output = clean_output.split("```")[1].split("```")[0]
                
                # Fix common JSON errors - handle invalid escape sequences
                import re
                # Fix invalid escape sequences like \n, \t, \r that aren't properly escaped
                # This regex finds backslashes not followed by valid JSON escape chars
                def fix_escapes(s):
                    # First, try parsing as-is
                    try:
                        json.loads(s)
                        return s
                    except json.JSONDecodeError:
                        pass
                    # Replace problematic escapes
                    s = s.replace("\\'", "'")  # Fix single quote escape
                    # Handle unescaped backslashes in strings (common in LaTeX)
                    # Replace single backslashes with double (except for valid JSON escapes)
                    # Valid JSON escapes: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
                    return s
                
                clean_output = fix_escapes(clean_output)
                
                parsed = json.loads(clean_output)
                logger.info("✅ Successfully parsed JSON output")
                logger.debug(f"Parsed keys: {list(parsed.keys()) if isinstance(parsed, dict) else 'not a dict'}")
                
                # NORMALIZE STRUCTURE: Ensure scenes are at top level
                if isinstance(parsed, dict):
                    # Check for scenes in various locations
                    scenes = []
                    if "scenes" in parsed:
                        scenes = parsed["scenes"]
                        logger.debug(f"Found {len(scenes)} scenes at top level")
                    elif "video_script" in parsed and isinstance(parsed["video_script"], dict):
                        scenes = parsed["video_script"].get("scenes", [])
                        logger.debug(f"Found {len(scenes)} scenes in video_script")
                    
                    # Rebuild normalized structure
                    script_artifacts = {
                        "concept_name": parsed.get("concept_name", parsed.get("enhanced_prompt", "Unknown")),
                        "learning_objectives": parsed.get("learning_objectives", []),
                        "scenes": scenes,  # Always at top level now
                        "estimated_duration": parsed.get("estimated_duration", 30),
                        "raw_parsed": parsed  # Keep original for debugging
                    }
                    logger.info(f"📦 Normalized script_artifacts with {len(scenes)} scenes")
                else:
                    script_artifacts = {"raw_output": output_str}
                    
            except Exception as parse_error:
                logger.warning(f"⚠️ JSON parse failed: {parse_error}")
                logger.debug(f"Raw output (first 500 chars): {output_str[:500]}")
                script_artifacts = {"raw_output": output_str}
                
            logger.info("📚 Knowledge Agent completed")
            
            # CRITICAL FIX: Only update script_artifacts if we have valid scenes
            # Don't overwrite good artifacts with failed parses
            existing_artifacts = state.get("script_artifacts", {})
            existing_scenes = []
            if isinstance(existing_artifacts, dict):
                existing_scenes = existing_artifacts.get("scenes", [])
            
            new_scenes = script_artifacts.get("scenes", [])
            
            if len(new_scenes) == 0 and len(existing_scenes) > 0:
                logger.warning(f"⚠️ New parse has 0 scenes but existing has {len(existing_scenes)}, keeping existing artifacts")
                return {
                    "messages": [AIMessage(content=output_str)],
                    "script_artifacts": existing_artifacts  # Keep existing valid artifacts
                }
            
            return {
                "messages": [AIMessage(content=output_str)],
                "script_artifacts": script_artifacts
            }
        except Exception as e:
            logger.error(f"❌ Knowledge Agent error: {e}", exc_info=True)
            raise
    
    return knowledge_node


if __name__ == "__main__":
    agent = create_knowledge_agent()
    print("Knowledge Agent created successfully!")
    print("Tools available:")
    print("  1. prompt_enhancement_tool - Enhance user prompts")
    print("  2. web_search_tool - Search for information")
    print("  3. script_generator_tool - Generate Manim code")
