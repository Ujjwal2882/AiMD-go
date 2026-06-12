"""
AiMD-go Layer Management Endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional

from app.services.layer_svc import layer_svc
from app.schemas.layers import LayerMetadata

router = APIRouter(prefix="/api", tags=["Layers"])

@router.get("/layers", response_model=List[LayerMetadata])
async def list_layers(project_id: Optional[str] = None):
    return layer_svc.list_layers(project_id=project_id)

@router.get("/layers/{layer_id}", response_model=LayerMetadata)
async def get_layer_metadata(layer_id: str):
    layer = layer_svc.get_layer_metadata(layer_id)
    if not layer:
        raise HTTPException(status_code=404, detail="Layer not found")
    return layer
