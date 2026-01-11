"""
VM executor tool for rendering Manim animations on remote infrastructure.
Handles job submission, queuing, and execution tracking.
"""
from langchain_core.tools import tool
from typing import Dict, Optional, List
import asyncio
import httpx
import os
import logging
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

# In-memory job store for mock mode
_mock_jobs: Dict[str, Dict] = {}


def get_vm_endpoint() -> Optional[str]:
    """Get VM render endpoint from environment."""
    return os.getenv("VM_RENDER_ENDPOINT")


async def submit_render_job_async(
    script: str,
    scene_id: str,
    quality: str = "low_quality",
    output_format: str = "mp4"
) -> Dict:
    """
    Submit a rendering job to the VM infrastructure.
    
    Args:
        script: Manim script code to execute
        scene_id: Unique scene identifier
        quality: Render quality (low_quality, medium_quality, high_quality)
        output_format: Output format (mp4, gif, webm)
        
    Returns:
        Job submission status
    """
    vm_endpoint = get_vm_endpoint()
    
    if not vm_endpoint or vm_endpoint == "http://localhost:8080":
        # Mock mode - simulate job submission
        return await _mock_submit_job(script, scene_id, quality, output_format)
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{vm_endpoint}/render",
                json={
                    "script": script,
                    "scene_id": scene_id,
                    "quality": quality,
                    "format": output_format,
                    "options": {
                        "resolution": "1920x1080" if quality == "high_quality" else ("1280x720" if quality == "medium_quality" else "854x480"),
                        "fps": 60 if quality == "high_quality" else (30 if quality == "medium_quality" else 15)
                    }
                }
            )
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"Submitted render job: {result.get('job_id')} for scene: {scene_id}")
            return result
            
    except httpx.ConnectError:
        logger.warning(f"VM endpoint not available, using mock mode")
        return await _mock_submit_job(script, scene_id, quality, output_format)
    except Exception as e:
        logger.error(f"Failed to submit render job: {e}")
        return {
            "job_id": f"error-{scene_id}",
            "status": "failed",
            "error": str(e),
            "scene_id": scene_id
        }


async def _mock_submit_job(
    script: str,
    scene_id: str,
    quality: str,
    output_format: str
) -> Dict:
    """Mock job submission for development/testing."""
    await asyncio.sleep(0.1)  # Simulate network latency
    
    job_id = f"job-{scene_id}-{uuid.uuid4().hex[:8]}"
    
    job_data = {
        "job_id": job_id,
        "status": "queued",
        "scene_id": scene_id,
        "quality": quality,
        "format": output_format,
        "created_at": datetime.utcnow().isoformat(),
        "estimated_time": 30 if quality == "high_quality" else (15 if quality == "medium_quality" else 5),
        "vm_instance": "mock-vm-01",
        "queue_position": len(_mock_jobs) + 1,
        "script_hash": hash(script) % 100000
    }
    
    _mock_jobs[job_id] = job_data
    
    logger.info(f"Mock job submitted: {job_id}")
    return job_data


def submit_render_job_sync(
    script: str,
    scene_id: str,
    quality: str = "low_quality",
    output_format: str = "mp4"
) -> Dict:
    """Synchronous version of job submission."""
    vm_endpoint = get_vm_endpoint()
    
    if not vm_endpoint or vm_endpoint == "http://localhost:8080":
        # Mock mode
        job_id = f"job-{scene_id}-{uuid.uuid4().hex[:8]}"
        job_data = {
            "job_id": job_id,
            "status": "queued",
            "scene_id": scene_id,
            "quality": quality,
            "format": output_format,
            "created_at": datetime.utcnow().isoformat(),
            "estimated_time": 30 if quality == "high_quality" else (15 if quality == "medium_quality" else 5),
            "vm_instance": "mock-vm-01",
            "queue_position": 1
        }
        _mock_jobs[job_id] = job_data
        return job_data
    
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{vm_endpoint}/render",
                json={
                    "script": script,
                    "scene_id": scene_id,
                    "quality": quality,
                    "format": output_format
                }
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"Sync render submission failed: {e}")
        return {
            "job_id": f"error-{scene_id}",
            "status": "failed",
            "error": str(e)
        }


@tool
def vm_executor_tool(script: str, scene_id: str) -> Dict:
    """
    Execute Manim rendering job on VM infrastructure.
    
    Submits a Manim script to the render farm for execution. The script
    will be queued and processed by an available VM instance.
    
    Args:
        script: Complete Manim Python script to execute
        scene_id: Unique identifier for this scene (e.g., "Scene1_Introduction")
        
    Returns:
        Job submission status with:
        - job_id: Unique job identifier for tracking
        - status: Current status (queued, processing, completed, failed)
        - scene_id: The scene identifier
        - estimated_time: Estimated render time in seconds
        - vm_instance: Assigned VM instance name
        - queue_position: Position in render queue
    """
    return submit_render_job_sync(script, scene_id)


@tool
async def vm_executor_tool_async(script: str, scene_id: str) -> Dict:
    """
    Async version: Execute Manim rendering job on VM infrastructure.
    
    Args:
        script: Complete Manim Python script to execute
        scene_id: Unique identifier for this scene
        
    Returns:
        Job submission status
    """
    return await submit_render_job_async(script, scene_id)


def submit_batch_jobs(scenes: List[Dict]) -> List[Dict]:
    """
    Submit multiple scenes for rendering.
    
    Args:
        scenes: List of scene dictionaries with 'manim_code' and 'scene_id'
        
    Returns:
        List of job submission results
    """
    results = []
    for scene in scenes:
        result = submit_render_job_sync(
            script=scene.get("manim_code", ""),
            scene_id=scene.get("scene_id", f"scene-{len(results)}")
        )
        results.append(result)
    return results


def submit_full_video_job(scenes: List[Dict], quality: str = "low_quality") -> Dict:
    """
    Submit all scenes to VM for full video rendering.
    
    Args:
        scenes: List of scene dictionaries with 'manim_code' and 'scene_id'
        quality: Render quality
        
    Returns:
        Job submission result with job_id
    """
    vm_endpoint = get_vm_endpoint()
    
    if not vm_endpoint or vm_endpoint == "http://localhost:8080":
        logger.warning("VM endpoint not configured, using mock mode")
        return _mock_full_video_job(scenes)
    
    try:
        scene_data = [
            {"scene_id": s.get("scene_id", f"Scene{i+1}"), "script": s.get("manim_code", "")}
            for i, s in enumerate(scenes)
        ]
        
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{vm_endpoint}/render-all",
                json={"scenes": scene_data, "quality": quality}
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"Submitted full video job: {result.get('job_id')}")
            return result
    except Exception as e:
        logger.error(f"Failed to submit full video job: {e}")
        return _mock_full_video_job(scenes)


def _mock_full_video_job(scenes: List[Dict]) -> Dict:
    """Mock full video job for development."""
    from pathlib import Path
    
    job_id = f"mock-full-{uuid.uuid4().hex[:8]}"
    
    # Use absolute path for output
    output_dir = os.getenv("VIDEO_OUTPUT_DIR", "media")
    if not os.path.isabs(output_dir):
        backend_root = Path(__file__).parent.parent.parent
        output_dir = str(backend_root / output_dir)
    
    _mock_jobs[job_id] = {
        "job_id": job_id,
        "status": "completed",  # Mock completes immediately
        "scene_count": len(scenes),
        "progress": 100,
        "output_path": os.path.join(output_dir, "final_video.mp4")
    }
    return _mock_jobs[job_id]


def poll_and_download_video(job_id: str, max_wait: int = 600) -> Dict:
    """
    Poll job status and download video when complete.
    
    Args:
        job_id: Job ID from submit_full_video_job
        max_wait: Maximum seconds to wait
        
    Returns:
        Result with local video path
    """
    import time
    from pathlib import Path
    
    vm_endpoint = get_vm_endpoint()
    
    # Get output directory - use absolute path relative to backend root
    output_dir = os.getenv("VIDEO_OUTPUT_DIR", "media")
    if not os.path.isabs(output_dir):
        # Make path absolute relative to backend directory
        backend_root = Path(__file__).parent.parent.parent
        output_dir = str(backend_root / output_dir)
    
    os.makedirs(output_dir, exist_ok=True)
    local_path = os.path.join(output_dir, f"{job_id}_final.mp4")
    
    # Check for mock mode: either no VM endpoint OR job_id indicates mock
    is_mock = (not vm_endpoint or 
               vm_endpoint == "http://localhost:8080" or 
               job_id.startswith("mock-"))
    
    if is_mock:
        # Mock mode - return fake path immediately, don't poll
        logger.info(f"Mock mode detected for job {job_id}, returning immediately")
        return {
            "status": "completed",
            "local_path": os.path.join(output_dir, "final_video.mp4"),
            "note": "Mock mode - no actual video generated. Deploy render_worker to VM for real rendering."
        }
    
    logger.info(f"Polling job {job_id} from {vm_endpoint}, saving to {local_path}")
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(f"{vm_endpoint}/jobs/{job_id}/status")
                status_data = response.json()
                
                if status_data.get("status") == "completed":
                    # Download the video
                    logger.info(f"Job {job_id} completed, downloading...")
                    video_response = client.get(
                        f"{vm_endpoint}/jobs/{job_id}/result",
                        timeout=300.0
                    )
                    video_response.raise_for_status()
                    
                    with open(local_path, "wb") as f:
                        f.write(video_response.content)
                    
                    logger.info(f"Video saved to: {local_path}")
                    return {
                        "status": "completed",
                        "local_path": local_path,
                        "file_size": len(video_response.content)
                    }
                    
                elif status_data.get("status") == "failed":
                    return {
                        "status": "failed",
                        "error": status_data.get("error", "Unknown error")
                    }
                
                # Still processing
                logger.debug(f"Job {job_id} progress: {status_data.get('progress', 0)}%")
                time.sleep(2)
                
        except Exception as e:
            logger.warning(f"Poll error: {e}")
            time.sleep(5)
    
    return {"status": "timeout", "error": f"Job did not complete in {max_wait}s"}


@tool
def full_video_executor_tool(scenes: List[Dict]) -> Dict:
    """
    Execute full video rendering on VM and download result.
    
    Submits all scenes to the VM render worker, waits for completion,
    and downloads the final assembled video.
    
    Args:
        scenes: List of scene dictionaries, each with:
            - scene_id: Unique identifier for the scene
            - manim_code: Complete Manim Python script
            
    Returns:
        Result with:
        - status: 'completed', 'failed', or 'timeout'
        - local_path: Path to downloaded video (if completed)
        - error: Error message (if failed)
    """
    if not scenes:
        return {"status": "failed", "error": "No scenes provided"}
    
    logger.info(f"Submitting {len(scenes)} scenes for full video rendering")
    
    # Submit job
    job_result = submit_full_video_job(scenes)
    job_id = job_result.get("job_id")
    
    if not job_id:
        return {"status": "failed", "error": "Failed to submit job"}
    
    # Poll and download
    return poll_and_download_video(job_id)
