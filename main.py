"""
🌍 AiMD-go — AI-Powered Geospatial Data Visualization Platform
Main Entry Point
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

from app.core.config import settings
from app.core.logging import setup_logging
from app.api import upload, layers, projects, detect, search, export, change_detect

# Initialize logging
setup_logging()

# ──────────────────── FastAPI Application ────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-Powered Geospatial Data Visualization Platform",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware — reads allowed origins from CORS_ORIGINS env var
# In production: CORS_ORIGINS="https://aimd-go.netlify.app"
# In development: defaults to localhost
cors_origins_str = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000")
cors_origins = [origin.strip() for origin in cors_origins_str.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
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
app.include_router(change_detect.router)


# ──────────────────── Health Check ────────────────────

@app.get("/health", tags=["System"])
@app.get("/api/health", tags=["System"])
async def health_check():
    """
    Health check endpoint.
    Used by Render health checks and the GitHub Actions keep-alive cron.
    Available at both /health and /api/health.
    """
    import time
    db_ok = False
    try:
        import psycopg2
        conn = psycopg2.connect(settings.DATABASE_URL)
        conn.cursor().execute("SELECT 1")
        conn.close()
        db_ok = True
    except Exception:
        pass

    return {
        "status": "healthy" if db_ok else "degraded",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "database": "connected" if db_ok else "unreachable",
        "timestamp": time.time(),
    }


# ──────────────────── Static Files & Frontend ────────────────────

# The UI is now served separately on port 3000.
# API runs strictly on port 8000.

from fastapi.responses import RedirectResponse

@app.get("/", tags=["Frontend"])
async def root_redirect():
    """Redirect users to the UI on port 3000."""
    return RedirectResponse(url="http://localhost:3000")


# ──────────────────── Startup Events ────────────────────

@app.on_event("startup")
async def startup_event():
    """Initialize directories, DB tables, and print startup banner."""
    settings.init_directories()

    # Initialize DB tables (lazy — only at startup, not at import)
    try:
        from app.storage.database import engine, Base
        Base.metadata.create_all(bind=engine)
        print("  [DB] Tables initialized successfully")
    except Exception as e:
        print(f"  [DB] Warning: Could not initialize tables: {e}")

    print("\n" + "=" * 60)
    print(f"  [AiMD-go] {settings.APP_NAME} v{settings.APP_VERSION}")
    print(f"  AI-Powered Geospatial Data Visualization Platform")
    print("=" * 60)
    print(f"  [Web UI]    http://localhost:3000")
    print(f"  [API Docs]  http://localhost:{settings.PORT}/docs")
    print(f"  [Data Dir]  {settings.DATA_DIR}")
    print("=" * 60 + "\n")


# ──────────────────── Main Entry Point ────────────────────

if __name__ == "__main__":
    # Initialize directories
    settings.init_directories()

    # Auto-open browser to the UI port (3000)
    try:
        webbrowser.open("http://localhost:3000")
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
