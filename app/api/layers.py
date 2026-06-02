"""
AiMD-go Layer API Endpoints
CRUD operations for map layers — metadata, GeoJSON data, style, visibility.
"""

from fastapi import APIRouter, HTTPException
from typing import Optional

from app.storage import storage

router = APIRouter(prefix="/api", tags=["Layers"])


@router.get("/layers")
async def list_layers(project_id: Optional[str] = None):
    """List all layers, optionally filtered by project."""
    layers = storage.list_layers(project_id=project_id)
    return {"layers": layers, "count": len(layers)}


@router.get("/layers/{layer_id}")
async def get_layer(layer_id: str):
    """Get layer metadata."""
    meta = storage.get_layer_metadata(layer_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Layer '{layer_id}' not found")
    return meta


@router.get("/layers/{layer_id}/geojson")
async def get_layer_geojson(layer_id: str):
    """Get the full GeoJSON data for a layer."""
    meta = storage.get_layer_metadata(layer_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Layer '{layer_id}' not found")

    geojson = storage.get_layer_geojson(layer_id)
    if not geojson:
        raise HTTPException(status_code=404, detail=f"GeoJSON data not found for layer '{layer_id}'")

    return geojson


@router.put("/layers/{layer_id}/style")
async def update_layer_style(layer_id: str, style: dict):
    """Update the visual style of a layer."""
    meta = storage.update_layer_style(layer_id, style)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Layer '{layer_id}' not found")
    return {"status": "success", "layer": meta}


@router.put("/layers/{layer_id}/visibility")
async def toggle_layer_visibility(layer_id: str, visible: bool = True):
    """Toggle layer visibility on the map."""
    meta = storage.update_layer_visibility(layer_id, visible)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Layer '{layer_id}' not found")
    return {"status": "success", "layer": meta}


@router.delete("/layers/{layer_id}")
async def delete_layer(layer_id: str):
    """Delete a layer and its GeoJSON data."""
    success = storage.delete_layer(layer_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Layer '{layer_id}' not found")
    return {"status": "success", "message": f"Layer '{layer_id}' deleted"}
