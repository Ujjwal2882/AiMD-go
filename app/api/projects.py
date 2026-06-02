"""
AiMD-go Project API Endpoints
Project management — CRUD operations for organizing layers into projects.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.storage import storage

router = APIRouter(prefix="/api", tags=["Projects"])


class ProjectCreateRequest(BaseModel):
    name: str
    description: str = ""


@router.get("/projects")
async def list_projects():
    """List all projects."""
    projects = storage.list_projects()
    return {"projects": projects, "count": len(projects)}


@router.post("/projects")
async def create_project(request: ProjectCreateRequest):
    """Create a new project."""
    if not request.name.strip():
        raise HTTPException(status_code=400, detail="Project name is required")

    project = storage.create_project(
        name=request.name.strip(),
        description=request.description.strip(),
    )
    return {"status": "success", "project": project}


@router.get("/projects/{project_id}")
async def get_project(project_id: str):
    """Get project details with its layers."""
    project = storage.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    # Include layer metadata
    layers = storage.list_layers(project_id=project_id)
    project["layers"] = layers

    return project


@router.put("/projects/{project_id}")
async def update_project(project_id: str, request: ProjectCreateRequest):
    """Update project name/description."""
    project = storage.update_project(project_id, {
        "name": request.name.strip(),
        "description": request.description.strip(),
    })
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return {"status": "success", "project": project}


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    """Delete a project and all its layers."""
    success = storage.delete_project(project_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return {"status": "success", "message": f"Project '{project_id}' deleted"}
