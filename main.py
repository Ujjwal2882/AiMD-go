"""
🌍 AiMD-go — AI-Powered Geospatial Data Visualization Platform
Main Entry Point

Usage:
    python main.py

Starts the FastAPI server on http://localhost:8000
Serves both the web UI and REST API from a single process.
"""

import os
import sys
import webbrowser
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.api import upload, layers, projects, detect, search, export

# ──────────────────── FastAPI Application ────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-Powered Geospatial Data Visualization Platform",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware (allow all origins for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────── Register API Routes ────────────────────

app.include_router(upload.router)
app.include_router(layers.router)
app.include_router(projects.router)
app.include_router(detect.router)
app.include_router(search.router)
app.include_router(export.router)


# ──────────────────── Health Check ────────────────────

@app.get("/api/health", tags=["System"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


# ──────────────────── Static Files & Frontend ────────────────────

# Mount static files (CSS, JS, assets)
static_dir = settings.STATIC_DIR
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", tags=["Frontend"])
async def serve_frontend():
    """Serve the main frontend HTML page."""
    index_path = static_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "Frontend not found. Place index.html in ./static/"}


# ──────────────────── Startup Events ────────────────────

@app.on_event("startup")
async def startup_event():
    """Initialize directories and print startup banner."""
    settings.init_directories()

    print("\n" + "=" * 60)
    print(f"  [AiMD-go] {settings.APP_NAME} v{settings.APP_VERSION}")
    print(f"  AI-Powered Geospatial Data Visualization Platform")
    print("=" * 60)
    print(f"  [Web UI]    http://localhost:{settings.PORT}")
    print(f"  [API Docs]  http://localhost:{settings.PORT}/docs")
    print(f"  [Data Dir]  {settings.DATA_DIR}")
    print("=" * 60 + "\n")


# ──────────────────── Main Entry Point ────────────────────

if __name__ == "__main__":
    # Initialize directories
    settings.init_directories()

    # Auto-open browser
    try:
        webbrowser.open(f"http://localhost:{settings.PORT}")
    except Exception:
        pass

    # Start server
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info",
    )
