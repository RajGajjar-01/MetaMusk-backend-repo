"""
Prompt enhancement tool using LLM to improve user prompts with multiple model fallback.
"""
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from typing import Dict, Optional, List, Any
from dotenv import load_dotenv
import os
import json
import time
import logging

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Disable LangSmith tracing to prevent errors
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGCHAIN_API_KEY"] = ""


def get_api_key(provider: str) -> Optional[str]:
    """Get API key for a given provider."""
    if provider == "gemini":
        return os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    elif provider == "groq":
        return os.getenv("GROQ_API_KEY")
    return None


def get_llm_model(provider: str, model: Optional[str] = None, temperature: float = 0):
    """Initialize LLM based on provider."""
    api_key = get_api_key(provider)
    
    if not api_key:
        logger.warning(f"API key not found for {provider}")
        return None
    
    try:
        if provider == "gemini":
            model_name = model or "gemini-2.5-flash"
            return ChatGoogleGenerativeAI(model=model_name, temperature=temperature)
        elif provider == "groq":
            model_name = model or "llama-3.3-70b-versatile"
            return ChatGroq(model=model_name, temperature=temperature)
    except Exception as e:
        logger.error(f"Failed to initialize {provider} model: {e}")
        return None
    
    return None


DEFAULT_SYSTEM_PROMPT = """You are an expert prompt engineer and educational content creator specializing in creating concise video scripts for mathematical and educational concepts under 30 seconds.

Your task is to take a user's simple prompt about a mathematical or educational concept and create a concise video script (under 30 seconds) that includes:
1. **Concise Video Script**: A step-by-step narration script that can be used to create educational videos
2. **Learning Objectives**: Clear learning goals for the short video
3. **Visual Elements**: Specific visual elements to animate
4. **Concrete Example**: One clear, simple numerical example

## Script Guidelines:

- Keep narration concise (approx. 60-80 words total)
- Start with a 5-second hook/attention grabber
- Include 1 clear, simple numerical example with step-by-step explanation
- Total video must be under 30 seconds
- Break into 3-4 short scenes (7-8 seconds each)
- End with a quick summary or key takeaway
- Focus on ONE core idea (don't try to cover everything)

## Output Format:

Return a JSON object with:
- `enhanced_prompt`: The improved, detailed prompt
- `concept_name`: Clear name of the concept
- `target_audience`: Beginner/Intermediate/Advanced
- `learning_objectives`: List of 1-3 specific learning goals
- `video_script`: Complete video script with scenes
  - `scenes`: Array of scene objects with `title`, `narration`, `visuals`, `duration`
- `example`: One concrete numerical example with step-by-step explanation
- `suggested_visuals`: List of visual elements to animate
- `estimated_duration`: Total video duration in seconds (must be ≤ 30)

## Example:

Input: "explain Fourier transform"

Output:
{{
  "enhanced_prompt": "Create a 30-second educational video explaining the Fourier Transform. Focus on the core intuition: breaking complex waves into simple sine waves. Use one simple numerical example.",
  "concept_name": "Fourier Transform",
  "target_audience": "Intermediate",
  "learning_objectives": [
    "Understand Fourier Transform as wave decomposition",
    "See a simple numerical example"
  ],
  "video_script": {{
    "scenes": [
      {{
        "title": "Hook",
        "narration": "Ever wonder how music players show those frequency bars? That's Fourier Transform!",
        "visuals": ["Music player equalizer animation"],
        "duration": 7
      }},
      {{
        "title": "Core Idea",
        "narration": "Any complex wave is made of simple sine waves. Each wave has its own frequency and strength.",
        "visuals": ["Complex wave decomposing into 3 sine waves"],
        "duration": 8
      }},
      {{
        "title": "Example",
        "narration": "Take f(t) = sin(t) + 0.5sin(3t). The transform shows two peaks - frequency 1 with strength 1, and frequency 3 with strength 0.5.",
        "visuals": ["Two sine waves combining", "Frequency graph showing two bars"],
        "duration": 10
      }},
      {{
        "title": "Summary",
        "narration": "Fourier Transform converts time signals to frequency components. It's everywhere!",
        "visuals": ["Quick icons: music, photo, atom"],
        "duration": 5
      }}
    ]
  }},
  "example": {{
    "title": "Simple Wave Decomposition",
    "input": "f(t) = sin(t) + 0.5sin(3t)",
    "steps": [
      "Identify first component: sin(t) with frequency 1, amplitude 1",
      "Identify second component: 0.5sin(3t) with frequency 3, amplitude 0.5",
      "Fourier transform shows: peak at ω=1 with height 1, peak at ω=3 with height 0.5"
    ]
  }},
  "suggested_visuals": [
    "Music equalizer bars",
    "Sine waves combining",
    "Frequency domain bar chart"
  ],
  "estimated_duration": 30
}}

Now enhance the user's prompt following these guidelines. Keep it under 30 seconds!"""


def enhance_prompt_with_retry(
    user_prompt: str,
    system_prompt: Optional[str] = None,
    providers: Optional[List[str]] = None,
    models: Optional[List[str]] = None,
    max_retries: int = 3,
    temperature: float = 0
) -> Dict:
    """
    Enhance a user's prompt with multiple model fallback and retry logic.
    
    Args:
        user_prompt: The user's original prompt/query
        system_prompt: Custom system prompt (uses default if None)
        providers: List of providers to try in order (default: ["gemini", "groq"])
        models: List of models corresponding to providers (None = use defaults)
        max_retries: Maximum retries per provider
        temperature: LLM temperature
        
    Returns:
        Dict containing enhanced prompt and metadata
    """
    if providers is None:
        providers = ["gemini", "groq"]
    
    if system_prompt is None:
        system_prompt = DEFAULT_SYSTEM_PROMPT
    
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "User prompt: {user_prompt}\n\nEnhance this prompt following the guidelines above. Return ONLY the JSON object, no other text.")
    ])
    
    last_error = None
    
    for provider_idx, provider in enumerate(providers):
        model = models[provider_idx] if models and provider_idx < len(models) else None
        llm = get_llm_model(provider, model, temperature)
        
        if not llm:
            logger.warning(f"Skipping {provider}: API key not available")
            continue
        
        for retry in range(max_retries):
            try:
                logger.info(f"Trying {provider} (attempt {retry + 1}/{max_retries})")
                
                chain = prompt_template | llm
                response = chain.invoke({"user_prompt": user_prompt})
                content = response.content
                
                result = parse_enhancement_response(content)
                result["provider_used"] = provider
                result["model_used"] = getattr(llm, 'model_name', 'unknown')
                result["retries"] = retry
                
                logger.info(f"Successfully enhanced prompt using {provider}")
                return result
                
            except Exception as e:
                last_error = e
                logger.error(f"Error with {provider} (attempt {retry + 1}): {e}")
                if retry < max_retries - 1:
                    wait_time = (2 ** retry) * 1
                    logger.info(f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
    
    logger.error(f"All providers failed. Last error: {last_error}")
    return get_fallback_response(user_prompt, str(last_error) if last_error else "Unknown error")


def parse_enhancement_response(content: Any) -> Dict:
    """Parse the LLM response and extract JSON."""
    try:
        content_str = str(content)
        
        if "```json" in content_str:
            json_start = content_str.find("```json") + 7
            json_end = content_str.find("```", json_start)
            json_str = content_str[json_start:json_end].strip()
        elif "{" in content_str and "}" in content_str:
            json_start = content_str.find("{")
            json_end = content_str.rfind("}") + 1
            json_str = content_str[json_start:json_end]
        else:
            return get_fallback_response(content_str, "No JSON found in response")
        
        result = json.loads(json_str)
        
        required_fields = [
            "enhanced_prompt",
            "concept_name",
            "target_audience",
            "learning_objectives",
            "suggested_visuals",
            "estimated_duration"
        ]
        
        for field in required_fields:
            if field not in result:
                if field == "learning_objectives":
                    result[field] = ["Understand the concept"]
                elif field == "suggested_visuals":
                    result[field] = ["Relevant diagrams and animations"]
                else:
                    result[field] = "Not specified"
        
        if "video_script" not in result:
            result["video_script"] = {"scenes": []}
        
        if "code_examples" not in result:
            result["code_examples"] = []
        
        return result
        
    except Exception as e:
        return get_fallback_response(content, f"Failed to parse: {str(e)}")


def get_fallback_response(user_prompt: str, error: str = "Failed to enhance") -> Dict:
    """Return a fallback response when enhancement fails."""
    return {
        "enhanced_prompt": f"Create an educational video about {user_prompt}. Include clear explanations, visual demonstrations, and real-world examples with concrete numerical examples.",
        "concept_name": user_prompt,
        "target_audience": "General",
        "learning_objectives": [f"Understand {user_prompt}"],
        "video_script": {
            "scenes": [{
                "title": "Introduction",
                "narration": f"Welcome! Today we'll learn about {user_prompt}. Let's explore this fascinating concept together.",
                "visuals": ["Opening animation", "Title text"],
                "manim_code": "class Intro(Scene):\\n    def construct(self):\\n        title = Text('{user_prompt}')\\n        self.play(Write(title))",
                "duration": 7.5
            }]
        },
        "code_examples": [{
            "title": "Basic Example",
            "code": "# Example code for " + user_prompt + "\\n# Add your implementation here",
            "explanation": "Basic example demonstrating the concept."
        }],
        "suggested_visuals": ["Diagrams and animations"],
        "estimated_duration": 30,
        "error": error,
        "provider_used": "fallback",
        "model_used": "fallback",
        "retries": 0
    }


@tool
def prompt_enhancement_tool(
    user_prompt: str,
    system_prompt: Optional[str] = None,
    providers: Optional[List[str]] = None,
    models: Optional[List[str]] = None,
    max_retries: int = 3,
    temperature: float = 0
) -> Dict:
    """
    Enhance a user's educational prompt using LLM with multiple model fallback.
    
    Args:
        user_prompt: The user's original prompt/query
        system_prompt: Custom system prompt (uses default if None)
        providers: List of providers to try in order
        models: List of models corresponding to providers
        max_retries: Maximum retries per provider
        temperature: LLM temperature (0-1)
        
    Returns:
        Dict containing enhanced prompt with video script and metadata
    """
    return enhance_prompt_with_retry(
        user_prompt=user_prompt,
        system_prompt=system_prompt,
        providers=providers,
        models=models,
        max_retries=max_retries,
        temperature=temperature
    )


def enhance_prompt_sync(
    user_prompt: str,
    system_prompt: Optional[str] = None,
    providers: Optional[List[str]] = None,
    models: Optional[List[str]] = None,
    max_retries: int = 3,
    temperature: float = 0
) -> Dict:
    """
    Synchronous version of prompt enhancement.
    
    Args:
        user_prompt: The user's original prompt
        system_prompt: Custom system prompt
        providers: List of providers to try
        models: List of models to use
        max_retries: Maximum retries
        temperature: LLM temperature
        
    Returns:
        Enhanced prompt dictionary
    """
    return enhance_prompt_with_retry(
        user_prompt=user_prompt,
        system_prompt=system_prompt,
        providers=providers,
        models=models,
        max_retries=max_retries,
        temperature=temperature
    )
