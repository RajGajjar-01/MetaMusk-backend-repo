"""
Script generator tool for creating Manim animation code using LLM.
Generates executable Manim Python code for educational animations.

Optimized with:
- Better system prompts with Manim best practices
- Retry logic for rate limiting
- Improved template fallback with real visual elements
- Caching support
"""
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from typing import List, Dict, Optional, Any
import os
import json
import logging
import time
import hashlib

logger = logging.getLogger(__name__)

# Cache for generated code (simple in-memory cache)
_code_cache: Dict[str, str] = {}

# Expert system prompt for Manim code generation with comprehensive examples
MANIM_SYSTEM_PROMPT = """You are a world-class Manim animator and Python developer. Generate complete, production-ready Manim code for educational animations.

## STRICT REQUIREMENTS:
1. Return ONLY valid Python code - no markdown, no explanations
2. Code must run with: `manim -pql script.py SceneName`
3. Use Manim Community Edition v0.18+ syntax
4. Always start with: `from manim import *`
5. **CRITICAL**: Total animation duration must be approximately 30 seconds (not 60!)

## CODE STRUCTURE (FOLLOW EXACTLY):
```python
from manim import *

class SceneName(Scene):
    def construct(self):
        # 1. Create objects first
        # 2. Position them
        # 3. Animate them with self.play()
        # 4. Add pauses with self.wait()
        pass
```

## CRITICAL ERROR PREVENTION:

### ❌ LATEX ERRORS - MUST AVOID:
- **ALWAYS use raw strings**: r"\\frac{{1}}{{2}}" NOT "\\frac{{1}}{{2}}"
- **Double escape backslashes**: r"\\alpha" NOT r"\alpha"
- **Test LaTeX**: Use simple math expressions, avoid complex LaTeX
- **Safe LaTeX examples**:
  - MathTex(r"x^2 + y^2 = r^2")
  - MathTex(r"\\frac{{a}}{{b}}")
  - MathTex(r"\\int_0^1 f(x) dx")
  - MathTex(r"\\alpha + \\beta = \\gamma")

### ❌ GETTER ERRORS - MUST AVOID:
- **NEVER pass arguments to getters**: obj.get_center() NOT obj.get_center(color=RED)
- **Correct getter usage**:
  - center = obj.get_center()  # No arguments!
  - top = obj.get_top()  # No arguments!
  - right = obj.get_right()  # No arguments!
- **Set properties separately**:
  - obj.set_color(RED)  # Use setter
  - obj.move_to(position)  # Use positioning methods

### ❌ ARGUMENT ERRORS - MUST AVOID:
- **NEVER use `end_angle`**: Use `angle` instead (angle = end_angle - start_angle)
- **Correct Arc usage**:
  - Arc(radius=1, start_angle=0, angle=TAU/4)  # Correct
  - Sector(inner_radius=1, outer_radius=2, angle=PI)  # Correct

### ❌ VECTOR NORMALIZATION - MUST AVOID:
- **NEVER call `.normalize()` on arrays**: numpy arrays don't have this method
- **Use Manim's normalize function**:
  - `from manim import normalize`
  - `normalized = normalize(vector)` # Correct
  - NOT `vector.normalize()` # Wrong!
- **For unit vectors**: Use `vector / np.linalg.norm(vector)` or `normalize(vector)`

### ❌ FILE DEPENDENCIES - MUST AVOID:
- **NEVER use external files**: No ImageMobject("path/to/image.png")
- **NEVER reference assets folder**: No SVGMobject("assets/icon.svg")
- **Use built-in shapes instead**:
  - Instead of brain icon → Use Circle or custom SVG path
  - Instead of images → Use geometric shapes and text
  - Instead of external SVG → Use Polygon, Arc, or built-in shapes

## MANIM BEST PRACTICES:

### Text & Math:
- Text("Regular text", font_size=36)
- MathTex(r"E = mc^2")  # Use raw strings for LaTeX
- Tex(r"\\alpha + \\beta")  # Double backslash for Greek letters

### Shapes:
- Circle(radius=1, color=BLUE, fill_opacity=0.5)
- Square(side_length=2, color=GREEN)
- Rectangle(width=4, height=2)
- Triangle()
- Arrow(start=LEFT, end=RIGHT)
- Line(start=LEFT*3, end=RIGHT*3)

### Positioning:
- .to_edge(UP/DOWN/LEFT/RIGHT)
- .to_corner(UL/UR/DL/DR)
- .move_to(ORIGIN)
- .next_to(other_mobject, direction, buff=0.5)
- .shift(UP * 2)

### Animations:
- Write(text)  # For text/equations
- Create(shape)  # For shapes
- FadeIn(obj), FadeOut(obj)
- Transform(obj1, obj2)
- ReplacementTransform(obj1, obj2)
- GrowFromCenter(obj)
- DrawBorderThenFill(obj)
- Indicate(obj)  # Highlight attention
- Circumscribe(obj)  # Draw circle around

### Color Palette:
RED, BLUE, GREEN, YELLOW, PURPLE, ORANGE, PINK, TEAL, GOLD
WHITE, BLACK, GRAY

### Grouping:
- VGroup(obj1, obj2, obj3).arrange(RIGHT, buff=0.5)
- Use arrange(DOWN) for vertical stacking

### Timing (TARGET: ~7-8 seconds per scene for 30-second total):
- self.play(animation, run_time=1.0)  # Keep animations short
- self.wait(0.5)  # Brief pauses only
- Use run_time=0.8 for quick animations
- Total scene duration should be 7-8 seconds

## COMMON PATTERNS:

### Equation with explanation:
```python
eq = MathTex(r"a^2 + b^2 = c^2")
label = Text("Pythagorean Theorem", font_size=24)
label.next_to(eq, DOWN)
self.play(Write(eq), run_time=1)
self.play(FadeIn(label), run_time=0.5)
self.wait(0.5)
```

### Step-by-step reveal:
```python
steps = VGroup(
    Text("Step 1: ...", font_size=28),
    Text("Step 2: ...", font_size=28),
    Text("Step 3: ...", font_size=28)
).arrange(DOWN, aligned_edge=LEFT)
for step in steps:
    self.play(Write(step), run_time=0.8)
    self.wait(0.3)
```

### Diagram with labels:
```python
circle = Circle(radius=1.5, color=BLUE)
center = circle.get_center()  # No arguments!
right_point = circle.get_right()  # No arguments!
radius = Line(center, right_point, color=RED)
r_label = MathTex(r"r").next_to(radius, UP, buff=0.1)
self.play(Create(circle), run_time=1)
self.play(Create(radius), Write(r_label), run_time=0.8)
```

## OUTPUT:
Return ONLY Python code. No explanations. No markdown formatting. Keep duration to ~7-8 seconds per scene."""


def get_llm(model: str = "gemini-2.5-flash"):
    """Get LLM for code generation with fallback models."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.warning("GOOGLE_API_KEY not found")
        return None
    
    try:
        return ChatGoogleGenerativeAI(
            model=model,
            temperature=0.1  # Very low for consistent code generation
        )
    except Exception as e:
        logger.error(f"Failed to initialize LLM: {e}")
        return None


def _get_cache_key(scene_description: str, visual_elements: List[str], narration: str, scene_id: str) -> str:
    """Generate cache key for a scene."""
    content = f"{scene_description}|{'|'.join(sorted(visual_elements))}|{narration[:100]}|{scene_id}"
    return hashlib.md5(content.encode()).hexdigest()


def generate_manim_code_with_llm(
    scene_description: str,
    visual_elements: List[str],
    narration: str,
    scene_id: str = "GeneratedScene",
    duration: float = 7.5,
    use_cache: bool = True,
    max_retries: int = 3
) -> str:
    """
    Generate Manim code using LLM with retry logic and caching.
    
    Args:
        scene_description: What the scene should demonstrate
        visual_elements: List of objects/animations needed
        narration: Voice-over text
        scene_id: Class name for the scene
        duration: Target duration in seconds
        use_cache: Whether to use cached results
        max_retries: Number of retry attempts on rate limiting
        
    Returns:
        Complete Manim Python code
    """
    # Check cache first
    cache_key = _get_cache_key(scene_description, visual_elements, narration, scene_id)
    if use_cache and cache_key in _code_cache:
        logger.info(f"Cache hit for scene: {scene_id}")
        return _code_cache[cache_key]
    
    llm = get_llm()
    
    if not llm:
        logger.warning("LLM not available, using template fallback")
        return generate_smart_template(scene_description, visual_elements, narration, scene_id, duration)
    
    # Build a detailed prompt
    visual_list = "\n".join(f"- {elem}" for elem in visual_elements) if visual_elements else "- General educational animation"
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", MANIM_SYSTEM_PROMPT),
        ("human", """Create a Manim animation for:

**Scene:** {scene_description}

**Required Visual Elements:**
{visual_elements}

**Narration/Context:** "{narration}"

**Class Name:** {scene_id}
**Duration:** ~{duration} seconds

Generate complete, runnable Manim code. Include all visual elements. Match timing to duration.""")
    ])
    
    # Retry loop for rate limiting
    for attempt in range(max_retries):
        try:
            chain = prompt | llm
            response = chain.invoke({
                "scene_description": scene_description,
                "visual_elements": visual_list,
                "narration": narration[:500],  # Limit narration length
                "scene_id": scene_id,
                "duration": duration
            })
            
            code = response.content
            
            # Clean up the response - remove markdown code blocks
            if "```python" in code:
                code = code.split("```python")[1].split("```")[0]
            elif "```" in code:
                parts = code.split("```")
                if len(parts) >= 2:
                    code = parts[1]
            
            code = code.strip()
            
            # Validate and fix basic structure
            if "from manim import" not in code:
                code = "from manim import *\n\n" + code
            
            if "class " not in code or "def construct" not in code:
                logger.warning("Generated code incomplete, using smart template")
                return generate_smart_template(scene_description, visual_elements, narration, scene_id, duration)
            
            # Cache the result
            _code_cache[cache_key] = code
            
            logger.info(f"✅ Generated Manim code for: {scene_id}")
            return code
            
        except Exception as e:
            error_msg = str(e)
            
            # Check for rate limiting
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg or "quota" in error_msg.lower():
                wait_time = (attempt + 1) * 10  # 10s, 20s, 30s
                logger.warning(f"Rate limited, waiting {wait_time}s before retry {attempt + 1}/{max_retries}")
                time.sleep(wait_time)
                continue
            else:
                logger.error(f"LLM generation error: {e}")
                break
    
    # Final fallback to template
    logger.warning("All LLM attempts failed, using smart template")
    return generate_smart_template(scene_description, visual_elements, narration, scene_id, duration)


def generate_smart_template(
    scene_description: str,
    visual_elements: List[str],
    narration: str,
    scene_id: str = "GeneratedScene",
    duration: float = 7.5
) -> str:
    """
    Generate intelligent template-based Manim code using visual elements.
    
    This template actually uses the visual elements to create
    meaningful animations instead of generic shapes.
    """
    # Parse visual elements to create actual objects
    mobject_definitions = []
    mobject_names = []
    animations = []
    
    for i, element in enumerate(visual_elements[:5]):  # Limit to 5 elements
        element_lower = element.lower()
        name = f"element_{i}"
        mobject_names.append(name)
        
        # Detect element type and create appropriate Manim object
        if "circle" in element_lower:
            mobject_definitions.append(f'{name} = Circle(radius=1.2, color=BLUE, fill_opacity=0.3)')
        elif "square" in element_lower:
            mobject_definitions.append(f'{name} = Square(side_length=2, color=GREEN, fill_opacity=0.3)')
        elif "triangle" in element_lower:
            mobject_definitions.append(f'{name} = Triangle(color=YELLOW, fill_opacity=0.3).scale(1.5)')
        elif "arrow" in element_lower:
            mobject_definitions.append(f'{name} = Arrow(LEFT * 2, RIGHT * 2, color=RED)')
        elif "equation" in element_lower or "formula" in element_lower or "math" in element_lower:
            mobject_definitions.append(f'{name} = MathTex(r"f(x) = ax^2 + bx + c", font_size=36)')
        elif "graph" in element_lower or "plot" in element_lower:
            mobject_definitions.append(f'{name} = Axes(x_range=[-3, 3], y_range=[-2, 2], axis_config={{"include_numbers": True}})')
        elif "text" in element_lower or "label" in element_lower:
            clean_text = element.replace('"', '\\"')[:40]
            mobject_definitions.append(f'{name} = Text("{clean_text}", font_size=28)')
        elif "line" in element_lower:
            mobject_definitions.append(f'{name} = Line(LEFT * 2, RIGHT * 2, color=WHITE)')
        elif "rectangle" in element_lower or "box" in element_lower:
            mobject_definitions.append(f'{name} = Rectangle(width=3, height=1.5, color=PURPLE, fill_opacity=0.2)')
        elif "number" in element_lower or "digit" in element_lower:
            mobject_definitions.append(f'{name} = MathTex(r"1, 2, 3, 4, 5", font_size=48)')
        else:
            # Default: create a labeled box for unknown elements
            clean_text = element.replace('"', '\\"')[:30]
            mobject_definitions.append(f'{name} = VGroup(Rectangle(width=3, height=1, color=TEAL), Text("{clean_text}", font_size=20)).arrange(ORIGIN)')
        
        animations.append(f'self.play(Create({name}), run_time=0.8)')
    
    # If no visual elements, create default ones
    if not mobject_definitions:
        mobject_definitions = [
            'title_text = Text("' + scene_description[:40].replace('"', '\\"') + '", font_size=36)',
            'main_shape = Circle(radius=1.5, color=BLUE, fill_opacity=0.5)',
        ]
        mobject_names = ['title_text', 'main_shape']
        animations = [
            'self.play(Write(title_text), run_time=1)',
            'title_text.to_edge(UP)',
            'self.play(Create(main_shape), run_time=1)',
        ]
    
    # Create the positioning code
    if len(mobject_names) > 1:
        positioning = f'VGroup({", ".join(mobject_names)}).arrange(RIGHT, buff=0.8).move_to(ORIGIN)'
    else:
        positioning = f'{mobject_names[0]}.move_to(ORIGIN)'
    
    # Create narration text
    display_narration = narration[:50].replace('"', '\\"') if narration else scene_description[:50].replace('"', '\\"')
    
    # Calculate wait times based on duration
    total_anim_time = len(animations) * 0.8 + 2  # Animation time + intro/outro
    pause_time = max(0.5, (duration - total_anim_time) / (len(animations) + 2))
    
    animations_code = f"\n        self.wait({pause_time:.1f})\n        ".join(animations)
    
    return f'''from manim import *

class {scene_id}(Scene):
    """
    {scene_description[:80]}
    """
    def construct(self):
        # ===== Title =====
        title = Text("{display_narration}...", font_size=32, color=WHITE)
        title.to_edge(UP, buff=0.5)
        self.play(Write(title), run_time=1)
        self.wait(0.3)
        
        # ===== Visual Elements =====
        {chr(10).join('        ' + d for d in mobject_definitions)}
        
        # ===== Positioning =====
        {positioning}
        
        # ===== Animations =====
        {animations_code}
        
        self.wait({pause_time:.1f})
        
        # ===== Highlight Key Point =====
        if len([{', '.join(mobject_names)}]) > 0:
            self.play(Indicate({mobject_names[0]}), run_time=0.5)
        
        self.wait(1)
        
        # ===== Fade Out =====
        self.play(
            *[FadeOut(mob) for mob in self.mobjects],
            run_time=1
        )
'''


def generate_from_enhanced_prompt(enhanced_prompt_data: Dict[str, Any]) -> List[Dict]:
    """
    Generate Manim code for all scenes from an enhanced prompt.
    
    Args:
        enhanced_prompt_data: Output from prompt_enhancement_tool
        
    Returns:
        List of scene dictionaries with generated code
    """
    scenes = []
    video_script = enhanced_prompt_data.get("video_script", {})
    script_scenes = video_script.get("scenes", [])
    
    logger.info(f"📝 Generating Manim code for {len(script_scenes)} scenes")
    
    for i, scene in enumerate(script_scenes):
        scene_id = f"Scene{i + 1}_{scene.get('title', 'Untitled').replace(' ', '').replace('-', '')[:20]}"
        
        logger.info(f"🎬 Generating scene {i + 1}/{len(script_scenes)}: {scene_id}")
        
        # Generate Manim code for this scene
        code = generate_manim_code_with_llm(
            scene_description=scene.get("title", "Animation Scene"),
            visual_elements=scene.get("visuals", []),
            narration=scene.get("narration", ""),
            scene_id=scene_id,
            duration=scene.get("duration", 15)
        )
        
        scenes.append({
            "scene_id": scene_id,
            "title": scene.get("title", f"Scene {i + 1}"),
            "narration": scene.get("narration", ""),
            "visuals": scene.get("visuals", []),
            "duration": scene.get("duration", 15),
            "manim_code": code
        })
    
    logger.info(f"✅ Generated code for {len(scenes)} scenes")
    return scenes


@tool
def script_generator_tool(
    scene_description: str,
    visual_elements: List[str],
    narration: str,
    scene_id: str = "GeneratedScene",
    duration: float = 7.5
) -> str:
    """
    Generate Manim script code for a scene using LLM.
    
    This tool creates complete, executable Manim Python code for educational
    animations based on the scene description and requirements.
    
    Args:
        scene_description: What the scene should demonstrate (e.g., "Show the Pythagorean theorem")
        visual_elements: List of objects/animations needed (e.g., ["right triangle", "squares on sides"])
        narration: Voice-over text for the scene
        scene_id: Class name for the Manim scene (default: "GeneratedScene")
        duration: Target duration in seconds (default: 15.0)
        
    Returns:
        Complete Manim Python code as a string
    """
    logger.info(f"🎨 Script generator called for: {scene_id}")
    return generate_manim_code_with_llm(
        scene_description=scene_description,
        visual_elements=visual_elements,
        narration=narration,
        scene_id=scene_id,
        duration=duration
    )


# Utility function for batch generation
def generate_all_scenes(enhanced_prompt: Dict) -> Dict:
    """
    Generate Manim code for all scenes in an enhanced prompt.
    
    Args:
        enhanced_prompt: Output from prompt_enhancement_tool
        
    Returns:
        Dictionary with all generated scenes and metadata
    """
    scenes = generate_from_enhanced_prompt(enhanced_prompt)
    
    return {
        "concept_name": enhanced_prompt.get("concept_name", "Unknown"),
        "total_scenes": len(scenes),
        "estimated_duration": sum(s.get("duration", 15) for s in scenes),
        "scenes": scenes
    }


def clear_cache():
    """Clear the code generation cache."""
    global _code_cache
    _code_cache = {}
    logger.info("Code generation cache cleared")
