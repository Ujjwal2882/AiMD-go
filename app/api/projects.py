"""
AiMD-go Projects Endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List
from uuid import uuid4

from app.schemas.projects import ProjectCreate, ProjectResponse
from app.storage.database import get_db
from app.storage.models import Project

router = APIRouter(prefix="/api", tags=["Projects"])

@router.post("/projects", response_model=ProjectResponse)
def create_project(project: ProjectCreate, db = Depends(get_db)):
    project_id = str(uuid4())[:12]
    new_project = Project(
        id=project_id,
        name=project.name,
        description=project.description
    )
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
    
    return {
        "id": new_project.id,
        "name": new_project.name,
        "description": new_project.description,
        "created_at": str(new_project.created_at),
        "updated_at": str(new_project.updated_at),
        "layer_ids": [l.id for l in new_project.layers]
    }

@router.get("/projects", response_model=List[ProjectResponse])
def list_projects(db = Depends(get_db)):
    projects = db.query(Project).all()
    return [{
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "created_at": str(p.created_at),
        "updated_at": str(p.updated_at),
        "layer_ids": [l.id for l in p.layers]
    } for p in projects]

@router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, db = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "created_at": str(project.created_at),
        "updated_at": str(project.updated_at),
        "layer_ids": [l.id for l in project.layers]
    }

@router.delete("/projects/{project_id}")
def delete_project(project_id: str, db = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()
    return {"status": "success", "message": "Project deleted"}
