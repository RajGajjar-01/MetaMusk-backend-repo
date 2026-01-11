from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes.prompt_enhancement import router as prompt_router
from app.api.routes.agents import router as agents_router
import logging
import sys
import os

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Set specific loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)
logger.info("🚀 Starting MetaMusk Backend...")

# Ensure media directory exists with absolute path
from pathlib import Path
MEDIA_DIR = Path(__file__).parent.parent / "media"
MEDIA_DIR.mkdir(exist_ok=True)
logger.info(f"📁 Media directory: {MEDIA_DIR}")

app = FastAPI(
    title="MetaMusk Multi-Agent Backend",
    description="Educational video generation using multi-agent AI system",
    version="1.0.0"
)

# Mount media directory for static files
app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(prompt_router)
app.include_router(agents_router)

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "metamusk-backend",
        "version": "1.0.0"
    }

@app.get("/")
def read_root():
    return {
        "message": "Welcome to MetaMusk Multi-Agent Backend",
        "docs": "/docs",
        "endpoints": {
            "prompt_enhancement": "/prompt/enhance",
            "video_generation": "/agents/generate-video",
            "agents_health": "/agents/health",
            "agents_stats": "/agents/stats",
            "health": "/health"
        }
    }
