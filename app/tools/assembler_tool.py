"""
Assembler tool for final video assembly with polish.
Adds transitions, audio, and finishing touches.
"""
from langchain_core.tools import tool
from typing import Dict, Optional, List
import subprocess
import os
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def get_output_directory() -> str:
    """Get or create output directory for videos."""
    from pathlib import Path as PathLib
    
    output_dir = os.getenv("VIDEO_OUTPUT_DIR", "media")
    
    # Make path absolute relative to backend root if not already absolute
    if not os.path.isabs(output_dir):
        backend_root = PathLib(__file__).parent.parent.parent
        output_dir = str(backend_root / output_dir)
    
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def check_ffmpeg_available() -> bool:
    """Check if ffmpeg is available."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def get_video_info(video_path: str) -> Dict:
    """Get video information using ffprobe."""
    info = {
        "duration": 0,
        "width": 1920,
        "height": 1080,
        "fps": 60
    }
    
    try:
        # Get duration
        result = subprocess.run([
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            info["duration"] = float(result.stdout.strip())
        
        # Get resolution and fps
        result = subprocess.run([
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate",
            "-of", "csv=p=0",
            video_path
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            parts = result.stdout.strip().split(",")
            if len(parts) >= 3:
                info["width"] = int(parts[0])
                info["height"] = int(parts[1])
                # Parse fps from fraction like "60/1"
                fps_parts = parts[2].split("/")
                if len(fps_parts) == 2:
                    info["fps"] = int(fps_parts[0]) / int(fps_parts[1])
                    
    except Exception as e:
        logger.warning(f"Could not get video info: {e}")
    
    return info


def assemble_video(
    aggregated_path: str,
    output_path: str,
    add_audio: bool = False,
    audio_path: Optional[str] = None,
    add_transitions: bool = True,
    fade_duration: float = 0.5
) -> Dict:
    """
    Assemble final video with polish effects.
    
    Args:
        aggregated_path: Path to aggregated video
        output_path: Path for final output
        add_audio: Whether to add background audio
        audio_path: Path to audio file
        add_transitions: Whether to add fade transitions
        fade_duration: Duration of fade effects in seconds
        
    Returns:
        Assembly result
    """
    if not check_ffmpeg_available():
        logger.warning("ffmpeg not available, using mock assembly")
        return mock_assemble(aggregated_path, add_audio, add_transitions)
    
    if not os.path.exists(aggregated_path):
        logger.warning(f"Input file not found: {aggregated_path}")
        return mock_assemble(aggregated_path, add_audio, add_transitions)
    
    try:
        video_info = get_video_info(aggregated_path)
        duration = video_info["duration"]
        
        # Build ffmpeg filter
        filters = []
        
        if add_transitions:
            # Add fade in at start and fade out at end
            fade_out_start = max(0, duration - fade_duration)
            filters.append(f"fade=in:0:d={fade_duration}")
            filters.append(f"fade=out:st={fade_out_start}:d={fade_duration}")
        
        # Build command
        cmd = ["ffmpeg", "-y", "-i", aggregated_path]
        
        # Add audio if requested
        if add_audio and audio_path and os.path.exists(audio_path):
            cmd.extend(["-i", audio_path])
        
        # Add video filters
        if filters:
            cmd.extend(["-vf", ",".join(filters)])
        
        # Handle audio
        if add_audio and audio_path and os.path.exists(audio_path):
            cmd.extend([
                "-c:v", "libx264",
                "-c:a", "aac",
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-shortest"
            ])
        else:
            cmd.extend([
                "-c:v", "libx264",
                "-an"  # No audio
            ])
        
        # Quality settings
        cmd.extend([
            "-preset", "medium",
            "-crf", "23",
            output_path
        ])
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        if result.returncode != 0:
            logger.error(f"ffmpeg assembly error: {result.stderr}")
            return mock_assemble(aggregated_path, add_audio, add_transitions)
        
        # Get final video info
        final_info = get_video_info(output_path)
        file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
        
        return {
            "final_video_path": output_path,
            "file_size_mb": file_size / (1024 * 1024),
            "duration_seconds": final_info["duration"],
            "resolution": f"{final_info['width']}x{final_info['height']}",
            "fps": final_info["fps"],
            "codec": "h264",
            "has_audio": add_audio and audio_path is not None,
            "has_transitions": add_transitions,
            "status": "success"
        }
        
    except subprocess.TimeoutExpired:
        logger.error("ffmpeg assembly timed out")
        return mock_assemble(aggregated_path, add_audio, add_transitions)
    except Exception as e:
        logger.error(f"Video assembly failed: {e}")
        return mock_assemble(aggregated_path, add_audio, add_transitions)


def mock_assemble(
    aggregated_path: str,
    add_audio: bool,
    add_transitions: bool
) -> Dict:
    """Mock assembly for development/testing."""
    output_dir = get_output_directory()
    output_path = os.path.join(output_dir, "final_video.mp4")
    
    return {
        "final_video_path": output_path,
        "file_size_mb": 12.5,
        "duration_seconds": 45.0,
        "resolution": "1920x1080",
        "fps": 60,
        "codec": "h264",
        "has_audio": add_audio,
        "has_transitions": add_transitions,
        "status": "mock",
        "note": "Using mock assembly - ffmpeg not available or input file missing"
    }


@tool
def assembler_tool(
    aggregated_path: str,
    add_audio: bool = False,
    add_transitions: bool = True
) -> Dict:
    """
    Assemble final video with polish effects.
    
    Takes the aggregated video and applies finishing touches like
    fade transitions and optional background audio.
    
    Args:
        aggregated_path: Path to aggregated scenes video (from aggregator_tool)
        add_audio: Whether to add background music (default: False)
        add_transitions: Whether to add fade in/out transitions (default: True)
        
    Returns:
        Final video information with:
        - final_video_path: Path to the finished video
        - file_size_mb: File size in megabytes
        - duration_seconds: Video duration
        - resolution: Video resolution
        - fps: Frames per second
        - codec: Video codec used
        - has_audio: Whether audio was added
        - has_transitions: Whether transitions were added
        - status: 'success' or 'mock'
    """
    output_dir = get_output_directory()
    output_path = os.path.join(output_dir, "final_video.mp4")
    
    # Look for default audio file if requested
    audio_path = None
    if add_audio:
        default_audio = os.path.join(output_dir, "background_music.mp3")
        if os.path.exists(default_audio):
            audio_path = default_audio
    
    return assemble_video(
        aggregated_path=aggregated_path,
        output_path=output_path,
        add_audio=add_audio,
        audio_path=audio_path,
        add_transitions=add_transitions
    )


def create_final_video(
    aggregated_result: Dict,
    add_audio: bool = False,
    add_transitions: bool = True
) -> Dict:
    """
    Create final video from aggregation result.
    
    Args:
        aggregated_result: Output from aggregator_tool
        add_audio: Whether to add background audio
        add_transitions: Whether to add fade transitions
        
    Returns:
        Final video result
    """
    aggregated_path = aggregated_result.get("aggregated_path", "")
    
    output_dir = get_output_directory()
    output_path = os.path.join(output_dir, "final_video.mp4")
    
    return assemble_video(
        aggregated_path=aggregated_path,
        output_path=output_path,
        add_audio=add_audio,
        add_transitions=add_transitions
    )
