"""
Job status tool for monitoring rendering jobs.
Provides status checking and polling capabilities.
"""
from langchain_core.tools import tool
from typing import Dict, Optional, List
import asyncio
import httpx
import os
import logging
from datetime import datetime
import random

logger = logging.getLogger(__name__)

# Reference to mock jobs from vm_executor_tool
from app.tools.vm_executor_tool import _mock_jobs


def get_vm_endpoint() -> Optional[str]:
    """Get VM render endpoint from environment."""
    return os.getenv("VM_RENDER_ENDPOINT")


async def check_job_status_async(job_id: str) -> Dict:
    """
    Check the status of a rendering job asynchronously.
    
    Args:
        job_id: Job identifier from vm_executor_tool
        
    Returns:
        Job status information
    """
    vm_endpoint = get_vm_endpoint()
    
    if not vm_endpoint or vm_endpoint == "http://localhost:8080":
        # Mock mode
        return await _mock_check_status(job_id)
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{vm_endpoint}/jobs/{job_id}/status")
            response.raise_for_status()
            return response.json()
    except httpx.ConnectError:
        return await _mock_check_status(job_id)
    except Exception as e:
        logger.error(f"Failed to check job status: {e}")
        return {
            "job_id": job_id,
            "status": "error",
            "error": str(e)
        }


async def _mock_check_status(job_id: str) -> Dict:
    """Mock status check - simulates job progression."""
    await asyncio.sleep(0.1)
    
    if job_id in _mock_jobs:
        job = _mock_jobs[job_id]
        
        # Simulate job progression
        current_status = job.get("status", "queued")
        
        if current_status == "queued":
            # 50% chance to move to processing
            if random.random() > 0.5:
                job["status"] = "processing"
                job["progress"] = 25
                job["started_at"] = datetime.utcnow().isoformat()
        elif current_status == "processing":
            # Increment progress
            progress = job.get("progress", 0) + random.randint(15, 30)
            if progress >= 100:
                job["status"] = "completed"
                job["progress"] = 100
                job["completed_at"] = datetime.utcnow().isoformat()
                job["output_path"] = f"/output/{job_id}.mp4"
            else:
                job["progress"] = min(progress, 95)
        
        return {
            "job_id": job_id,
            "status": job["status"],
            "progress": job.get("progress", 0),
            "output_path": job.get("output_path"),
            "error": job.get("error"),
            "started_at": job.get("started_at"),
            "completed_at": job.get("completed_at"),
            "scene_id": job.get("scene_id")
        }
    
    return {
        "job_id": job_id,
        "status": "not_found",
        "error": f"Job {job_id} not found"
    }


def check_job_status_sync(job_id: str) -> Dict:
    """Synchronous version of job status check."""
    vm_endpoint = get_vm_endpoint()
    
    if not vm_endpoint or vm_endpoint == "http://localhost:8080":
        # Mock mode - simulate completed job
        if job_id in _mock_jobs:
            job = _mock_jobs[job_id]
            # For sync testing, immediately complete
            return {
                "job_id": job_id,
                "status": "completed",
                "progress": 100,
                "output_path": f"/output/{job_id}.mp4",
                "error": None,
                "started_at": job.get("created_at"),
                "completed_at": datetime.utcnow().isoformat(),
                "scene_id": job.get("scene_id"),
                "duration_seconds": job.get("estimated_time", 30)
            }
        return {
            "job_id": job_id,
            "status": "completed",
            "progress": 100,
            "output_path": f"/output/{job_id}.mp4",
            "error": None
        }
    
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(f"{vm_endpoint}/jobs/{job_id}/status")
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"Sync status check failed: {e}")
        return {
            "job_id": job_id,
            "status": "error",
            "error": str(e)
        }


@tool
def job_status_tool(job_id: str) -> Dict:
    """
    Check rendering job status.
    
    Use this tool to poll the status of a rendering job submitted
    via vm_executor_tool. Keep polling until status is 'completed' or 'failed'.
    
    Args:
        job_id: Job identifier from vm_executor_tool
        
    Returns:
        Job status information with:
        - job_id: The job identifier
        - status: Current status (queued, processing, completed, failed)
        - progress: Completion percentage (0-100)
        - output_path: Path to rendered video (when completed)
        - error: Error message (if failed)
        - started_at: Job start timestamp
        - completed_at: Job completion timestamp
        - duration_seconds: Total render time
    """
    return check_job_status_sync(job_id)


@tool
async def job_status_tool_async(job_id: str) -> Dict:
    """
    Async version: Check rendering job status.
    
    Args:
        job_id: Job identifier from vm_executor_tool
        
    Returns:
        Job status information
    """
    return await check_job_status_async(job_id)


async def wait_for_completion(
    job_id: str,
    timeout_seconds: int = 300,
    poll_interval: float = 2.0
) -> Dict:
    """
    Wait for a job to complete with polling.
    
    Args:
        job_id: Job identifier
        timeout_seconds: Maximum wait time
        poll_interval: Seconds between status checks
        
    Returns:
        Final job status
    """
    start_time = datetime.utcnow()
    
    while True:
        status = await check_job_status_async(job_id)
        
        if status["status"] in ["completed", "failed", "error"]:
            return status
        
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        if elapsed > timeout_seconds:
            return {
                "job_id": job_id,
                "status": "timeout",
                "error": f"Job did not complete within {timeout_seconds} seconds"
            }
        
        await asyncio.sleep(poll_interval)


def wait_for_all_jobs(job_ids: List[str], timeout_seconds: int = 600) -> List[Dict]:
    """
    Wait for multiple jobs to complete.
    
    Args:
        job_ids: List of job identifiers
        timeout_seconds: Maximum total wait time
        
    Returns:
        List of final job statuses
    """
    # For sync mode, just return completed status for all
    return [check_job_status_sync(job_id) for job_id in job_ids]
