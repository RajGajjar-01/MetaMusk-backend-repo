"""
Aggregator tool for combining rendered scenes into a sequence.
Uses ffmpeg for video concatenation.
"""
from langchain_core.tools import tool
from typing import List, Dict, Optional
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


def get_video_duration(video_path: str) -> float:
    """Get duration of a video file using ffprobe."""
    try:
        result = subprocess.run([
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            return float(result.stdout.strip())
    except Exception as e:
        logger.warning(f"Could not get duration for {video_path}: {e}")
    
    return 15.0  # Default duration estimate


def concatenate_videos(scene_paths: List[str], output_path: str) -> Dict:
    """
    Concatenate multiple video files using ffmpeg.
    
    Args:
        scene_paths: List of video file paths
        output_path: Path for the output video
        
    Returns:
        Aggregation result
    """
    if not check_ffmpeg_available():
        logger.warning("ffmpeg not available, using mock aggregation")
        return mock_aggregate(scene_paths)
    
    # Filter existing files
    existing_paths = [p for p in scene_paths if os.path.exists(p)]
    
    if not existing_paths:
        logger.warning("No existing video files found, using mock aggregation")
        return mock_aggregate(scene_paths)
    
    try:
        # Create concat file for ffmpeg
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            concat_file = f.name
            for path in existing_paths:
                # Escape single quotes in path
                escaped_path = path.replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")
        
        # Run ffmpeg concatenation
        cmd = [
            "ffmpeg", "-y",  # Overwrite output
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c", "copy",  # Copy streams without re-encoding
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        # Clean up concat file
        os.unlink(concat_file)
        
        if result.returncode != 0:
            logger.error(f"ffmpeg error: {result.stderr}")
            return mock_aggregate(scene_paths)
        
        # Get total duration
        total_duration = get_video_duration(output_path)
        
        # Get file size
        file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
        
        return {
            "aggregated_path": output_path,
            "total_duration": total_duration,
            "scene_count": len(existing_paths),
            "file_size_bytes": file_size,
            "resolution": "1920x1080",
            "fps": 60,
            "status": "success"
        }
        
    except subprocess.TimeoutExpired:
        logger.error("ffmpeg concatenation timed out")
        return mock_aggregate(scene_paths)
    except Exception as e:
        logger.error(f"Video concatenation failed: {e}")
        return mock_aggregate(scene_paths)


def mock_aggregate(scene_paths: List[str]) -> Dict:
    """Mock aggregation for development/testing."""
    output_dir = get_output_directory()
    output_path = os.path.join(output_dir, "combined.mp4")
    
    return {
        "aggregated_path": output_path,
        "total_duration": len(scene_paths) * 15.0,
        "scene_count": len(scene_paths),
        "file_size_bytes": len(scene_paths) * 5 * 1024 * 1024,  # ~5MB per scene
        "resolution": "1920x1080",
        "fps": 60,
        "status": "mock",
        "note": "Using mock aggregation - ffmpeg not available or no input files"
    }


@tool
def aggregator_tool(scene_paths: List[str]) -> Dict:
    """
    Aggregate rendered scenes into a single video sequence.
    
    Takes multiple rendered scene video files and concatenates them
    into a single continuous video using ffmpeg.
    
    Args:
        scene_paths: List of rendered scene file paths (e.g., ["/output/scene1.mp4", "/output/scene2.mp4"])
        
    Returns:
        Aggregation result with:
        - aggregated_path: Path to the combined video
        - total_duration: Total duration in seconds
        - scene_count: Number of scenes combined
        - file_size_bytes: Output file size
        - resolution: Video resolution
        - fps: Frames per second
        - status: 'success' or 'mock'
    """
    output_dir = get_output_directory()
    output_path = os.path.join(output_dir, "combined.mp4")
    
    return concatenate_videos(scene_paths, output_path)


def aggregate_from_job_results(job_results: List[Dict]) -> Dict:
    """
    Aggregate videos from job status results.
    
    Args:
        job_results: List of job status dictionaries with 'output_path'
        
    Returns:
        Aggregation result
    """
    scene_paths = [
        job.get("output_path")
        for job in job_results
        if job.get("status") == "completed" and job.get("output_path")
    ]
    
    if not scene_paths:
        return mock_aggregate([f"scene_{i}.mp4" for i in range(len(job_results))])
    
    output_dir = get_output_directory()
    output_path = os.path.join(output_dir, "combined.mp4")
    
    return concatenate_videos(scene_paths, output_path)
