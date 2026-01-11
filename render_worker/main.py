from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import subprocess
import os
import uuid
import logging
from typing import Dict, Optional, List
from datetime import datetime
from fastapi.responses import FileResponse
import tempfile

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Manim Render Worker")

# Job storage (in-memory for simplicity, use Redis/DB for production)
jobs: Dict[str, Dict] = {}
OUTPUT_DIR = "/app/output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

class RenderRequest(BaseModel):
    script: str
    scene_id: str
    quality: str = "low_quality"  # low_quality, medium_quality, high_quality
    format: str = "mp4"

class SceneScript(BaseModel):
    scene_id: str
    script: str

class RenderAllRequest(BaseModel):
    scenes: List[SceneScript]
    quality: str = "low_quality"
    format: str = "mp4"

def run_render_job(job_id: str, request: RenderRequest):
    """Background task to run Manim render."""
    try:
        jobs[job_id]["status"] = "processing"
        jobs[job_id]["started_at"] = datetime.utcnow().isoformat()
        
        # Save script to file
        script_path = os.path.join(OUTPUT_DIR, f"{job_id}_script.py")
        with open(script_path, "w") as f:
            f.write(request.script)
            
        # Determine Manim flags based on quality
        quality_flag = "-qm" # Medium quality (default)
        if request.quality == "low_quality":
            quality_flag = "-ql"
        elif request.quality == "high_quality":
            quality_flag = "-qh"
            
        # Run Manim command
        # manim -qm script.py SceneName -o output_filename
        output_filename = f"{job_id}"
        cmd = [
            "manim",
            quality_flag,
            script_path,
            request.scene_id,
            "-o", output_filename,
            "--media_dir", OUTPUT_DIR
        ]
        
        logger.info(f"Starting render for job {job_id}: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300 # 5 minute timeout
        )
        
        if result.returncode == 0:
            jobs[job_id]["status"] = "completed"
            jobs[job_id]["completed_at"] = datetime.utcnow().isoformat()
            jobs[job_id]["progress"] = 100
            # Manim output path structure: media_dir/videos/script_name/quality/scene_name.mp4
            # note: manim command above might output differently depending on version
            # With specific -o, it should be predictable.
            # However, Manim Community structure is: media/videos/{script_name}/{quality}/{scene_name}.mp4
            # We will search for the .mp4 file in the output dir
            
            # Simple check for output file
            # Assuming manim outputs to specific path or we find it
            # For simplicity in this worker, we'll traverse to find the mp4
            video_path = find_video_output(OUTPUT_DIR, job_id)
            if video_path:
                jobs[job_id]["output_path"] = video_path
            else:
                 jobs[job_id]["status"] = "failed"
                 jobs[job_id]["error"] = "Output video not found"
                 
        else:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["error"] = result.stderr
            logger.error(f"Render failed for job {job_id}: {result.stderr}")

    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        logger.error(f"Job {job_id} exception: {e}")

def find_video_output(base_dir, job_id_prefix):
    """Helper to find the generated video file."""
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.endswith(".mp4") and job_id_prefix in file:
                return os.path.join(root, file)
            # Find any mp4 if we can't match name exactly (fallback)
            if file.endswith(".mp4") and os.path.getmtime(os.path.join(root, file)) > (datetime.now().timestamp() - 300):
                 # Checks for recent file if specific name match fails (fallback logic)
                 pass
    return None


@app.post("/render")
async def submit_render(request: RenderRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "created_at": datetime.utcnow().isoformat(),
        "scene_id": request.scene_id
    }
    
    background_tasks.add_task(run_render_job, job_id, request)
    
    return jobs[job_id]

@app.get("/jobs/{job_id}/status")
async def get_job_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]

@app.get("/jobs/{job_id}/result")
async def get_job_result(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job = jobs[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job not completed")
        
    if "output_path" not in job or not os.path.exists(job["output_path"]):
         raise HTTPException(status_code=500, detail="Output file missing")
         
    return FileResponse(job["output_path"])

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "manim-render-worker"}


def run_full_render_job(job_id: str, request: RenderAllRequest):
    """Render all scenes, aggregate, and assemble final video."""
    try:
        jobs[job_id]["status"] = "processing"
        jobs[job_id]["started_at"] = datetime.utcnow().isoformat()
        jobs[job_id]["progress"] = 0
        
        quality_flag = "-ql"
        if request.quality == "medium_quality":
            quality_flag = "-qm"
        elif request.quality == "high_quality":
            quality_flag = "-qh"
        
        rendered_paths = []
        total_scenes = len(request.scenes)
        
        # Render each scene
        for i, scene in enumerate(request.scenes):
            jobs[job_id]["progress"] = int((i / total_scenes) * 80)
            jobs[job_id]["current_scene"] = scene.scene_id
            
            script_path = os.path.join(OUTPUT_DIR, f"{job_id}_{scene.scene_id}.py")
            with open(script_path, "w") as f:
                f.write(scene.script)
            
            output_name = f"{job_id}_{scene.scene_id}"
            cmd = [
                "manim", quality_flag, script_path, scene.scene_id,
                "-o", output_name, "--media_dir", OUTPUT_DIR
            ]
            
            logger.info(f"Rendering scene {i+1}/{total_scenes}: {scene.scene_id}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            
            if result.returncode != 0:
                jobs[job_id]["status"] = "failed"
                jobs[job_id]["error"] = f"Scene {scene.scene_id} failed: {result.stderr[:500]}"
                logger.error(f"Scene {scene.scene_id} failed: {result.stderr}")
                return
            
            video_path = find_video_output(OUTPUT_DIR, output_name)
            if video_path:
                rendered_paths.append(video_path)
            else:
                jobs[job_id]["status"] = "failed"
                jobs[job_id]["error"] = f"Output not found for {scene.scene_id}"
                return
        
        jobs[job_id]["progress"] = 85
        jobs[job_id]["current_scene"] = "aggregating"
        
        # Aggregate scenes with ffmpeg
        final_path = os.path.join(OUTPUT_DIR, f"{job_id}_final.mp4")
        
        if len(rendered_paths) == 1:
            # Single scene - just copy
            os.rename(rendered_paths[0], final_path)
        else:
            # Multiple scenes - concatenate
            concat_file = os.path.join(OUTPUT_DIR, f"{job_id}_concat.txt")
            with open(concat_file, "w") as f:
                for path in rendered_paths:
                    f.write(f"file '{path}'\n")
            
            concat_cmd = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", concat_file, "-c", "copy", final_path
            ]
            
            result = subprocess.run(concat_cmd, capture_output=True, text=True, timeout=300)
            os.unlink(concat_file)
            
            if result.returncode != 0:
                jobs[job_id]["status"] = "failed"
                jobs[job_id]["error"] = f"Aggregation failed: {result.stderr[:500]}"
                return
        
        jobs[job_id]["progress"] = 100
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["completed_at"] = datetime.utcnow().isoformat()
        jobs[job_id]["output_path"] = final_path
        jobs[job_id]["scene_count"] = len(rendered_paths)
        logger.info(f"Job {job_id} completed: {final_path}")
        
    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        logger.error(f"Job {job_id} exception: {e}")


@app.post("/render-all")
async def submit_full_render(request: RenderAllRequest, background_tasks: BackgroundTasks):
    """Submit all scenes for rendering, aggregation, and assembly."""
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "created_at": datetime.utcnow().isoformat(),
        "scene_count": len(request.scenes),
        "progress": 0
    }
    
    background_tasks.add_task(run_full_render_job, job_id, request)
    
    return jobs[job_id]
